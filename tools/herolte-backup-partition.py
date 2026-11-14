#!/usr/bin/env python3
"""herolte-backup-partition.py: copia de SOLO LECTURA de una partición del S7 desde TWRP, por trozos verificados.

  herolte-backup-partition.py NOMBRE DISPOSITIVO SALIDA.img [--chunk-mib 128] [--retries 4]
  p. ej.  herolte-backup-partition.py USERDATA /dev/block/sda18 /media/.../USERDATA.img

Para cada trozo (unidades de 4096 B, el tamaño de sector de la UFS): lee el trozo con `dd ... | nc -l` en el teléfono y `adb forward` (BACKUP_TRANSPORT=exec usa `adb exec-out`, 30 veces más lento), calcula su
SHA-256 en el PC, calcula el SHA-256 del MISMO trozo en el teléfono (`dd ... | sha256sum`) y solo lo acepta si coinciden; reintenta
(esperando a que adb vea el teléfono) si hay desconexión o discrepancia. Es REANUDABLE: SALIDA.img.state guarda los trozos
aceptados y sus hashes. Al final comprueba que el tamaño del fichero es el de la partición y escribe SALIDA.img.sha256 con el hash
de todo el fichero. NUNCA escribe en el teléfono: solo `dd if=`, `blockdev --getsize64` y `sha256sum`. ADB=ruta del adb (por defecto adb).
"""
import argparse, hashlib, json, os, socket, subprocess, sys, time

ADB = os.environ.get('ADB', 'adb')
UNIT = 4096


def adb(*args, capture=True, timeout=None):
    return subprocess.run([ADB, *args], capture_output=capture, timeout=timeout)


def wait_device(deadline=600):
    t0 = time.time()
    while time.time() - t0 < deadline:
        r = adb('devices')
        lines = [l for l in r.stdout.decode().splitlines()[1:] if l.strip()]
        if len(lines) == 1 and lines[0].split()[1] == 'recovery':
            return True
        adb('reconnect', 'offline')
        time.sleep(5)
    return False


def phone_size(dev):
    r = adb('shell', 'blockdev --getsize64 %s' % dev)
    return int(r.stdout.decode().strip())


PORT = int(os.environ.get('BACKUP_PORT', '5555'))
TRANSPORT = os.environ.get('BACKUP_TRANSPORT', 'nc')   # 'nc' (rápido: ~30 MB/s) o 'exec' (adb exec-out: ~1 MB/s en este TWRP; lo usan las pruebas)


def read_chunk_exec(dev, skip, count):
    r = adb('exec-out', 'dd if=%s bs=%d skip=%d count=%d 2>/dev/null' % (dev, UNIT, skip, count), timeout=900)
    return r.stdout


def read_chunk_nc(dev, skip, count):
    """El teléfono sirve el trozo con `dd | nc -l` y el PC lo lee por `adb forward` (30 veces más rápido que exec-out en este TWRP).
    Solo lectura del disco; el único efecto en el teléfono es un proceso nc temporal que escucha en un puerto local de adb."""
    adb('shell', 'killall nc 2>/dev/null')
    adb('forward', 'tcp:%d' % PORT, 'tcp:%d' % PORT)
    srv = subprocess.Popen([ADB, 'shell', 'dd if=%s bs=%d skip=%d count=%d 2>/dev/null | nc -l -p %d' % (dev, UNIT, skip, count, PORT)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    want = count * UNIT; data = b''
    try:
        for _ in range(8):                       # el listener tarda un instante en existir; sin él el forward cierra al momento
            time.sleep(1.0)
            data = b''
            try:
                c = socket.create_connection(('127.0.0.1', PORT), timeout=30)
                c.settimeout(120)
                parts = []
                while True:
                    b = c.recv(1 << 20)
                    if not b: break
                    parts.append(b)
                c.close(); data = b''.join(parts)
            except (OSError, socket.timeout):
                data = b''
            if len(data) == want: break
            if data: break                        # datos parciales: que lo reintente el bucle superior
    finally:
        srv.terminate()
        try: srv.wait(5)
        except subprocess.TimeoutExpired: srv.kill()
        adb('shell', 'killall nc 2>/dev/null')
    return data


def read_chunk(dev, skip, count):
    return read_chunk_nc(dev, skip, count) if TRANSPORT == 'nc' else read_chunk_exec(dev, skip, count)


def phone_hash(dev, skip, count):
    r = adb('shell', 'dd if=%s bs=%d skip=%d count=%d 2>/dev/null | sha256sum' % (dev, UNIT, skip, count), timeout=900)
    out = r.stdout.decode().split()
    return out[0] if out else ''


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('name'); ap.add_argument('dev'); ap.add_argument('out')
    ap.add_argument('--chunk-mib', type=int, default=128); ap.add_argument('--chunk-kib', type=int, default=0, help='solo para pruebas'); ap.add_argument('--retries', type=int, default=4)
    a = ap.parse_args(argv)
    if not wait_device(60):
        print('ABORTA: no hay exactamente un dispositivo en recovery'); return 2
    size = phone_size(a.dev)
    if size <= 0 or size % UNIT:
        print('ABORTA: tamaño de %s no válido: %d' % (a.dev, size)); return 2
    units = size // UNIT; chunk = (a.chunk_kib * 1024 if a.chunk_kib else a.chunk_mib * 1048576) // UNIT
    state_path = a.out + '.state'
    state = {'name': a.name, 'dev': a.dev, 'size': size, 'chunk_units': chunk, 'done': {}}
    if os.path.exists(state_path):
        old = json.load(open(state_path))
        if old.get('dev') == a.dev and old.get('size') == size and old.get('chunk_units') == chunk: state = old
        else: print('ABORTA: el estado previo no coincide con esta partición/tamaño/trozo'); return 2
    mode = 'r+b' if os.path.exists(a.out) else 'w+b'
    n = (units + chunk - 1) // chunk
    t0 = time.time(); got = 0
    with open(a.out, mode) as f:
        f.truncate(size)
        for i in range(n):
            if str(i) in state['done']: continue
            skip = i * chunk; count = min(chunk, units - skip)
            ok = False
            for attempt in range(a.retries):
                if not wait_device(600): print('ABORTA: el teléfono no vuelve'); return 3
                try:
                    data = read_chunk(a.dev, skip, count)
                    want = phone_hash(a.dev, skip, count)
                except subprocess.TimeoutExpired:
                    data = b''; want = ''
                have = hashlib.sha256(data).hexdigest()
                if len(data) == count * UNIT and have == want:
                    f.seek(skip * UNIT); f.write(data); f.flush(); os.fsync(f.fileno())
                    state['done'][str(i)] = have; ok = True; break
                print('trozo %d intento %d: %d B (esperado %d) hash %s teléfono %s' % (i, attempt + 1, len(data), count * UNIT, have[:12], want[:12]), flush=True)
            if not ok: print('ABORTA: el trozo %d no se pudo leer verificado' % i); return 4
            json.dump(state, open(state_path + '.tmp', 'w')); os.replace(state_path + '.tmp', state_path)
            got += count * UNIT
            if i % 10 == 0 or i == n - 1:
                print('%s: trozo %d/%d  %.1f MB/s' % (a.name, i + 1, n, got / 1e6 / max(time.time() - t0, 1e-6)), flush=True)
    if os.path.getsize(a.out) != size: print('ABORTA: el tamaño final no es el de la partición'); return 5
    h = hashlib.sha256()
    with open(a.out, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 24), b''): h.update(blk)
    open(a.out + '.sha256', 'w').write('%s  %s\n' % (h.hexdigest(), os.path.basename(a.out)))
    print('OK %s: %d B, sha256 %s' % (a.name, size, h.hexdigest()))
    return 0


if __name__ == '__main__': sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""herolte-write-userdata.py: escribe una imagen (la raíz iOS HFS+) en la partición USERDATA del S7 desde TWRP, por trozos verificados.

  herolte-write-userdata.py IMAGEN SHA256 [--execute] [--task T-0044] [--chunk-mib 64] [--state FICHERO] [--dry-transport]

ACCIÓN ROJA (device-write-userdata): BORRA Android (USERDATA). Sin --execute solo comprueba y enseña el plan (no escribe nada ni abre
conexión de escritura). Con --execute exige TODO esto:
  - la imagen existe, su tamaño es múltiplo de 4096 y su SHA-256 es exactamente el argumento SHA256;
  - hay un único dispositivo en recovery; `by-name/USERDATA` apunta a sda18 y mide lo esperado; la imagen cabe;
  - USERDATA no está montada en el teléfono;
  - `governance.py gate device-write-userdata --task TAREA` sale con 0 (decisión APPROVED del Director que NOMBRE la acción).
Transporte (el de la copia de seguridad, ~18 MB/s; `adb push`/`exec-in` son lentos o no funcionan en este TWRP): el PC envía cada
trozo a `nc -l -p PUERTO | dd of=USERDATA seek=…` en el teléfono por `adb forward`; después el teléfono calcula el SHA-256 del MISMO
rango leído del disco y solo se acepta si coincide con el del PC (reintenta). Es REANUDABLE (--state). Al final el teléfono calcula el
SHA-256 del prefijo del disco con el tamaño de la imagen y debe ser el de la imagen. --dry-transport manda los trozos a /dev/null en el
teléfono (prueba el transporte sin escribir el disco). Nunca toca otra partición: la única ruta de escritura es USERDATA.
"""
import argparse, hashlib, json, os, socket, subprocess, sys, time

ADB = os.environ.get('ADB', 'adb')
DEV = os.environ.get('USERDATA_DEV', '/dev/block/platform/155a0000.ufs/by-name/USERDATA')
EXPECT_BLOCK = os.environ.get('USERDATA_BLOCK', 'sda18')
EXPECT_SIZE = int(os.environ.get('USERDATA_SIZE', '23431790592'))
UNIT = 4096
HERE = os.path.dirname(os.path.abspath(__file__))


def adb(*a, timeout=None):
    return subprocess.run([ADB, *a], capture_output=True, timeout=timeout)


def one_recovery(deadline=600):
    t0 = time.time()
    while time.time() - t0 < deadline:
        lines = [l for l in adb('devices').stdout.decode().splitlines()[1:] if l.strip()]
        if len(lines) == 1 and lines[0].split()[1] == 'recovery': return True
        adb('reconnect', 'offline'); time.sleep(5)
    return False


def sh(cmd, timeout=None): return adb('shell', cmd, timeout=timeout).stdout.decode().strip()


def sha_file_range(path, off, n):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        f.seek(off); left = n
        while left:
            b = f.read(min(left, 1 << 24))
            if not b: raise SystemExit('lectura corta de la imagen')
            h.update(b); left -= len(b)
    return h.hexdigest()


def send_chunk(data, skip, count, port, target):
    adb('shell', 'killall nc 2>/dev/null')
    adb('forward', 'tcp:%d' % port, 'tcp:%d' % port)
    srv = subprocess.Popen([ADB, 'shell', 'nc -l -p %d | dd of=%s bs=%d seek=%d count=%d conv=fsync 2>/dev/null' % (port, target, UNIT, skip, count)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = False
    try:
        for _ in range(8):
            time.sleep(1.0)
            try:
                c = socket.create_connection(('127.0.0.1', port), timeout=30); c.settimeout(120)
                c.sendall(data); c.shutdown(socket.SHUT_WR)
                try: c.recv(1)
                except OSError: pass
                c.close(); ok = True; break
            except OSError:
                continue
        try: srv.wait(120)
        except subprocess.TimeoutExpired: srv.kill()
    finally:
        if srv.poll() is None: srv.kill()
        adb('shell', 'killall nc 2>/dev/null')
    return ok


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('image'); ap.add_argument('sha256'); ap.add_argument('--execute', action='store_true')
    ap.add_argument('--task', default='T-0044'); ap.add_argument('--chunk-mib', type=int, default=64)
    ap.add_argument('--state'); ap.add_argument('--port', type=int, default=5556); ap.add_argument('--retries', type=int, default=4)
    ap.add_argument('--dry-transport', action='store_true'); ap.add_argument('--max-chunks', type=int, default=0, help='solo con --dry-transport: enviar solo los N primeros trozos'); ap.add_argument('--no-gate', action='store_true', help='solo pruebas con adb falso')
    a = ap.parse_args(argv)
    img = a.image
    if not os.path.isfile(img) or os.path.islink(img): print('ABORTA: la imagen no existe o es un symlink'); return 2
    size = os.path.getsize(img)
    if size % UNIT or size == 0: print('ABORTA: el tamaño de la imagen no es múltiplo de 4096'); return 2
    if len(a.sha256) != 64: print('ABORTA: SHA256 no válido'); return 2
    h = hashlib.sha256()
    with open(img, 'rb') as f:
        for b in iter(lambda: f.read(1 << 24), b''): h.update(b)
    if h.hexdigest() != a.sha256: print('ABORTA: el hash de la imagen (%s) no es el esperado' % h.hexdigest()); return 2
    print('imagen OK: %d B sha256 %s' % (size, a.sha256))
    if not one_recovery(60): print('ABORTA: debe haber exactamente un dispositivo en recovery'); return 3
    link = sh('readlink -f %s' % DEV)
    psize = int(sh('blockdev --getsize64 %s' % DEV) or 0)
    mounts = sh('cat /proc/mounts')
    print('USERDATA -> %s, %d B (esperado %s, %d B)' % (link, psize, EXPECT_BLOCK, EXPECT_SIZE))
    if not link.endswith('/' + EXPECT_BLOCK) or psize != EXPECT_SIZE: print('ABORTA: la partición no es la esperada'); return 3
    if size > psize: print('ABORTA: la imagen no cabe'); return 3
    if (EXPECT_BLOCK in mounts or ' /data ' in mounts) and not a.dry_transport: print('ABORTA: USERDATA/data está montada en el teléfono (desmontar /sdcard y /data en TWRP antes de escribir)'); return 3
    if EXPECT_BLOCK in mounts: print('aviso: USERDATA está montada en TWRP (/data, /sdcard); es una prueba de transporte, no se escribe el disco')
    chunk = a.chunk_mib * 1048576 // UNIT; units = size // UNIT; n = (units + chunk - 1) // chunk
    print('plan: %d trozos de %d MiB hacia %s%s' % (n, a.chunk_mib, 'ESTO NO ES UNA PRUEBA: ' if a.execute and not a.dry_transport else '', '/dev/null (prueba del transporte)' if a.dry_transport else DEV))
    if not a.execute: print('ENSAYO: no se escribe nada. Con --execute y la autorización registrada se escribiría.'); return 0
    if not a.dry_transport and not a.no_gate:
        rc = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'governance.py'), 'gate', 'device-write-userdata', '--task', a.task]).returncode
        if rc != 0: print('ABORTA: el gobierno NO registra una autorización vigente de device-write-userdata para %s' % a.task); return 4
    target = '/dev/null' if a.dry_transport else DEV
    state_path = a.state or (img + '.write.state'); state = {'sha256': a.sha256, 'chunk': chunk, 'done': {}}
    if os.path.exists(state_path):
        old = json.load(open(state_path))
        if old.get('sha256') == a.sha256 and old.get('chunk') == chunk: state = old
        else: print('ABORTA: el estado previo no corresponde a esta imagen/trozo'); return 2
    t0 = time.time(); moved = 0
    with open(img, 'rb') as f:
        for i in range(n):
            if str(i) in state['done']: continue
            if a.dry_transport and a.max_chunks and i >= a.max_chunks: break
            skip = i * chunk; count = min(chunk, units - skip); f.seek(skip * UNIT); data = f.read(count * UNIT); want = hashlib.sha256(data).hexdigest()
            ok = False
            for attempt in range(a.retries):
                if not one_recovery(600): print('ABORTA: el teléfono no vuelve'); return 5
                if send_chunk(data, skip, count, a.port, target):
                    got = want if a.dry_transport else sh('dd if=%s bs=%d skip=%d count=%d 2>/dev/null | sha256sum' % (DEV, UNIT, skip, count), timeout=900).split()[0:1]
                    got = got if isinstance(got, str) else (got[0] if got else '')
                    if got == want: ok = True; break
                print('trozo %d intento %d: sin confirmar' % (i, attempt + 1), flush=True)
            if not ok: print('ABORTA: el trozo %d no se pudo escribir verificado' % i); return 6
            state['done'][str(i)] = want; json.dump(state, open(state_path + '.tmp', 'w')); os.replace(state_path + '.tmp', state_path)
            moved += count * UNIT
            if i % 10 == 0 or i == n - 1: print('trozo %d/%d  %.1f MB/s' % (i + 1, n, moved / 1e6 / max(time.time() - t0, 1e-6)), flush=True)
    if a.dry_transport: print('OK transporte: %d trozos enviados a /dev/null' % len(state['done'])); return 0
    mb = 1048576
    final = sh('dd if=%s bs=%d count=%d 2>/dev/null | sha256sum' % (DEV, mb if size % mb == 0 else UNIT, size // mb if size % mb == 0 else size // UNIT), timeout=3600).split()
    if not final or final[0] != a.sha256: print('FALLA: el hash del prefijo de USERDATA (%s) no es el de la imagen' % (final[0] if final else '?')); return 7
    print('OK: USERDATA contiene la imagen (%d B), sha256 %s leído en el teléfono' % (size, a.sha256)); return 0


if __name__ == '__main__': sys.exit(main(sys.argv[1:]))

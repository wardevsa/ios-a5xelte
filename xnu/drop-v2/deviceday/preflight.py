#!/usr/bin/env python3
"""Comprobaciones previas al día del dispositivo. En el anfitrión no escribe nada fuera de un directorio temporal.

  python3 -I xnu/drop-v2/deviceday/preflight.py [--kit DIR] [--kernel PATH] [--device]

  --kit DIR     kit de artefactos (por defecto ~/HackiOS/builds/device-day)
  --kernel P    kernel candidato: lo clasifica (¿es DROP v2?) mirando los mensajes que contiene
  --device      además, LEE el estado del teléfono por adb (solo órdenes de lectura: devices, get-state, ls,
                blockdev --getsize64). No escribe, no monta, no reinicia. Requiere TWRP y al responsable presente.

Sale con 0 solo si todo lo pedido está en orden. Una comprobación que no se puede hacer se marca como "AVISO".
"""
import argparse
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(HERE, '..', 'test'))
sys.path.insert(0, HERE)

BOOT_SIZE = 41943040            # --partition-size de la guía
results = {'ok': 0, 'fail': 0, 'warn': 0}


def report(kind, name, detail=''):
    results[kind] += 1
    tag = {'ok': 'OK', 'fail': 'FALLA', 'warn': 'AVISO'}[kind]
    print(f'  [{tag}] {name}{(" — " + detail) if detail else ""}')


def check(name, ok, detail=''):
    report('ok' if ok else 'fail', name, '' if ok else detail)


def sh(*cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def classify_kernel(path):
    data = open(path, 'rb').read()
    if data[:4] != b'\xcf\xfa\xed\xfe' or int.from_bytes(data[4:8], 'little') != 0x0100000C:
        return 'no es un Mach-O arm64'
    v2 = [b'resuming interrupted install of package', b'payload does not match its SHA-256',
          b'device cache flush failed']
    if all(m in data for m in v2):
        return 'DROP v2'
    if b'installed but .ready' in data:
        return 'DROP 0332 (marcadores .ready/.drop-id, sin barreras)'
    if b'entries written' in data:
        return 'DROP anterior a 0332'
    return 'sin DROP reconocible'


def section(t):
    print(f'\n{t}')


def host_checks(kit):
    section('Herramientas del anfitrión')
    for tool in ('adb', 'python3', 'gcc', 'clang', 'sha256sum'):
        check(tool, shutil.which(tool) is not None, 'no está en el PATH')
    report('ok' if shutil.which('aarch64-none-elf-gcc') or shutil.which('aarch64-linux-gnu-gcc') else 'warn',
           'compilador cruzado aarch64 (GCC) para el cargador',
           '' if shutil.which('aarch64-none-elf-gcc') or shutil.which('aarch64-linux-gnu-gcc')
           else 'no hay; el kit trae un cargador de conveniencia compilado con clang (loader-clang/)')

    section('Repositorio')
    branch = sh('git', '-C', REPO, 'branch', '--show-current').stdout.strip()
    print(f'      rama: {branch}, HEAD {sh("git", "-C", REPO, "rev-parse", "--short", "HEAD").stdout.strip()}')
    host = open(os.path.join(REPO, 'tools', 'herolte-drop.py')).read()
    check('tools/herolte-drop.py escribe HERODRP2', "ZONE_MAGIC = b'HERODRP2'" in host)
    hero = open(os.path.join(REPO, 'gpu', 'eagl', 'test', 'hero-run.c')).read()
    check('hero-run.c usa .drop/ready y consumed', 'dropv2_pending' in hero and 'DROP_CONSUMED' in hero)
    patches = sorted(os.listdir(os.path.join(REPO, 'xnu', 'patches')))
    has334 = '0334-herolte-drop-v2.patch' in patches   # nombre completo: upstream tiene otro 0334 (T-0009)
    report('ok' if has334 else 'warn', 'parche 0334-herolte-drop-v2 en xnu/patches/',
           '' if has334 else 'no está (queda en xnu/drop-v2/patches-proposed/): el CI NO lo compilará hasta que se adopte')
    if has334 and any(p.startswith('0333-herolte-drop-block1') for p in patches):
        report('fail', '0333 y 0334 a la vez en xnu/patches/',
               '0334 sustituye herolte_drop.c desde el estado 0332: con 0333 delante NO aplica y el CI lo salta en silencio')
    strays = [f for f in os.listdir(os.getcwd()) if f.startswith('herolte-drop') and f.endswith('.bin')]
    check('sin restos herolte-drop*.bin en el directorio actual', not strays, str(strays))

    section('Kit de artefactos')
    manifest = os.path.join(kit, 'MANIFEST.sha256')
    if not os.path.exists(manifest):
        report('fail', 'MANIFEST.sha256', f'no existe en {kit}')
        return
    bad = []
    n = 0
    for line in open(manifest):
        digest, rel = line.rstrip('\n').split('  ', 1)
        path = os.path.join(kit, rel)
        n += 1
        if not os.path.exists(path) or hashlib.sha256(open(path, 'rb').read()).hexdigest() != digest:
            bad.append(rel)
    check(f'{n} ficheros del kit coinciden con MANIFEST.sha256', not bad, str(bad[:5]))
    for rel in ('artifacts/kernel-0331-upstream-1c454bf/kernel.development.herolte',
                'artifacts/kernel-0332-fork-8d1cf43/kernel.development.herolte'):
        p = os.path.join(kit, rel)
        if os.path.exists(p):
            print(f'      {rel.split("/")[1]}: {classify_kernel(p)}')


def rehearsal():
    section('Ensayo del paquete de autoprueba contra el núcleo C (volumen simulado)')
    import make_selftest as ms
    argv, sys.argv = sys.argv, [sys.argv[0]]
    try:
        import test_core as tc
    finally:
        sys.argv = argv
    host = ms.load_host()
    fs = tc.initial()
    with tempfile.TemporaryDirectory(prefix='rehearsal-') as d:
        for variant, gen in (('a', 1), ('b', 2)):
            items = []
            for rel, data, mode in ms.content(variant):
                p = os.path.join(d, variant, rel)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, 'wb').write(data)
                os.chmod(p, mode)
                items.append((rel, p))
            blob, _, _ = host.pack(items, gen)
            env = tc.Env(fs, blob)
            rc = tc.boot(env)
            st = tc.parse_state(fs.read(tc.D + '/state'))
            ok = (rc == 0 and st and st['phase'] == 3 and st['gen'] == gen and
                  all(fs.read(tc.ROOT + '/' + r) == dt for r, dt, _ in ms.content(variant)) and
                  fs.read(tc.D + '/ready') == f'{gen}|{blob[32:64].hex()}'.encode())
            check(f'variante {variant} (generación {gen}): instalada y publicada', ok, '; '.join(env.logs))
        snap, ops0 = fs.snapshot(), fs.ops
        tc.boot(tc.Env(fs, blob))
        check('reinicio sin cambios: cero operaciones', fs.snapshot() == snap and fs.ops == ops0)


def device_checks():
    section('Teléfono (SOLO LECTURA, por adb)')
    adb = os.environ.get('HEROLTE_ADB', 'adb')
    devs = [l for l in sh(adb, 'devices').stdout.splitlines()[1:] if l.strip()]
    check('un único dispositivo conectado', len(devs) == 1, str(devs))
    state = sh(adb, 'get-state').stdout.strip()
    check('el teléfono está en recovery (TWRP)', state == 'recovery', f'estado: {state or "?"}')
    ls = sh(adb, 'shell', 'ls -l /dev/block/platform/155a0000.ufs/by-name/').stdout
    names = {}
    for line in ls.splitlines():
        parts = line.split()
        if len(parts) >= 2 and '->' in parts:
            i = parts.index('->')
            names[parts[i - 1]] = parts[i + 1]
    for part, dev in (('BOOT', '/dev/block/sda5'), ('USERDATA', '/dev/block/sda18')):
        check(f'{part} -> {dev} (la guía)', names.get(part) == dev, f'es {names.get(part)}')
    size = sh(adb, 'shell', f'blockdev --getsize64 {names.get("BOOT", "/dev/block/sda5")}').stdout.strip()
    check(f'BOOT mide {BOOT_SIZE} bytes', size == str(BOOT_SIZE), f'mide {size}')
    print('      particiones protegidas (NO se escriben nunca): EFS, RECOVERY, bootloader; EFS: copia de TWRP fuera del teléfono')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--kit', default=os.path.expanduser('~/HackiOS/builds/device-day'))
    ap.add_argument('--kernel')
    ap.add_argument('--device', action='store_true')
    args = ap.parse_args()
    host_checks(args.kit)
    if args.kernel:
        section('Kernel candidato')
        kind = classify_kernel(args.kernel)
        print(f'      {args.kernel}\n      sha256 {hashlib.sha256(open(args.kernel, "rb").read()).hexdigest()}\n      clasificación: {kind}')
        check('el kernel candidato es DROP v2', kind == 'DROP v2', kind)
    else:
        section('Kernel candidato')
        report('warn', 'sin --kernel', 'aún no hay kernel con DROP v2 (necesita compilación del CI)')
    rehearsal()
    if args.device:
        device_checks()
    print(f'\n{results["ok"]} correctas, {results["warn"]} avisos, {results["fail"]} fallos')
    return 1 if results['fail'] else 0


if __name__ == '__main__':
    sys.exit(main())

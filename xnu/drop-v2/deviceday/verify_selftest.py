#!/usr/bin/env python3
"""Comprueba, SOLO LEYENDO, que el paquete de autoprueba de DROP v2 quedó instalado en el teléfono.

  HEROLTE_ADB=adb python3 -I xnu/drop-v2/deviceday/verify_selftest.py EXPECTED.json

Requiere el teléfono en TWRP con /data desmontado. Usa tools/herolte-hfs-read.py, que solo hace `dd if=DEV`
mediante `adb exec-out`: no escribe nada. NO ejecutar sin el responsable del proyecto (toca el dispositivo).

Comprueba: contenido de cada fichero (SHA-256 y tamaño), .drop/state (COMMITTED, generación y SHA del paquete),
.drop/ready con el token esperado, y que no queden .drop/stage.list ni .drop/state.tmp.
"""
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
READER = os.path.join(REPO, 'tools', 'herolte-hfs-read.py')
ROOT = '/private/var/herolte'


def get(path, workdir):
    out = os.path.join(workdir, 'f.bin')
    if os.path.exists(out):
        os.remove(out)
    r = subprocess.run([sys.executable, '-I', READER, 'get', path, out], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out):
        return None, (r.stderr or r.stdout).strip()[-160:]
    with open(out, 'rb') as f:
        return f.read(), ''


def ls(path):
    r = subprocess.run([sys.executable, '-I', READER, 'ls', path], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    meta = json.load(open(sys.argv[1]))
    bad = []

    def check(name, ok, detail=''):
        print(f'  [{"OK" if ok else "FALLA"}] {name}{(" — " + detail) if detail and not ok else ""}')
        if not ok:
            bad.append(name)

    with tempfile.TemporaryDirectory(prefix='v2verify-') as w:
        for rel, exp in sorted(meta['files'].items()):
            data, err = get(f'{ROOT}/{rel}', w)
            check(rel, data is not None and len(data) == exp['size'] and
                  hashlib.sha256(data).hexdigest() == exp['sha256'],
                  err or ('contenido distinto' if data is not None else 'no existe'))
        st, err = get(f'{ROOT}/.drop/state', w)
        ok = st is not None and len(st) == 88 and st[:8] == b'HDROPST2' and hashlib.sha256(st[:56]).digest() == st[56:88]
        check('.drop/state válido', ok, err)
        if ok:
            phase, attempts, gen = struct.unpack_from('<IIQ', st, 8)
            check('estado COMMITTED (3)', phase == 3, f'fase {phase}')
            check('generación y SHA del estado', f'{gen}|{st[24:56].hex()}' == meta['ready_token'], f'{gen}|{st[24:56].hex()}')
            print(f'      intentos registrados: {attempts}')
        rd, err = get(f'{ROOT}/.drop/ready', w)
        check('.drop/ready con el token esperado', rd is not None and rd.decode(errors='replace') == meta['ready_token'], err)
        listing = ls(f'{ROOT}/.drop')
        check('listado de .drop', listing is not None)
        if listing is not None:
            for leftover in ('stage.list', 'state.tmp'):
                check(f'sin {leftover}', leftover not in listing)
    print('\n' + (f'FALLAN: {", ".join(bad)}' if bad else 'todo correcto'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

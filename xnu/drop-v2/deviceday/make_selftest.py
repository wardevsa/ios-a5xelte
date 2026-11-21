#!/usr/bin/env python3
"""Genera el paquete de AUTOPRUEBA de DROP v2 y la lista de lo que debe aparecer en el teléfono.

  python3 -I xnu/drop-v2/deviceday/make_selftest.py OUTDIR [--variant a|b]

Solo escribe en OUTDIR (fuera del repositorio). No toca ningún dispositivo.
Los ficheros son inocuos y se instalan bajo /private/var/herolte/v2test/ (nada que iOS lea):
  hello.txt, bin/run.sh (0755), big.bin (2,5 MiB: varias ventanas de 1 MiB), empty (0 bytes), deep/a/b/c/leaf.txt.
`--variant b` cambia hello.txt y big.bin: sirve para la segunda prueba (actualización sobre lo ya instalado).

Salida: OUTDIR/files/..., OUTDIR/expected.json (ruta -> sha256, modo, tamaño; y el token esperado de
.drop/ready) y OUTDIR/command.txt con la orden exacta de tools/herolte-drop.py.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))


def load_host():
    spec = importlib.util.spec_from_file_location('herolte_drop', os.path.join(REPO, 'tools', 'herolte-drop.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def content(variant):
    rng = random.Random(f'herolte-v2-selftest-{variant}')
    return [
        ('v2test/hello.txt', f'DROP v2 selftest, variant {variant}\n'.encode(), 0o644),
        ('v2test/bin/run.sh', b'#!/bin/sh\necho v2test\n', 0o755),
        ('v2test/big.bin', rng.randbytes(2_621_440 + (4096 if variant == 'b' else 0)), 0o644),
        ('v2test/empty', b'', 0o644),
        ('v2test/deep/a/b/c/leaf.txt', b'leaf\n', 0o644),
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('outdir')
    ap.add_argument('--variant', choices=('a', 'b'), default='a')
    ap.add_argument('--generation', type=int, default=1)
    args = ap.parse_args()
    out = os.path.abspath(args.outdir)
    if os.path.commonpath([out, REPO]) == REPO:
        raise SystemExit('OUTDIR must be outside the repository')
    host = load_host()
    items, expected = [], {}
    for rel, data, mode in content(args.variant):
        path = os.path.join(out, 'files', rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data)
        os.chmod(path, mode)
        items.append((rel, path))
        expected[rel] = {'sha256': hashlib.sha256(data).hexdigest(), 'mode': mode, 'size': len(data)}
    blob, entries, ident = host.pack(items, args.generation)
    token = f'{args.generation}|{blob[32:64].hex()}'
    meta = {'variant': args.variant, 'generation': args.generation, 'ready_token': token,
            'files': expected, 'zone_blocks': len(blob) // 4096}
    with open(os.path.join(out, 'expected.json'), 'w') as f:
        json.dump(meta, f, indent=1, sort_keys=True)
    cmd = ('python3 tools/herolte-drop.py adb ' + ' '.join(f'{rel}={path}' for rel, path in items)
           + f' --generation {args.generation}')
    with open(os.path.join(out, 'command.txt'), 'w') as f:
        f.write(cmd + '\n')
    print(f'variant {args.variant}: {len(items)} files, zone image {len(blob)} bytes, ready token {token}')
    print(f'order of writing and the command: {out}/command.txt (DO NOT RUN without the project lead)')


if __name__ == '__main__':
    sys.exit(main())

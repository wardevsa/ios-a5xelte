#!/usr/bin/env python3
"""herolte-trim-dd-tail.py: quita de una copia hecha con `adb exec-out dd if=... ` el texto de estadísticas de dd que `exec-out` mezcla en stdout.

Síntoma (2026-11-14): BOOT.img de 41943138 bytes en vez de 41943040, con sha256 distinto aunque los primeros 41943040 bytes son idénticos.
La cola es exactamente: "N+0 records in\\nN+0 records out\\nB bytes (...) copied, ...\\n". B (los bytes copiados) es el tamaño real de la partición.

  python3 -I tools/herolte-trim-dd-tail.py DIR_O_FICHERO [...]            # SOLO INFORMA (por defecto)
  python3 -I tools/herolte-trim-dd-tail.py --apply DIR_O_FICHERO [...]    # recorta la cola con truncate y escribe FICHERO.trimmed.sha256

Comprobaciones antes de recortar (si una falla, no toca nada): la cola empieza exactamente en el byte B; "records in" y "records out" coinciden; tamaño del fichero = B + longitud de la cola.
Después de --apply, compara FICHERO.trimmed.sha256 con el `sha256sum` calculado EN EL TELÉFONO sobre la misma partición. No usar mientras otro proceso escribe esos ficheros."""
import os, re, sys, hashlib

TAIL = re.compile(rb'(\d+)\+(\d+) records in\r?\n(\d+)\+(\d+) records out\r?\n(\d+) bytes[^\n]*copied[^\n]*\n?$')


def analyse(path, window=512):
    size = os.path.getsize(path)
    with open(path, 'rb') as f:
        f.seek(max(0, size - window)); tail = f.read()
    m = TAIL.search(tail)
    if not m: return dict(path=path, status='SIN-COLA', size=size)
    b = int(m.group(5)); tail_len = len(tail) - m.start()
    if (m.group(1), m.group(2)) != (m.group(3), m.group(4)): return dict(path=path, status='RECORDS-DISTINTOS', size=size)
    if size != b + tail_len: return dict(path=path, status='TAMANO-INCOHERENTE', size=size, bytes=b, tail=tail_len)
    return dict(path=path, status='CON-COLA', size=size, bytes=b, tail=tail_len)


def sha256(path, limit=None):
    h = hashlib.sha256(); left = limit
    with open(path, 'rb') as f:
        while True:
            n = 1 << 24 if left is None else min(1 << 24, left)
            if n == 0: break
            b = f.read(n)
            if not b: break
            h.update(b)
            if left is not None: left -= len(b)
    return h.hexdigest()


def files(args):
    for a in args:
        if os.path.isdir(a):
            for n in sorted(os.listdir(a)):
                if n.endswith('.img'): yield os.path.join(a, n)
        else: yield a


def main(argv):
    apply = '--apply' in argv; args = [a for a in argv[1:] if a != '--apply']
    if not args: print(__doc__); return 2
    bad = 0
    for p in files(args):
        r = analyse(p)
        print('%-20s %s' % (r['status'], p) + ('  tamaño %(size)d -> %(bytes)d (cola %(tail)d bytes)' % r if 'bytes' in r and 'tail' in r else ''))
        if r['status'] != 'CON-COLA':
            bad += r['status'] != 'SIN-COLA'; continue
        if apply:
            with open(p, 'r+b') as f: f.truncate(r['bytes'])
            h = sha256(p)
            with open(p + '.trimmed.sha256', 'x') as o: o.write('%s  %s\n' % (h, os.path.basename(p)))
            print('   recortado; sha256 %s' % h)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

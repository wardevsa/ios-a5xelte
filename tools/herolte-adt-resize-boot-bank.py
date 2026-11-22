#!/usr/bin/env python3
"""Resize the boot DRAM bank of a herolte ADT (chosen/dram-size and the first hakios-ram-banks entry).

  herolte-adt-resize-boot-bank.py IN.adt OUT.adt --mb N

Only shrinks (N MiB <= current). Everything else, including the extra banks, is kept byte for byte.
Refuses to overwrite OUT. Used for the min3 candidate (1536 MiB, KI-0009 / HEROLTE_PROGRESS 2026-10-24).
"""
import argparse, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adt  # noqa: E402


def resize(blob, mb):
    r = adt.parse(blob)
    root = r[0] if isinstance(r, tuple) else r
    chosen = next(c for c in root.children if c.name == 'chosen')
    size = mb << 20
    props = {k: i for i, (k, f, v) in enumerate(chosen.props)}
    old = struct.unpack('<Q', chosen.props[props['dram-size']][2])[0]
    if size > old or size % 0x4000:
        raise SystemExit(f'invalid size {size:#x} (current {old:#x}, 16 KiB multiple, shrink only)')
    k, f, _ = chosen.props[props['dram-size']]
    chosen.props[props['dram-size']] = (k, f, struct.pack('<Q', size))
    if 'hakios-ram-banks' in props:
        k, f, v = chosen.props[props['hakios-ram-banks']]
        base, bsize = struct.unpack_from('<QQ', v, 0)
        base_db = struct.unpack('<Q', chosen.props[props['dram-base']][2])[0]
        if (base, bsize) != (base_db, old):
            raise SystemExit('first ram bank is not the boot bank')
        chosen.props[props['hakios-ram-banks']] = (k, f, struct.pack('<QQ', base, size) + v[16:])
    return adt.serialize(root)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('src'); ap.add_argument('dst'); ap.add_argument('--mb', type=int, required=True)
    a = ap.parse_args()
    if os.path.exists(a.dst):
        raise SystemExit(f'refusing to overwrite {a.dst}')
    out = resize(open(a.src, 'rb').read(), a.mb)
    open(a.dst, 'xb').write(out)
    print(f'{a.dst}: {len(out)} bytes')

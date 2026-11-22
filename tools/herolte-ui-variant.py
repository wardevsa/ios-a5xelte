#!/usr/bin/env python3
"""Make a screen variant of the live device tree for the S7UI lab (docs/herolte-ui-lab.md).

  herolte-ui-variant.py OUT.adt --canvas WxH [--subtype N] [--scale 2|3] [--home-button 1|2] [--base ADT]

Edits only the properties the screen depends on, in the ADT that the images already use (--base, default boot-candidates/herolte-3g.adt): the canvas
(/arm-io/disp0 canvas-width/height), /product artwork-device-subtype and artwork-scale-factor, /chosen display-scale and /buttons home-button-type.
Prints what changed and the boot-line arguments that must go with it (sweetfb_lw, sweetfb_lh, sweetfb_fill). Nothing touches a phone.
"""
import argparse
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adt  # noqa: E402

BASE = Path(os.environ.get('HEROLTE_DEVICE_DAY', Path.home() / 'HackiOS/builds/device-day')) / 'boot-candidates/herolte-3g.adt'


def walk(node, path=''):
    name = node.prop('name')
    name = name.rstrip(b'\0').decode() if name else '?'
    yield path + '/' + name, node
    for c in node.children:
        yield from walk(c, path + '/' + name)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('out', type=Path)
    p.add_argument('--canvas', required=True, help='WxH of the UI canvas, e.g. 828x1792')
    p.add_argument('--subtype', type=int, help='artwork-device-subtype (pixel height of the real device: 1334 iPhone 8, 1792 XR, 2436 X)')
    p.add_argument('--scale', type=int, help='artwork-scale-factor and display-scale (2 or 3)')
    p.add_argument('--home-button', type=int, choices=(1, 2), help='1 a home button, 2 gesture navigation')
    p.add_argument('--base', type=Path, default=BASE)
    a = p.parse_args()
    cw, ch = (int(v) for v in a.canvas.lower().split('x'))
    want = {'canvas-width': cw, 'canvas-height': ch}
    if a.subtype:
        want['artwork-device-subtype'] = a.subtype
    if a.scale:
        want['artwork-scale-factor'] = a.scale
        want['display-scale'] = a.scale
    if a.home_button:
        want['home-button-type'] = a.home_button
    r = adt.parse(a.base.read_bytes())
    root = r[0] if isinstance(r, tuple) else r
    for path, node in walk(root):
        for i, (k, f, v) in enumerate(list(node.props)):
            if k in want and len(v) == 4:
                old = struct.unpack('<I', v)[0]
                node.props[i] = (k, f, struct.pack('<I', want[k]))
                print(f"{path}:{k}  {old} -> {want[k]}")
    a.out.write_bytes(adt.serialize(root))
    print(f"wrote {a.out}")
    print(f"boot line: sweetfb_lw={cw} sweetfb_lh={ch}" + ("" if cw * 16 == ch * 9 else "   (not 16:9: add sweetfb_fill=1 to stretch it over the panel)"))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Rebuild the phone's own screenshots (kernel patch 0484, boot-arg hsnap=<s>) from a pulled herolog.

  herolte-snap-decode.py LOG OUTDIR [--scale N]

Each snapshot is 288x512 RGB565 little-endian, one base64 line per row ("HEROLTE SNAP <id> <row> <base64>") after a header line
("HEROLTE SNAP <id> <tag> 288x512 rgb565 le at <pa>"). Writes OUTDIR/<id>-<tag>.png and OUTDIR/contact-sheet.png with all of them side by side.
Lines can be glued to other log text (the log is a ring written by several threads): the row lines are found by their pattern anywhere in a line.
"""
import base64
import re
import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw

W, H = 288, 512
HEADER = re.compile(r"HEROLTE SNAP (\d+) (\S+) 288x512 rgb565 le")
ROW = re.compile(r"HEROLTE SNAP (\d+) (\d+) ([A-Za-z0-9+/=]{760,780})")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    scale = 1
    if '--scale' in sys.argv:
        scale = int(sys.argv[sys.argv.index('--scale') + 1])
        args = [a for a in args if a != str(scale)]
    log, out = Path(args[0]), Path(args[1])
    out.mkdir(parents=True, exist_ok=True)
    tags, rows = {}, {}
    for line in log.read_text(errors='replace').splitlines():
        m = HEADER.search(line)
        if m:
            tags[int(m.group(1))] = m.group(2)
        for r in ROW.finditer(line):
            data = base64.b64decode(r.group(3))
            if len(data) == W * 2:
                rows.setdefault(int(r.group(1)), {})[int(r.group(2))] = data
    shots = []
    for sid in sorted(rows):
        img = Image.new('RGB', (W, H), (255, 0, 255))      # magenta = a row that never reached the log
        px = img.load()
        got = 0
        for y, data in rows[sid].items():
            if y >= H:
                continue
            got += 1
            for x in range(W):
                v = struct.unpack_from('<H', data, x * 2)[0]
                px[x, y] = (((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31)
        name = f"{sid:02d}-{tags.get(sid, 'snap')}"
        if scale > 1:
            img = img.resize((W * scale, H * scale), Image.NEAREST)
        img.save(out / f"{name}.png")
        print(f"{name}: {got} of {H} rows")
        shots.append((name, img))
    if shots:
        sw, sh = shots[0][1].size
        sheet = Image.new('RGB', (sw * len(shots) + 8 * (len(shots) - 1), sh + 14), (30, 30, 30))
        d = ImageDraw.Draw(sheet)
        for i, (name, img) in enumerate(shots):
            sheet.paste(img, (i * (sw + 8), 14))
            d.text((i * (sw + 8) + 2, 1), name[:34], fill=(255, 255, 255))
        sheet.save(out / 'contact-sheet.png')
    print(f"{len(shots)} snapshots in {out}")


if __name__ == '__main__':
    main()

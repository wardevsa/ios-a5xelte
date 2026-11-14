#!/usr/bin/env python3
"""Convert an image into the boot-splash blob that shim/herolte/xnu_boot.c draws before XNU starts.

  herolte-make-splash.py IMAGE OUT.bin [--fit contain|cover|stretch] [--bg RRGGBB] [--no-rle] [--preview OUT.png]
  herolte-make-splash.py --demo OUT.bin [--preview OUT.png]       # a plain placeholder, no input image

The panel is 1440x2560. The blob stores the image at 720x1280 (RGB565, optionally RLE) and the loader scales it x2.
Put the result at shim/herolte/splash.bin (git-ignored) and rebuild the loader; docs/herolte-splash.md has the rest.
Host-side only: it never touches a device.
"""
import argparse
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

FB_W, FB_H = 1440, 2560
IMG_W, IMG_H = 720, 1280
MAGIC = b'HSPL'


def rgb565(img):
    out = bytearray()
    for r, g, b in img.convert('RGB').getdata():
        out += struct.pack('<H', ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3))
    return bytes(out)


def rle(pix):
    """Tokens: 0x80|(n-1), value  = run of n (1..128) equal pixels; (n-1), n values = n (1..128) literals."""
    px = [pix[i:i + 2] for i in range(0, len(pix), 2)]
    out, i, n = bytearray(), 0, len(px)
    while i < n:
        j = i
        while j + 1 < n and px[j + 1] == px[i] and j + 1 - i < 127:
            j += 1
        run = j - i + 1
        if run >= 3:
            out.append(0x80 | (run - 1))
            out += px[i]
            i += run
            continue
        k = i
        while k < n and k - i < 128 and not (k + 2 < n and px[k] == px[k + 1] == px[k + 2]):
            k += 1
        k = max(k, i + 1)
        out.append(k - i - 1)
        for q in range(i, k):
            out += px[q]
        i = k
    return bytes(out)


def build_blob(img, use_rle=True):
    w, h = img.size
    pix = rgb565(img)
    payload, flags = pix, 0
    if use_rle:
        packed = rle(pix)
        if len(packed) < len(pix):
            payload, flags = packed, 1
    return MAGIC + struct.pack('<HHHHI', w, h, flags, 0, len(payload)) + payload


def decode_reference(blob, fb_w=FB_W, fb_h=FB_H):
    """Independent re-implementation of shim/herolte/splash.c; returns fb_h rows of fb_w ARGB values."""
    assert blob[:4] == MAGIC
    w, h, flags, _, plen = struct.unpack_from('<HHHHI', blob, 4)
    data = blob[16:16 + plen]
    px, p = [], 0
    if flags & 1:
        while len(px) < w * h:
            c = data[p]
            p += 1
            if c & 0x80:
                v = data[p:p + 2]
                p += 2
                px += [v] * ((c & 0x7f) + 1)
            else:
                for _ in range(c + 1):
                    px.append(data[p:p + 2])
                    p += 2
    else:
        px = [data[i:i + 2] for i in range(0, plen, 2)]

    def argb(v):
        c = v[0] | (v[1] << 8)
        r, g, b = (c >> 11) & 31, (c >> 5) & 63, c & 31
        return 0xff000000 | (((r << 3) | (r >> 2)) << 16) | (((g << 2) | (g >> 4)) << 8) | ((b << 3) | (b >> 2))

    scale = min(fb_w // w, fb_h // h)
    offx, offy = (fb_w - w * scale) // 2, (fb_h - h * scale) // 2
    rows = []
    for y in range(fb_h):
        if y < offy or y >= offy + h * scale:
            rows.append([0xff000000] * fb_w)
            continue
        sy = (y - offy) // scale
        row = [0xff000000] * offx
        for i in range(w):
            row += [argb(px[sy * w + i])] * scale
        row += [0xff000000] * (fb_w - len(row))
        rows.append(row)
    return rows


def fit(img, mode, bg):
    img = img.convert('RGB')
    if mode == 'stretch':
        return img.resize((IMG_W, IMG_H), Image.LANCZOS)
    s = (max if mode == 'cover' else min)(IMG_W / img.width, IMG_H / img.height)
    r = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
    canvas = Image.new('RGB', (IMG_W, IMG_H), bg)
    canvas.paste(r, ((IMG_W - r.width) // 2, (IMG_H - r.height) // 2))
    return canvas


def demo():
    img = Image.new('RGB', (IMG_W, IMG_H))
    d = ImageDraw.Draw(img)
    for y in range(IMG_H):                     # dark vertical gradient
        t = y / IMG_H
        d.line([(0, y), (IMG_W, y)], fill=(int(10 + 20 * t), int(12 + 30 * t), int(24 + 70 * t)))
    d.rounded_rectangle([IMG_W // 2 - 150, IMG_H // 2 - 150, IMG_W // 2 + 150, IMG_H // 2 + 150], 70, outline=(230, 230, 240), width=10)
    d.ellipse([IMG_W // 2 - 40, IMG_H // 2 - 40, IMG_W // 2 + 40, IMG_H // 2 + 40], fill=(230, 230, 240))
    try:
        font = ImageFont.load_default(size=42)
    except TypeError:
        font = ImageFont.load_default()
    for text, dy in (('iOS on Galaxy S7', 230), ('HEROLTE', 290)):
        w = d.textlength(text, font=font)
        d.text(((IMG_W - w) / 2, IMG_H // 2 + dy), text, fill=(200, 205, 225), font=font)
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('image', nargs='?')
    ap.add_argument('out')
    ap.add_argument('--demo', action='store_true')
    ap.add_argument('--fit', choices=('contain', 'cover', 'stretch'), default='contain')
    ap.add_argument('--bg', default='000000')
    ap.add_argument('--no-rle', action='store_true')
    ap.add_argument('--preview')
    a = ap.parse_args()
    if a.demo:
        if a.image:                 # "--demo OUT.bin": the single positional is the output
            a.out, a.image = a.image, None
        img = demo()
    else:
        if not a.image:
            ap.error('give an IMAGE or --demo')
        bg = tuple(int(a.bg[i:i + 2], 16) for i in (0, 2, 4))
        img = fit(Image.open(a.image), a.fit, bg)
    blob = build_blob(img, not a.no_rle)
    with open(a.out, 'wb') as f:
        f.write(blob)
    print(f'{a.out}: {len(blob)} bytes ({"RLE" if blob[8] & 1 else "raw"}), {IMG_W}x{IMG_H} RGB565, drawn x2 on {FB_W}x{FB_H}')
    if a.preview:
        rows = decode_reference(blob)
        out = Image.new('RGB', (FB_W, FB_H))
        out.putdata([((v >> 16) & 255, (v >> 8) & 255, v & 255) for row in rows for v in row])
        out.save(a.preview)
        print(f'preview (decoded as the loader will): {a.preview}')


if __name__ == '__main__':
    sys.exit(main())

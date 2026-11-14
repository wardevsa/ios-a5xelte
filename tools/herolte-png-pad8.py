"""Pad PNGs to a width that is a multiple of 8 pixels by repeating the last column.

CoreAnimation lays images out with rows rounded to 32 bytes; a decoded PNG with tight rows (1105 px = 4420 bytes)
was read with 4448-byte rows past the end of its buffer (backboardd SIGSEGV, boot-walls). Non-interlaced 8-bit
RGB/RGBA/gray/gray+alpha PNGs only; others are copied unchanged.

    herolte-png-pad8.py IN_DIR OUT_DIR       (every file but 'list'; 'list' is copied)
    herolte-png-pad8.py --file IN OUT        (one file)
"""
import os
import shutil
import struct
import sys
import zlib

CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}


def chunks(data):
    at = 8
    while at < len(data):
        n, kind = struct.unpack('>I4s', data[at:at + 8])
        yield kind, data[at + 8:at + 8 + n]
        at += 12 + n


def paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else (b if pb <= pc else c)


def unfilter(raw, width, height, bpp):
    stride = width * bpp
    out = bytearray(stride * height)
    prev = bytearray(stride)
    at = 0
    for y in range(height):
        ftype = raw[at]
        line = bytearray(raw[at + 1:at + 1 + stride])
        at += 1 + stride
        if ftype == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif ftype == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif ftype == 4:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                up_left = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + paeth(left, prev[i], up_left)) & 255
        elif ftype != 0:
            raise ValueError(f'filter {ftype}')
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return out


def chunk(kind, body):
    return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)


def pad(path_in, path_out):
    data = open(path_in, 'rb').read()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        shutil.copyfile(path_in, path_out)
        return 'not PNG, copied'
    ihdr = None
    idat = []
    keep = []
    for kind, body in chunks(data):
        if kind == b'IHDR':
            ihdr = body
        elif kind == b'IDAT':
            idat.append(body)
        elif kind in (b'iCCP', b'sRGB', b'gAMA', b'cHRM', b'pHYs'):
            keep.append((kind, body))
    width, height, depth, ctype, _, _, interlace = struct.unpack('>IIBBBBB', ihdr)
    if depth != 8 or interlace or ctype not in CHANNELS:
        shutil.copyfile(path_in, path_out)
        return f'depth {depth} type {ctype} interlace {interlace}: copied'
    new_w = (width + 7) & ~7
    if new_w == width:
        shutil.copyfile(path_in, path_out)
        return f'{width}x{height}: already a multiple of 8'
    bpp = CHANNELS[ctype]
    pixels = unfilter(zlib.decompress(b''.join(idat)), width, height, bpp)
    stride, new_stride = width * bpp, new_w * bpp
    rows = bytearray()
    for y in range(height):
        line = pixels[y * stride:(y + 1) * stride]
        last = line[-bpp:]
        rows += b'\0' + line + last * (new_w - width)
    out = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', new_w, height, 8, ctype, 0, 0, 0))
    for kind, body in keep:
        out += chunk(kind, body)
    out += chunk(b'IDAT', zlib.compress(bytes(rows), 6)) + chunk(b'IEND', b'')
    open(path_out, 'wb').write(out)
    return f'{width}x{height} -> {new_w}x{height} ({len(data)} -> {len(out)} bytes)'


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--file':
        print(pad(sys.argv[2], sys.argv[3]))
        return
    src, dst = sys.argv[1], sys.argv[2]
    os.makedirs(dst, exist_ok=True)
    for name in sorted(os.listdir(src), key=lambda n: (not n.isdigit(), int(n) if n.isdigit() else 0, n)):
        a, b = os.path.join(src, name), os.path.join(dst, name)
        if name == 'list' or not os.path.isfile(a):
            if os.path.isfile(a):
                shutil.copyfile(a, b)
            continue
        print(name, pad(a, b), flush=True)


main()

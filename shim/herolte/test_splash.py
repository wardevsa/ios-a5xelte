#!/usr/bin/env python3
"""Prueba en el PC del decodificador del cargador (splash.c) contra la referencia de tools/herolte-make-splash.py.

  python3 shim/herolte/test_splash.py        # compila splash.c con gcc (ASan+UBSan) en un directorio temporal
"""
import ctypes as C
import importlib.util
import os
import random
import struct
import subprocess
import sys
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('mk', os.path.join(HERE, '..', '..', 'tools', 'herolte-make-splash.py'))
mk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mk)

so = os.path.join(tempfile.mkdtemp(prefix='splash-'), 'libsplash.so')
subprocess.check_call(['gcc', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined',
                       '-fno-sanitize-recover=undefined', '-shared', '-fPIC', os.path.join(HERE, 'splash.c'), '-o', so])
lib = C.CDLL(so)
lib.hero_splash_blit.restype = C.c_int
lib.hero_splash_blit.argtypes = [C.c_void_p, C.c_uint, C.c_uint, C.c_char_p, C.c_size_t]

bad = 0


def check(name, ok):
    global bad
    print(f'  [{"OK" if ok else "FALLA"}] {name}')
    bad += not ok


def blit(blob, fb_w, fb_h):
    buf = (C.c_uint32 * (fb_w * fb_h))()
    rc = lib.hero_splash_blit(C.byref(buf), fb_w, fb_h, blob, len(blob))
    return rc, list(buf)


rng = random.Random(7)


def noise(w, h):
    img = Image.new('RGB', (w, h))
    img.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(w * h)])
    return img


def flat(w, h):
    img = Image.new('RGB', (w, h), (10, 120, 250))
    for x in range(0, w, 5):
        for y in range(h // 3):
            img.putpixel((x, y), (250, 20, 20))
    return img


cases = [('ruido 16x24 en 48x72 (x3, sin márgenes)', noise(16, 24), 48, 72, True),
         ('ruido sin RLE', noise(16, 24), 48, 72, False),
         ('zonas planas (RLE) 40x30 en 90x70 (x2, márgenes)', flat(40, 30), 90, 70, True),
         ('imagen del mismo tamaño que la pantalla (x1)', noise(20, 20), 20, 20, True),
         ('ancho limita la escala', noise(30, 10), 70, 100, True)]
print('Decodificador C frente a la referencia de Python')
for name, img, fw, fh, use_rle in cases:
    blob = mk.build_blob(img, use_rle)
    rc, got = blit(blob, fw, fh)
    want = [v for row in mk.decode_reference(blob, fw, fh) for v in row]
    check(f'{name}: rc={rc}, {"RLE" if blob[8] & 1 else "raw"}', rc == 0 and got == want)
print('Blobs inválidos')
good = mk.build_blob(noise(8, 8), False)
check('magic incorrecta', blit(b'XXXX' + good[4:], 40, 40)[0] == -1)
check('cabecera truncada', blit(good[:10], 40, 40)[0] == -1)
check('imagen mayor que la pantalla', blit(good, 4, 4)[0] == -2)
check('flags desconocidas', blit(good[:8] + struct.pack('<H', 2) + good[10:], 40, 40)[0] == -2)
check('tamaño de payload imposible', blit(good[:12] + struct.pack('<I', 0xffffffff) + good[16:], 40, 40)[0] == -2)
check('raw con longitud que no cuadra', blit(good[:12] + struct.pack('<I', 8) + good[16:24], 40, 40)[0] == -3)
rle_blob = mk.build_blob(flat(40, 30), True)
check('RLE truncado se detecta (sin leer fuera del blob)', blit(rle_blob[:30], 90, 70)[0] in (-2, -4))
trunc = rle_blob[:16] + rle_blob[16:60]
trunc = trunc[:12] + struct.pack('<I', len(trunc) - 16) + trunc[16:]
check('RLE con payload corto: -4', blit(trunc, 90, 70)[0] == -4)
print('\n' + ('FALLAN' if bad else 'todo correcto'))
sys.exit(1 if bad else 0)

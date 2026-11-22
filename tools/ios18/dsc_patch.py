#!/usr/bin/env python3
"""dsc_patch.py: fixed-word patches of the iOS 26 dyld shared cache (23G90, iPhone12,1), page hashes updated.

  dsc_patch.py [--check] CACHE_FILE [CACHE_FILE ...]      (the main file and its .01, .02 ... sub-caches)

Each patch names the image it must fall in and the word that must be there; anything else and nothing is written
for that patch (a different build or device lays the cache out differently: the addresses are this cache's).

  push_surface   QuartzCore CA::OGL::Context::push_surface asserts "found != slist->end ()" (ogl-context.cpp 0x4a2)
                 when a surface was made without Context::track_surface(): iOS 26 left such paths in that nothing of
                 Apple's runs any more (software / GLES renderers). backboardd aborted there under the CPU renderer
                 (AsynchronousNode::retain_surface, boots 26k4-26k6). As malthiscode/ios-b1lte B1L-0042: the not-found
                 branch (cbnz x8, +0x3c) becomes an unconditional b +0x3c, the untracked surface is simply pushed.
Run after pacstrip_cache.py / v80strip_cache.py (they do not touch these words) and before fips_rehmac.py.
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v80strip_cache as vc  # noqa: E402

# (unslid address, image basename, expected word, new word, name)
PATCHES = [
    (0x183f0f1e4, 'QuartzCore', 0xb50001e8, 0x1400000f, 'push_surface'),
]


def image_at(cache, addr):
    for base, path in cache.images:
        segs, sects = cache.macho(base)
        for name, va, size in segs:
            if name == b'__TEXT' and va <= addr < va + size:
                return path.rsplit('/', 1)[-1]
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('files', nargs='+')
    ap.add_argument('--check', action='store_true', help='report only, write nothing')
    a = ap.parse_args()
    cache = vc.Cache([f for f in a.files if not f.endswith(('.symbols', '.atlas', '.map'))], not a.check)
    changed, bad = {}, 0
    for addr, image, old, new, name in PATCHES:
        w = cache.where(addr, 4)
        img = image_at(cache, addr)
        if w is None or img != image:
            print(f'{name}: {addr:#x} is in {img}, not {image}: skipped')
            bad += 1
            continue
        buf, off = cache.bufs[w[0]], w[1]
        cur = struct.unpack_from('<I', buf, off)[0]
        if cur == new:
            print(f'{name}: already patched')
            continue
        if cur != old:
            print(f'{name}: {addr:#x} holds {cur:#010x}, not {old:#010x}: skipped')
            bad += 1
            continue
        if not a.check:
            struct.pack_into('<I', buf, off, new)
            changed.setdefault(w[0], set()).add(off >> 12)
        print(f'{name}: {addr:#x} {old:#010x} -> {new:#010x} ({image})')
    for p, pages in changed.items():
        n = vc.fix_signature(cache.bufs[p], pages)
        cache.bufs[p].flush()
        print(f'  {os.path.basename(p)}: {len(pages)} pages changed, {n} hashes updated')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()

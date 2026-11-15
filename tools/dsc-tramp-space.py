#!/usr/bin/env python3
"""Where could out-of-line code for the S7 (ARMv8.0) live in an iOS 18 dyld shared cache?

  dsc-tramp-space.py CACHE_FILE [CACHE_FILE ...]      (the main file and its .01, .02 ... subcaches)

An LSE atomic (CAS, LDADD, SWP ...) does not fit in 4 bytes of ARMv8.0 code: it becomes a B to a
per-site routine (LDAXR/STLXR loop, then B back), which must lie within +-128 MiB of the site, in an
executable mapping. Candidates: the bytes between the end of an image's last __TEXT section and the start
of the next image's __TEXT (alignment padding, inside the r-x mapping and covered by the code signature).

Printed (numbers only, nothing of the cache leaves the machine):
  - the mappings of every file, and the address gaps between them
  - the padding: count, total, how much of it is all zero, size histogram
  - LSE sites by form (what the routines must implement), and odd operands (Rn = SP, Rt = Rs ...)
  - a greedy placement of one routine per site (earliest feasible pad, +-120 MiB): how many fit
  - other instructions ARMv8.0 lacks besides LSE/RCpc/PAC (FP16, RDM, FCMA, JSCVT, dot product, SHA3/SHA512)
  - RCpc: LDAPR (LDAR equivalent, 4 for 4) vs LDAPUR/STLUR with a non-zero offset (not 4 for 4)
"""
import os, struct, sys
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util
_spec = importlib.util.spec_from_file_location('scan', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dsc-lse-scan.py'))
scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan)

RANGE = 120 << 20
TRAMP = int(os.environ.get('TRAMP_BYTES', '64'))       # bytes per routine (estimate)


def text_segment(cache, address):
    """(segment start, segment end, end of the last section) of an image's __TEXT; None if unreadable."""
    head = cache.read(address, 32)
    if not head or struct.unpack_from('<I', head, 0)[0] != 0xFEEDFACF:
        return None
    ncmds, sizeofcmds = struct.unpack_from('<II', head, 16)
    cmds = cache.read(address + 32, sizeofcmds) or b''
    off = 0
    for _ in range(ncmds):
        if off + 8 > len(cmds):
            break
        cmd, size = struct.unpack_from('<II', cmds, off)
        if cmd == 0x19 and cmds[off + 8:off + 24].split(b'\0')[0] == b'__TEXT':
            vmaddr, vmsize = struct.unpack_from('<QQ', cmds, off + 24)
            nsects = struct.unpack_from('<I', cmds, off + 64)[0]
            last = vmaddr
            for s in range(nsects):
                so = off + 72 + s * 80
                addr, ssize = struct.unpack_from('<QQ', cmds, so + 32)
                last = max(last, addr + ssize)
            return vmaddr, vmaddr + vmsize, last
        off += size
    return None


def lse_form(w):
    """A name for the routine an LSE word needs: op, size, ordering."""
    size = 8 << (w >> 30)
    a, r = (w >> 23) & 1, (w >> 22) & 1
    if (w & 0x3FA07C00) == 0x08A07C00:                     # CAS: L = bit 22, o0 = bit 15
        a, r = (w >> 22) & 1, (w >> 15) & 1
        return f'cas{size}{"a" if a else ""}{"l" if r else ""}'
    if (w & 0xBFA07C00) == 0x08207C00:
        a, r = (w >> 22) & 1, (w >> 15) & 1
        return f'casp{64 if (w >> 30) & 1 else 32}{"a" if a else ""}{"l" if r else ""}'
    o3, opc = (w >> 15) & 1, (w >> 12) & 7
    rt = w & 31
    if o3:
        name = 'swp'
    else:
        name = ('add', 'clr', 'eor', 'set', 'smax', 'smin', 'umax', 'umin')[opc]
        name = ('st' if rt == 31 and not a else 'ld') + name
    return f'{name}{size}{"a" if a else ""}{"l" if r else ""}'


def odd_operands(w):
    rt, rn, rs = w & 31, (w >> 5) & 31, (w >> 16) & 31
    out = []
    if rn == 31:
        out.append('Rn=SP')
    if rt == rs and rt != 31:
        out.append('Rt=Rs')
    if rt == rn or rs == rn:
        out.append('Rn=Rt/Rs')
    return out


def extra_classes(w):
    """Counts of ARMv8.1+ classes other than LSE/RCpc/PAC, on a numpy word array."""
    out = {}
    out['fjcvtzs'] = (w & 0xFFFFFC00) == 0x1E7E0000
    out['rdm'] = (((w & 0xBF20F400) == 0x2E008400) | ((w & 0xFF20F400) == 0x7E008400) |
                  ((w & 0xBF00D400) == 0x2F00D000) | ((w & 0xFF00D400) == 0x7F00D000))
    out['fcma'] = ((w & 0xBF20E400) == 0x2E00C400) | ((w & 0xBF20EC00) == 0x2E00E400) | ((w & 0xBF009400) == 0x2F001000)
    out['dotprod'] = (((w & 0xBFE0FC00) == 0x0E809400) | ((w & 0xBFE0FC00) == 0x2E809400) |
                      ((w & 0xBFC0F400) == 0x0F80E000) | ((w & 0xBFC0F400) == 0x2F80E000))
    # FP16 data processing: scalar ftype=11 (minus FCVT from half, which ARMv8.0 has), vector three-same FP16
    scal = (w & 0xFF200000) == 0x1EE00000
    fcvt_from_h = (w & 0xFFFE7C00) == 0x1EE24000      # FCVT Sd/Dd, Hn (opc 00/01 in 1-source, bits 20-15 0001 0x)
    out['fp16'] = (scal & ~fcvt_from_h) | ((w & 0x9F60C400) == 0x0E400400) | ((w & 0xBFFE0C00) == 0x0EF80800)
    out['sha3_sha512'] = ((w & 0xFFE08000) == 0xCE000000) | ((w & 0xFFE08000) == 0xCE200000) | \
                         ((w & 0xFFE0B000) == 0xCE608000) | ((w & 0xFFFFF000) == 0xCEC08000)
    out['rcpc_offset'] = ((w & 0x3F600C00) == 0x19400000) & (((w >> 12) & 0x1FF) != 0)
    out['rcpc_zero_offset'] = ((w & 0x3F600C00) == 0x19400000) & (((w >> 12) & 0x1FF) == 0)
    out['ldapr'] = (w & 0x3FFFFC00) == 0x38BFC000
    return out


def lse_mask(w):
    ldapr = (w & 0x3FFFFC00) == 0x38BFC000
    cas = (w & 0x3FA07C00) == 0x08A07C00
    casp = (w & 0xBFA07C00) == 0x08207C00
    ldop = ((w & 0x3F208C00) == 0x38200000) | ((w & 0x3F208C00) == 0x38208000)
    return (cas | casp | ldop) & ~ldapr


def main():
    cache = scan.Cache(sys.argv[1:])
    print(f'{len(cache.files)} files, {len(cache.maps)} mappings, {len(cache.images)} images')
    print('mappings (address, size, file):')
    maps = sorted(cache.maps)
    for i, (a, s, p, o) in enumerate(maps):
        gap = (maps[i + 1][0] - (a + s)) if i + 1 < len(maps) else 0
        print(f'  {a:#012x} {s:#011x} ({s >> 20:5} MiB) {os.path.basename(p)}  gap after {gap >> 20} MiB')

    # image __TEXT segments, sorted
    segs = []
    for address, name in cache.images:
        t = text_segment(cache, address)
        if t:
            segs.append((t[0], t[1], t[2], name))
    segs.sort()
    def map_end(addr):
        for a, s, p, o in maps:
            if a <= addr < a + s:
                return a + s
        return addr

    pads = []                                # (start, end, zero?, name): inside the image's own __TEXT segment
    gaps = []                                # the same, from the segment end to the next image (other cache data?)
    sizes = Counter()
    for i, (start, end, last, name) in enumerate(segs):
        nxt = segs[i + 1][0] if i + 1 < len(segs) and segs[i + 1][0] >= end else end
        nxt = min(nxt, map_end(last))
        lo = (last + 15) & ~15
        for out, a, b in ((pads, lo, min(end, nxt)), (gaps, max(lo, end), nxt)):
            if b > a:
                data = cache.read(a, b - a) or b''
                zero = len(data) == b - a and not any(data)
                out.append((a, b, zero, name))
                if out is pads:
                    n = b - a
                    sizes['<1K' if n < 1024 else '<4K' if n < 4096 else '<16K' if n < 16384 else '<64K' if n < 65536 else '>=64K'] += 1
    for label, lst in (('inside __TEXT segments', pads), ('between segments', gaps)):
        tot = sum(e - s for s, e, z, n in lst)
        totz = sum(e - s for s, e, z, n in lst if z)
        print(f'padding {label}: {len(lst)}, {tot >> 10} KiB, all-zero {totz >> 10} KiB in {sum(1 for p in lst if p[2])}')
    print('  sizes of the padding inside segments:', dict(sizes))

    # LSE sites, RCpc and the other classes over every image's code sections
    sites = []
    forms, odd = Counter(), Counter()
    extra = Counter()
    per_image = Counter()
    for address, name in cache.images:
        for a, s in scan.text_sections(cache, address):
            data = cache.read(a, s)
            if not data:
                continue
            w = np.frombuffer(data[:len(data) // 4 * 4], dtype='<u4')
            m = lse_mask(w)
            idx = np.nonzero(m)[0]
            for i in idx:
                word = int(w[i])
                sites.append(a + 4 * int(i))
                forms[lse_form(word)] += 1
                for o in odd_operands(word):
                    odd[o] += 1
            if len(idx):
                per_image[name.rsplit('/', 1)[-1]] += len(idx)
            for k, v in extra_classes(w).items():
                n = int(v.sum())
                if n:
                    extra[k] += n
    sites.sort()
    print(f'LSE sites: {len(sites)}')
    print('  forms:', ', '.join(f'{k}={v}' for k, v in forms.most_common()))
    print('  odd operands:', dict(odd))
    print('  most sites:', ', '.join(f'{k}={v}' for k, v in per_image.most_common(25)))
    print('other classes:', dict(extra))

    # greedy placement: sites in address order, each in the earliest zero pad with room inside +-RANGE
    def place(label, spaces, tramp):
        zp = sorted([s, e, s] for s, e, z, n in spaces if z and e - s >= tramp)     # start, end, next free
        j, placed, failed = 0, 0, 0
        far = Counter()
        for s in sites:
            while j < len(zp) and (zp[j][1] < s - RANGE or zp[j][1] - zp[j][2] < tramp):
                j += 1
            k = j
            while k < len(zp) and zp[k][1] - zp[k][2] < tramp:
                k += 1
            if k < len(zp) and zp[k][2] <= s + RANGE and zp[k][2] + tramp <= zp[k][1]:
                d = abs(zp[k][2] - s)
                far['<1M' if d < 1 << 20 else '<16M' if d < 16 << 20 else '<64M' if d < 64 << 20 else '<120M'] += 1
                zp[k][2] += tramp
                placed += 1
            else:
                failed += 1
        left = sum(e - f for s, e, f in zp)
        print(f'placement in {label}, {tramp} bytes per routine, +-{RANGE >> 20} MiB: {placed} placed, {failed} '
              f'without room; distance {dict(far)}; left {left >> 10} KiB')

    for tramp in (TRAMP, 48, 96):
        place('padding inside segments', pads, tramp)
        place('padding inside and between segments', pads + gaps, tramp)


if __name__ == '__main__':
    main()

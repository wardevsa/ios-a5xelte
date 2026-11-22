#!/usr/bin/env python3
"""Count the instructions an ARMv8.0 CPU (the S7's) lacks in a dyld shared cache.

  dsc-lse-scan.py CACHE_FILE [CACHE_FILE ...]      (the main file and its .01, .02 ... subcaches)

Every executable mapping (dyld_cache_mapping_info with VM_PROT_EXECUTE in initProt) is read as
32-bit words and each word is classified. Printed: totals per class, and the share of all
instructions. Only counts are printed: nothing of the cache leaves the machine.

Classes (ARM ARM encodings):
  cas      CAS/CASA/CASL/CASAL, all sizes              (size 001000 1 L 1 Rs o0 11111 Rn Rt)
  casp     CASP/CASPA/CASPL/CASPAL                     (0 sz 001000 0 L 1 Rs o0 11111 Rn Rt)
  ldop     LDADD/LDCLR/LDEOR/LDSET/LDSMAX.../LDUMIN and their ST* aliases (atomic memory ops)
  swp      SWP/SWPA/SWPL/SWPAL
  ldapr    LDAPR (RCpc, ARMv8.3) and LDAPUR (RCpc immediate, ARMv8.4)
  pac_hint PACIASP/AUTIASP/PACIBSP/AUTIBSP... in the HINT space: NOPs on ARMv8.0, nothing to do
  pac_op   RETAA/RETAB, BRAA/BLRAA/BRAAZ..., ERETAA, LDRAA/LDRAB, PACIA/AUTIA... (register forms),
           XPACI/XPACD, PACGA: undefined on ARMv8.0, each must be rewritten or emulated
"""
import struct, sys
from collections import Counter


def classify(w):
    if (w & 0x3FA07C00) == 0x08A07C00:
        return 'cas'
    if (w & 0xBFA07C00) == 0x08207C00:
        return 'casp'
    if (w & 0x3FFFFC00) == 0x38BFC000:              # LDAPR (o3 1, opc 100, Rs 11111): before the LD<op> test
        return 'ldapr'
    if (w & 0x3F208C00) == 0x38208000 and ((w >> 12) & 7) == 0:
        return 'swp'
    if (w & 0x3F208C00) == 0x38200000:
        return 'ldop'
    if (w & 0x3F600C00) == 0x19400000:              # LDAPUR*/STLUR (RCpc immediate)
        return 'ldapr'
    # HINT-space PAC: PACIAZ/PACIASP/PACIBZ/PACIBSP/AUTIAZ/AUTIASP/AUTIBZ/AUTIBSP, PACIA1716 ..., XPACLRI
    if (w & 0xFFFFF01F) == 0xD503201F and ((w >> 5) & 0x7F) in (0x08, 0x0A, 0x0C, 0x0E, 0x18, 0x19, 0x1A, 0x1B,
                                                                0x1C, 0x1D, 0x1E, 0x1F, 0x07):
        return 'pac_hint'
    if w in (0xD65F0BFF, 0xD65F0FFF):                # RETAA, RETAB
        return 'pac_op'
    if (w & 0xFE9FF000) == 0xD61F0800:               # BRAA/BRAB/BLRAA/BLRAB/BRAAZ/BRABZ/BLRAAZ/BLRABZ
        return 'pac_op'
    if (w & 0xFF200400) == 0xF8200400:               # LDRAA/LDRAB
        return 'pac_op'
    if (w & 0xFFFFC000) == 0xDAC10000:               # PACIA/PACIB/PACDA/PACDB/AUTIA/... (register), XPACI/XPACD
        return 'pac_op'
    if (w & 0xFFE0FC00) == 0x9AC03000:               # PACGA
        return 'pac_op'
    return None


class Cache:
    """All files of a split cache: address -> (file, offset), and the image list of the main file."""

    def __init__(self, paths):
        self.maps = []          # (address, size, path, file_offset)
        self.images = []        # (address, path string)
        self.files = {p: open(p, 'rb') for p in paths}
        for p, f in self.files.items():
            head = f.read(0x200)
            if not head.startswith(b'dyld_v1'):
                continue
            mapping_off, mapping_count = struct.unpack_from('<II', head, 0x10)
            for i in range(mapping_count):
                f.seek(mapping_off + i * 32)
                address, size, file_off, _, _ = struct.unpack('<QQQII', f.read(32))
                self.maps.append((address, size, p, file_off))
            img_off, img_count = struct.unpack_from('<II', head, 0x18)
            if img_count == 0 and len(head) >= 0x1c8:
                img_off, img_count = struct.unpack_from('<II', head, 0x1c0)
            if img_count and not self.images:
                for i in range(img_count):
                    f.seek(img_off + i * 32)
                    address, _, _, path_off, _ = struct.unpack('<QQQII', f.read(32))
                    f.seek(path_off)
                    name = f.read(256).split(b'\0')[0].decode(errors='replace')
                    self.images.append((address, name))

    def read(self, address, size):
        for a, s, p, o in self.maps:
            if a <= address < a + s:
                f = self.files[p]
                f.seek(o + (address - a))
                return f.read(min(size, a + s - address))
        return None


def text_sections(cache, address):
    """(address, size) of the __TEXT,__text section of the image at address."""
    head = cache.read(address, 32)
    if not head or struct.unpack_from('<I', head, 0)[0] != 0xFEEDFACF:
        return []
    ncmds, sizeofcmds = struct.unpack_from('<II', head, 16)
    cmds = cache.read(address + 32, sizeofcmds) or b''
    out, off = [], 0
    for _ in range(ncmds):
        if off + 8 > len(cmds):
            break
        cmd, size = struct.unpack_from('<II', cmds, off)
        if cmd == 0x19:                                 # LC_SEGMENT_64
            nsects = struct.unpack_from('<I', cmds, off + 64)[0]
            for s in range(nsects):
                so = off + 72 + s * 80
                sect = cmds[so:so + 16].split(b'\0')[0]
                seg = cmds[so + 16:so + 32].split(b'\0')[0]
                addr, ssize = struct.unpack_from('<QQ', cmds, so + 32)
                if seg == b'__TEXT' and sect in (b'__text', b'__auth_stubs', b'__stubs'):
                    out.append((addr, ssize))
        off += size
    return out


def classify_np(w, counts):
    """The same classes as classify(), on a numpy array of words (the scan of a whole cache in seconds)."""
    import numpy as np
    ldapr = (w & 0x3FFFFC00) == 0x38BFC000
    ldapur = (w & 0x3F600C00) == 0x19400000
    swp = ((w & 0x3F208C00) == 0x38208000) & (((w >> 12) & 7) == 0)
    ldop = ((w & 0x3F208C00) == 0x38200000) | (((w & 0x3F208C00) == 0x38208000) & (((w >> 12) & 7) != 0) & ~ldapr)
    ldop &= ~ldapr & ~swp
    cas = (w & 0x3FA07C00) == 0x08A07C00
    casp = (w & 0xBFA07C00) == 0x08207C00
    imm = (w >> 5) & 0x7F
    hint = ((w & 0xFFFFF01F) == 0xD503201F) & np.isin(imm, (0x08, 0x0A, 0x0C, 0x0E, 0x18, 0x19, 0x1A, 0x1B,
                                                          0x1C, 0x1D, 0x1E, 0x1F, 0x07))
    pac = ((w == 0xD65F0BFF) | (w == 0xD65F0FFF) | ((w & 0xFE9FF800) == 0xD61F0800) | ((w & 0xFF200400) == 0xF8200400) |
           ((w & 0xFFFFC000) == 0xDAC10000) | ((w & 0xFFE0FC00) == 0x9AC03000))
    for name, m in (('cas', cas), ('casp', casp), ('ldop', ldop), ('swp', swp), ('ldapr', ldapr | ldapur),
                    ('pac_hint', hint), ('pac_op', pac)):
        counts[name] += int(m.sum())


def scan_range(cache, address, size, counts):
    import numpy as np
    words = 0
    while size > 0:
        chunk = cache.read(address, min(size, 64 << 20))
        if not chunk:
            break
        n = len(chunk) // 4
        words += n
        classify_np(np.frombuffer(chunk[:n * 4], dtype='<u4'), counts)
        address += len(chunk)
        size -= len(chunk)
    return words


HOT = ('libobjc.A.dylib', 'libsystem_platform.dylib', 'libsystem_malloc.dylib', 'libsystem_pthread.dylib',
       'libdispatch.dylib', 'libsystem_kernel.dylib', 'CoreFoundation', 'Foundation', 'QuartzCore', 'UIKitCore',
       'libswiftCore.dylib', 'libc++.1.dylib')


def main():
    cache = Cache(sys.argv[1:])
    print(f'{len(cache.files)} files, {len(cache.maps)} mappings, {len(cache.images)} images')
    counts = Counter()
    total = 0
    for address, name in cache.images:
        mine = Counter()
        words = sum(scan_range(cache, a, s, mine) for a, s in text_sections(cache, address))
        total += words
        counts.update(mine)
        base = name.rsplit('/', 1)[-1]
        if base in HOT:
            lse = mine['cas'] + mine['casp'] + mine['ldop'] + mine['swp']
            print(f'  {base:28} {words:9} words: LSE {lse:6} (cas {mine["cas"]}, ldop {mine["ldop"]}, swp {mine["swp"]}, '
                  f'casp {mine["casp"]}), RCpc {mine["ldapr"]}, PAC ops {mine["pac_op"]}, PAC hints {mine["pac_hint"]}')
    print(f'total instruction words in __text: {total}')
    for c in ('cas', 'casp', 'ldop', 'swp', 'ldapr', 'pac_hint', 'pac_op'):
        print(f'{c:9} {counts[c]:10}  ({counts[c] * 1e6 / max(total, 1):8.1f} per million)')
    lse = counts['cas'] + counts['casp'] + counts['ldop'] + counts['swp']
    print(f'LSE total {lse}, RCpc {counts["ldapr"]}, PAC needing rewrite {counts["pac_op"]}')


if __name__ == '__main__':
    main()

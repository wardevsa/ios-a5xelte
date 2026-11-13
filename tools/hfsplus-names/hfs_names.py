"""Names on an HFS+ volume as XNU stores them, and as Linux's hfsplus module would write them. ANALYSIS AND PROPOSAL ONLY: not wired into any
root-generation script.

xnu_nfd(s)     what XNU's HFS stores for a name: Unicode 3.2 canonical decomposition, NOT applied to U+2000-2FFF, U+F900-FAFF, U+2F800-2FAFF
               (TN1150; the same rule the tables of XNU's vfs_utfconv.c encode), with canonical ordering of combining marks. Differential-tested
               against XNU's own code (tools/hfsplus-names/test_hfs_names.py, every BMP character and 3000 random strings).
linux_table(ko) the decomposition table of a Linux hfsplus.ko, found by structure and validated on known decompositions.
linux_nfd(s,t) what Linux's hfsplus (default mount, no 'nodecompose') writes for a name: per-character table lookup, Hangul arithmetic, no reordering.
"""
import io, struct, subprocess, unicodedata

U32 = unicodedata.ucd_3_2_0
EXCLUDED = ((0x2000, 0x2FFF), (0xF900, 0xFAFF), (0x2F800, 0x2FAFF))


def _excluded(cp): return any(a <= cp <= b for a, b in EXCLUDED)


def xnu_nfd(s):
    out, run = [], []
    for ch in s:
        if _excluded(ord(ch)):                       # kept as is; a starter, so it also bounds the reordering of marks
            if run: out.append(U32.normalize('NFD', ''.join(run))); run = []
            out.append(ch)
        else:
            run.append(ch)
    if run: out.append(U32.normalize('NFD', ''.join(run)))
    return ''.join(out)


def linux_table(ko_path):
    """Return the u16 table of fs/hfsplus/tables.c from a (possibly .zst) module. Located by structure, checked on e-acute, A-grave, u-diaeresis."""
    raw = open(ko_path, 'rb').read()
    if ko_path.endswith('.zst'):
        raw = subprocess.run(['zstd', '-dc'], input=raw, capture_output=True, check=True).stdout
    def look(t, uc):
        def g(i): return t[i] if 0 <= i < len(t) else None
        off = g((uc >> 12) & 0xf)
        if not off or off == 0xffff: return None
        for sh in (8, 4, 0):
            off = g(off + ((uc >> sh) & 0xf))
            if not off: return None
        size = off & 3
        return tuple(t[off // 4:off // 4 + size]) if size else None
    for align in (0, 1):
        arr = struct.unpack_from('<%dH' % ((len(raw) - align) // 2), raw, align)
        for p in range(len(arr) - 64):
            if arr[p] != 0 and not 16 <= arr[p] < 4096: continue
            t = arr[p:p + 20000]
            if look(t, 0xE9) == (0x65, 0x301) and look(t, 0xC0) == (0x41, 0x300) and look(t, 0xFC) == (0x75, 0x308):
                return list(t)
    raise RuntimeError('hfsplus decompose table not found in %s' % ko_path)


def linux_decomp(table, uc):
    if 0xAC00 <= uc <= 0xD7A3:
        s = uc - 0xAC00; l, v, t = 0x1100 + s // 588, 0x1161 + (s % 588) // 28, 0x11A7 + s % 28
        return [l, v] + ([t] if s % 28 else [])
    g = lambda i: table[i] if 0 <= i < len(table) else 0
    off = g((uc >> 12) & 0xf)
    if not off or off == 0xffff: return [uc]
    for sh in (8, 4):
        off = g(off + ((uc >> sh) & 0xf))
        if not off: return [uc]
    off = g(off + (uc & 0xf)); size = off & 3
    return list(table[off // 4:off // 4 + size]) if size else [uc]


def linux_nfd(s, table): return ''.join(chr(c) for ch in s for c in linux_decomp(table, ord(ch)))


def hfs_component(name, nodecompose_available=True):
    """PROPOSED correction, not applied anywhere: the byte-exact name XNU expects for a source name (':' in a POSIX name is '/' on HFS+).
    It must be written with the volume mounted 'nodecompose' (Linux then stores it verbatim); with Linux's default mount the result would be
    decomposed again by Linux's table and (for 144 BMP characters) differ."""
    if not nodecompose_available: raise ValueError('only valid with nodecompose')
    return xnu_nfd(name.replace(':', '/'))


def find_collisions(names):
    """Names of one directory that become equal after hfs_component() (HFSX compares the UTF-16 units exactly)."""
    seen, dup = {}, []
    for n in names:
        k = hfs_component(n)
        if k in seen and seen[k] != n: dup.append((seen[k], n))
        seen.setdefault(k, n)
    return dup


def too_long(name): return len(hfs_component(name).encode('utf-16-le')) // 2 > 255

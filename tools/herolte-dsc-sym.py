#!/usr/bin/env python3
"""Symbolize unslid addresses against a split iOS 16 dyld shared cache (local analysis only).

  dscsym.py DSC_DIR build            index -> DSC_DIR/symindex.bin
  dscsym.py DSC_DIR ADDR [ADDR ...]  image + symbol + offset
"""
import bisect, glob, mmap, os, pickle, struct, sys


class Cache:
    def __init__(self, d):
        self.maps = []
        self.files = []
        main = None
        for path in sorted(glob.glob(os.path.join(d, 'dyld_shared_cache_arm64*'))):
            if path.endswith(('.symbols', '.bin', '.part')):
                continue
            f = open(path, 'rb')
            m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            self.files.append(m)
            off, count = struct.unpack_from('<II', m, 0x10)
            for i in range(count):
                addr, size, foff = struct.unpack_from('<QQQ', m, off + 32 * i)
                self.maps.append((addr, size, m, foff))
            if path.endswith('dyld_shared_cache_arm64'):
                main = m
        self.main = main
        self.maps.sort(key=lambda t: t[0])

    def read(self, va, n):
        for addr, size, m, foff in self.maps:
            if addr <= va < addr + size:
                o = foff + (va - addr)
                return m[o:o + n]
        return None

    def images(self):
        off, count = struct.unpack_from('<QQ', self.main, 0x88)
        out = []
        for i in range(count):
            uuid, load, tsize, poff = struct.unpack_from('<16sQII', self.main, off + 32 * i)
            path = self.main[poff:self.main.find(b'\0', poff)].decode()
            out.append((load, tsize, path))
        return out


def macho_symbols(c, load):
    hdr = c.read(load, 32)
    if hdr is None or struct.unpack_from('<I', hdr, 0)[0] != 0xfeedfacf:
        return []
    ncmds, sizeofcmds = struct.unpack_from('<II', hdr, 16)
    cmds = c.read(load + 32, sizeofcmds)
    off = 0
    linkedit = None
    symtab = None
    for _ in range(ncmds):
        cmd, size = struct.unpack_from('<II', cmds, off)
        if cmd == 0x19:
            name = cmds[off + 8:off + 24].split(b'\0')[0]
            vmaddr, vmsize, fileoff = struct.unpack_from('<QQQ', cmds, off + 24)
            if name == b'__LINKEDIT':
                linkedit = (vmaddr, fileoff)
        elif cmd == 0x2:
            symtab = struct.unpack_from('<IIII', cmds, off + 8)
        off += size
    if not linkedit or not symtab:
        return []
    symoff, nsyms, stroff, strsize = symtab
    base = linkedit[0] - linkedit[1]
    syms = c.read(base + symoff, nsyms * 16)
    strs = c.read(base + stroff, strsize)
    if syms is None or strs is None:
        return []
    out = []
    for i in range(nsyms):
        strx, ntype, sect, desc, value = struct.unpack_from('<IBBHQ', syms, 16 * i)
        if (ntype & 0x0e) == 0x0e and value:
            e = strs.find(b'\0', strx)
            out.append((value, strs[strx:e].decode('utf-8', 'replace')))
    return out


def local_symbols(d):
    path = os.path.join(d, 'dyld_shared_cache_arm64.symbols')
    if not os.path.exists(path):
        return []
    f = open(path, 'rb')
    m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    lso, lss = struct.unpack_from('<QQ', m, 0x48)
    nl_off, nl_count, s_off, s_size, e_off, e_count = struct.unpack_from('<6I', m, lso)
    out = []
    base = lso
    for i in range(nl_count):
        strx, ntype, sect, desc, value = struct.unpack_from('<IBBHQ', m, base + nl_off + 16 * i)
        if (ntype & 0x0e) == 0x0e and value:
            s = base + s_off + strx
            e = m.find(b'\0', s)
            out.append((value, m[s:e].decode('utf-8', 'replace')))
    return out


def build(d):
    c = Cache(d)
    imgs = c.images()
    syms = []
    for load, tsize, path in imgs:
        syms += macho_symbols(c, load)
    syms += local_symbols(d)
    syms.sort()
    dedup = []
    for v, n in syms:
        if dedup and dedup[-1][0] == v:
            continue
        dedup.append((v, n))
    with open(os.path.join(d, 'symindex.bin'), 'wb') as fh:
        pickle.dump({'imgs': sorted(imgs), 'syms': dedup}, fh)
    print(len(imgs), 'images,', len(dedup), 'symbols')


def lookup(d, addrs):
    idx = pickle.load(open(os.path.join(d, 'symindex.bin'), 'rb'))
    imgs, syms = idx['imgs'], idx['syms']
    vals = [v for v, _ in syms]
    loads = [l for l, _, _ in imgs]
    for a in addrs:
        i = bisect.bisect_right(loads, a) - 1
        img = '?'
        if i >= 0 and a < imgs[i][0] + imgs[i][1]:
            img = os.path.basename(imgs[i][2])
        j = bisect.bisect_right(vals, a) - 1
        sym = f'{syms[j][1]}+{a - syms[j][0]:#x}' if j >= 0 and a - syms[j][0] < 0x100000 else '?'
        print(f'{a:#x} {img} {sym}')


if __name__ == '__main__':
    d = sys.argv[1]
    if sys.argv[2] == 'build':
        build(d)
    else:
        lookup(d, [int(x, 16) for x in sys.argv[2:]])

#!/usr/bin/env python3
"""Find things in the iOS dyld shared cache of the root image (split into subcaches) by RTTI.

  dsc-find.py DSC_DIR vtable CLASS_TYPEINFO_NAME [SLOT_OFFSET ...]
  dsc-find.py DSC_DIR dis ADDRESS [COUNT]

`vtable N2CA3OGL11GLESContextE 0x378 0x388` prints the unslid address of the class's vtable (as
HakiOS's inject.c names them: the offset-to-top word) and what the given slots hold. Pointers are
decoded as slide info v3 has them in the cache files (auth: offset from the cache base; plain:
the address itself).
"""
import glob
import os
import struct
import sys

CACHE_BASE = 0x180000000


class Cache:
    def __init__(self, directory):
        self.maps = []                          # (address, size, file data, file offset)
        for path in sorted(glob.glob(os.path.join(directory, 'dyld_shared_cache_arm64e*'))):
            if path.endswith('.map') or path.endswith('.symbols'):
                continue
            data = open(path, 'rb').read()
            off, count = struct.unpack_from('<II', data, 0x10)
            for i in range(count):
                address, size, fileoff = struct.unpack_from('<QQQ', data, off + 32 * i)
                self.maps.append((address, size, data, fileoff))

    def where(self, address):
        for a, s, data, fo in self.maps:
            if a <= address < a + s:
                return data, fo + address - a
        return None, None

    def read(self, address, n):
        data, at = self.where(address)
        return None if data is None else data[at:at + n]

    def u64(self, address):
        b = self.read(address, 8)
        return None if b is None else struct.unpack('<Q', b)[0]

    @staticmethod
    def target(raw):
        if raw >> 63:                           # auth: offset from the cache's base
            return CACHE_BASE + (raw & 0xffffffff)
        return raw & 0x3ffffffff                # (the cache's addresses are below 16 GiB; above them other fields)

    def find_bytes(self, needle):
        for a, s, data, fo in self.maps:
            at = data.find(needle, fo, fo + s)
            while at >= 0:
                yield a + at - fo
                at = data.find(needle, at + 1, fo + s)

    def find_pointer(self, value):
        """Words whose decoded target is `value` (8-aligned)."""
        for a, s, data, fo in self.maps:
            lo = value & 0x7ffffffffff
            # plain pointers keep the address in their low 43 bits; auth ones the offset in the low 32
            for key in (struct.pack('<I', lo & 0xffffffff), struct.pack('<I', (value - CACHE_BASE) & 0xffffffff)):
                at = data.find(key, fo, fo + s)
                while at >= 0:
                    if (at - fo) % 8 == 0:
                        raw = struct.unpack_from('<Q', data, at)[0]
                        if self.target(raw) == value:
                            yield a + at - fo
                    at = data.find(key, at + 1, fo + s)


def main():
    cache = Cache(sys.argv[1])
    what = sys.argv[2]
    if what == 'vtable':
        name = sys.argv[3].encode() + b'\0'
        seen = set()
        for s in cache.find_bytes(name):
            if cache.read(s - 1, 1) not in (b'\0',):
                continue
            for ti_name_ptr in cache.find_pointer(s):
                typeinfo = ti_name_ptr - 8
                if typeinfo in seen:
                    continue
                seen.add(typeinfo)
                print('typeinfo name %#x, typeinfo %#x' % (s, typeinfo))
                for ref in cache.find_pointer(typeinfo):
                    if cache.u64(ref - 8) != 0:     # the word before is offset-to-top, 0 for a primary vtable
                        continue
                    vtable = ref - 8
                    print('  vtable %#x' % vtable)
                    for slot in sys.argv[4:]:
                        o = int(slot, 16)
                        raw = cache.u64(vtable + 0x10 + o)
                        print('    slot %#x at %#x: raw %#018x -> %#x' % (o, vtable + 0x10 + o, raw, cache.target(raw)))
    elif what == 'dis':
        import capstone
        address = int(sys.argv[3], 16)
        count = int(sys.argv[4]) if len(sys.argv) > 4 else 24
        md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
        for insn in md.disasm(cache.read(address, 4 * count), address):
            print('%#x: %s %s' % (insn.address, insn.mnemonic, insn.op_str))
    elif what == 'str':
        for s in cache.find_bytes(sys.argv[3].encode()):
            print('%#x' % s)


main()

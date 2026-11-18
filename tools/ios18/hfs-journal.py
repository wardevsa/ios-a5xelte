#!/usr/bin/env python3
"""Turn the "journaled" attribute of an HFS+/HFSX image on or off, leaving its journal where mkfs.hfsplus -J put it.

  hfs-journal.py on|off|show IMG

Why (Galaxy S7, iOS 18 root, 2026-11-18): Renegade formats the root without a journal, because hfsroot_owners.py edits the
catalog in place and refuses a journaled volume. On the phone every hard reset into TWRP then left the allocation bitmap
behind what had been written: boot-18k23 had "BlockMarkFreeInternal() trying to free unallocated blocks on volume iOSRoot",
"Runtime corruption detected", and the drop zone's wallpaper.png could not be written (error 5): the home screen went black.

mkroot-s7.py formats with mkfs.hfsplus -s -J (the journal is a pair of reserved files, .journal and .journal_info_block,
empty) and clears the attribute at once, so every Renegade step sees the unjournaled volume it expects; this tool sets it
again when the image is finished. The phone's kernel then mounts a journaled volume whose journal is empty, and keeps the
journal from there on.
"""
import struct
import sys

JOURNALED = 1 << 13        # kHFSVolumeJournaledBit, in the volume header's attributes (offset 4)
VH = 1024                  # the volume header, 1024 bytes into the volume


def read_header(f):
    f.seek(VH)
    vh = bytearray(f.read(512))
    sig = struct.unpack_from('>H', vh, 0)[0]
    if sig not in (0x482B, 0x4858):                     # 'H+', 'HX'
        sys.exit(f'not an HFS+/HFSX volume (signature {sig:#06x})')
    return vh


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ('on', 'off', 'show'):
        sys.exit(__doc__)
    what, img = sys.argv[1:]
    with open(img, 'r+b' if what != 'show' else 'rb') as f:
        vh = read_header(f)
        attrs = struct.unpack_from('>I', vh, 4)[0]
        jib = struct.unpack_from('>I', vh, 12)[0]           # journalInfoBlock: 0 when mkfs made no journal
        if what == 'show':
            print(f'{img}: journaled {bool(attrs & JOURNALED)}, journal info block {jib}')
            return
        if what == 'on' and jib == 0:
            sys.exit(f'{img}: no journal was made (format with mkfs.hfsplus -J)')
        new = attrs | JOURNALED if what == 'on' else attrs & ~JOURNALED
        struct.pack_into('>I', vh, 4, new)
        f.seek(VH)
        f.write(vh)
        # the alternate volume header, 1024 bytes before the end, says the same
        f.seek(0, 2)
        end = f.tell()
        f.seek(end - 1024)
        alt = bytearray(f.read(512))
        if struct.unpack_from('>H', alt, 0)[0] in (0x482B, 0x4858):
            struct.pack_into('>I', alt, 4, new)
            f.seek(end - 1024)
            f.write(alt)
        print(f'{img}: journaled {what} (attributes {attrs:#x} -> {new:#x}, journal info block {jib})')


if __name__ == '__main__':
    main()

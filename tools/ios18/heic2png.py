#!/usr/bin/env python3
"""Turn every .HEIC under ROOT/Library/Wallpaper into PNG, in place, under the same name.

  heic2png.py ROOT          (needs pillow and pillow-heif)

Why (Galaxy S7, iOS 18 root, 2026-11-19): CollectionsPoster draws iOS's own wallpapers (the iOS 17/18 and Clownfish
collections, 24 files) from HEIC through ImageIO and VideoToolbox, and this phone has no HEVC decoder iOS can use: the
wallpaper came out black (boot-18k33, with herosb's picture turned off). iOS 16's port did the same with macOS's sips
(tools/herolte-wallpaper-png.sh, through hero-run); ImageIO goes by the bytes, not the name, so PNG data under the .HEIC
name is decoded as PNG. Transparency is kept (the floating layers), and so are owner and mode.
"""
import os
import sys
import tempfile

try:
    import pillow_heif
    from PIL import Image
except ImportError:
    sys.exit('heic2png.py: pillow and pillow-heif are needed (pip install pillow-heif)')


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    top = os.path.join(sys.argv[1], 'Library', 'Wallpaper')
    pillow_heif.register_heif_opener()
    done = kept = 0
    before = after = 0
    for d, _, names in os.walk(top):
        for n in names:
            if not n.lower().endswith('.heic'):
                continue
            path = os.path.join(d, n)
            with open(path, 'rb') as f:
                head = f.read(8)
            if head.startswith(b'\x89PNG'):
                kept += 1                       # an earlier run's
                continue
            st = os.stat(path)
            img = Image.open(path)
            img = img.convert('RGBA' if ('A' in img.getbands() or img.info.get('transparency') is not None) else 'RGB')
            fd, tmp = tempfile.mkstemp(dir=d, prefix='.heic2png.')
            os.close(fd)
            img.save(tmp, 'PNG', optimize=False, compress_level=6)
            os.chown(tmp, st.st_uid, st.st_gid)
            os.chmod(tmp, st.st_mode & 0o7777)
            os.replace(tmp, path)
            before += st.st_size
            after += os.path.getsize(path)
            done += 1
    print(f'heic2png: {done} wallpaper HEIC files are PNG now ({before >> 20} -> {after >> 20} MiB), {kept} were already')


if __name__ == '__main__':
    main()

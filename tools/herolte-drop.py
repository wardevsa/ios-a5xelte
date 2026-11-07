#!/usr/bin/env python3
"""Put files into the S7's iOS root from TWRP, through the kernel's drop zone.

The 128 MiB of USERDATA right below the persistent log (beyond the 20 GiB
HFSX volume) hold a package that the kernel writes into the root volume on
every boot, just before launchd (bsd/dev/herolte_drop.c). Destinations must
be under /private/var/herolte/; /private/var/herolte/autorun runs once per
boot as root (launchd job com.herolte.autorun, tools/herolte-tune-ios-root.sh).

  herolte-drop.py ADB autorun=build/herogpu-test [lib/libfoo.dylib=out/libfoo.dylib ...]
  herolte-drop.py ADB ... app=Foo.ipa app=Bar.app
  herolte-drop.py ADB --clear

DEST=SRC: DEST is relative to /private/var/herolte/ (directories are created);
files keep SRC's executable bit (mode 0755 or 0644). Run with the phone in
TWRP, /data unmounted.

app=FILE.ipa or app=DIR.app: an iOS app (arm64) goes to apps/NAME.app, and
hero-run moves it to /Applications and registers it with LaunchServices on
the next boot. Only apps that are not encrypted: open-source or your own
builds (an .ipa from Xcode, AltStore sources of open-source apps...). App
Store downloads are encrypted with FairPlay, which this port cannot run;
they are refused.
"""
import argparse
import hashlib
import os
import struct
import subprocess
import sys
import time
import zipfile

LC_ENCRYPTION_INFO, LC_ENCRYPTION_INFO_64 = 0x21, 0x2c
CPU_TYPE_ARM64 = 0x0100000c


def macho_slices(data):
    """(cputype, cpusubtype, offset) of each Mach-O in data, [] if it is not one."""
    if len(data) < 8:
        return []
    magic = struct.unpack_from('>I', data, 0)[0]
    if magic in (0xcafebabe, 0xcafebabf):          # fat, big-endian header
        n = struct.unpack_from('>I', data, 4)[0]
        wide = magic == 0xcafebabf
        out = []
        for i in range(min(n, 16)):
            if wide:
                ct, st, off = struct.unpack_from('>IIQ', data, 8 + i * 32)
            else:
                ct, st, off = struct.unpack_from('>III', data, 8 + i * 20)
            out.append((ct, st & 0xffffff, off))
        return out
    if struct.unpack_from('<I', data, 0)[0] in (0xfeedfacf, 0xfeedface):
        ct, st = struct.unpack_from('<II', data, 4)
        return [(ct, st & 0xffffff, 0)]
    return []


def macho_encrypted(data, off):
    magic, _, _, _, ncmds = struct.unpack_from('<IIIII', data, off)
    p = off + (32 if magic == 0xfeedfacf else 28)
    for _ in range(ncmds):
        cmd, size = struct.unpack_from('<II', data, p)
        if cmd in (LC_ENCRYPTION_INFO, LC_ENCRYPTION_INFO_64) and struct.unpack_from('<I', data, p + 16)[0] != 0:
            return True
        p += size
    return False


def app_items(src):
    """[(dest, bytes, mode)] of an app bundle, from an .ipa or a .app folder; exits on what cannot run here."""
    files = []
    if os.path.isdir(src):
        name = os.path.basename(os.path.normpath(src))
        for root, _, names in os.walk(src):
            for n in names:
                full = os.path.join(root, n)
                if os.path.islink(full):
                    continue
                rel = os.path.relpath(full, src).replace(os.sep, '/')
                files.append((rel, open(full, 'rb').read()))
    else:
        z = zipfile.ZipFile(src)
        apps = sorted({i.split('/')[1] for i in z.namelist() if i.startswith('Payload/') and i.split('/')[1].endswith('.app')})
        if len(apps) != 1:
            sys.exit(f'{src}: expected one Payload/NAME.app, found {apps}')
        name = apps[0]
        for info in z.infolist():
            if info.is_dir() or not info.filename.startswith(f'Payload/{name}/'):
                continue
            if (info.external_attr >> 16) & 0o170000 == 0o120000:       # symlink
                continue
            files.append((info.filename[len(f'Payload/{name}/'):], z.read(info)))
    if not name.endswith('.app'):
        sys.exit(f'{src}: not an app bundle')
    machos = 0
    for rel, data in files:
        slices = macho_slices(data)
        if not slices:
            continue
        machos += 1
        arm64 = [s for s in slices if s[0] == CPU_TYPE_ARM64 and s[1] != 2]    # 2: arm64e, PAC the S7 lacks
        if not arm64:
            sys.exit(f'{name}/{rel}: no plain arm64 code (only {[hex(s[0]) for s in slices]}); it cannot run on the S7')
        if any(macho_encrypted(data, s[2]) for s in arm64):
            sys.exit(f'{name}/{rel}: encrypted (FairPlay, an App Store download): this port cannot run it')
    if machos == 0:
        sys.exit(f'{src}: no executable found')
    size = sum(len(d) for _, d in files)
    print(f'app {name}: {len(files)} files, {machos} Mach-O, {size >> 10} KiB')
    return [(f'apps/{name}/{rel}', data, 0o755 if macho_slices(data) else 0o644) for rel, data in files]

DEV = '/dev/block/platform/155a0000.ufs/by-name/USERDATA'
BLOCK = 4096
LOG_BLOCKS = 1 + (4 << 20) // BLOCK
DROP_BLOCKS = 32768
PREFIX = '/private/var/herolte/'


def adb(tool, *args, data=None):
    return subprocess.run([tool, *args], check=True, capture_output=True, input=data).stdout


def pack(items):
    payload = bytearray()
    dirs = set()
    entries = []
    files = []
    have_apps = False
    for dest, src in items:
        if dest == 'app':
            files += app_items(src)
            have_apps = True
            continue
        data = open(src, 'rb').read()
        mode = 0o755 if os.access(src, os.X_OK) or dest == 'autorun' else 0o644
        files.append((dest, data, mode))
    if have_apps:
        files.append(('apps/.ready', b'ready\n', 0o644))     # last: hero-run waits for it
    for dest, data, mode in files:
        dest = dest.strip('/')
        parts = dest.split('/')
        for i in range(1, len(parts)):
            d = PREFIX + '/'.join(parts[:i])
            if d not in dirs:
                dirs.add(d)
                entries.append((d, 0, b''))
        if len(PREFIX + dest) > 255:
            sys.exit(f'path too long for the drop zone: {dest}')
        entries.append((PREFIX + dest, mode, data))
    for path, mode, data in entries:
        p = path.encode()
        payload += struct.pack('<IIQ', len(p), mode, len(data)) + p
        payload += b'\0' * (-len(payload) % 8)
        payload += data
        payload += b'\0' * (-len(payload) % 8)
    if len(payload) > (DROP_BLOCKS - 1) * BLOCK:
        sys.exit(f'package too large: {len(payload)} bytes')
    ident = int(time.time())
    header = struct.pack('<8sIIQQ', b'HERODRP1', 1, len(entries), len(payload), ident)
    blob = header + b'\0' * (BLOCK - len(header)) + bytes(payload)
    blob += b'\0' * (-len(blob) % BLOCK)
    return blob, entries, ident


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('adb')
    ap.add_argument('items', nargs='*', help='DEST=SRC')
    ap.add_argument('--clear', action='store_true', help='erase the package header')
    args = ap.parse_args()

    size = int(adb(args.adb, 'shell', f'blockdev --getsize64 {DEV}').strip())
    first = size // BLOCK - LOG_BLOCKS - DROP_BLOCKS
    if args.clear:
        adb(args.adb, 'shell', f'dd if=/dev/zero of={DEV} bs={BLOCK} seek={first} count=1 conv=fsync')
        print('drop zone cleared')
        return
    if not args.items:
        ap.error('nothing to drop')
    blob, entries, ident = pack([i.split('=', 1) for i in args.items])
    local = 'herolte-drop.bin'
    open(local, 'wb').write(blob)
    adb(args.adb, 'push', local, '/tmp/drop.bin')
    adb(args.adb, 'shell', f'dd if=/tmp/drop.bin of={DEV} bs={BLOCK} seek={first} conv=fsync')
    back = adb(args.adb, 'shell', f'dd if={DEV} bs={BLOCK} skip={first} count={len(blob) // BLOCK} '
                                  f'2>/dev/null | sha256sum').split()[0].decode()
    adb(args.adb, 'shell', 'rm /tmp/drop.bin')
    os.remove(local)
    ok = back == hashlib.sha256(blob).hexdigest()
    shown = [e for e in entries if '/apps/' not in e[0]]
    for path, mode, data in shown:
        print(f'  {"dir " if mode == 0 else oct(mode)} {path} {len(data)} bytes')
    if len(shown) != len(entries):
        print(f'  ... and {len(entries) - len(shown)} entries of apps/')
    print(f'package {ident}: {len(blob)} bytes at block {first} -> {"verified" if ok else "MISMATCH"}')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()

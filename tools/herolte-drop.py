#!/usr/bin/env python3
"""Build and transfer a validated DROP package to the herolte USERDATA drop zone.

Package format HERODRP2 (xnu/drop-v2/): the header carries the payload's SHA-256 and a
generation, and is written last, so the kernel installs a package only when it is whole.
A kernel without DROP v2 ignores it (and a v2 kernel rejects the old HERODRP1 format).
Destinations are relative to /private/var/herolte/.
"""
import argparse
import hashlib
import os
import stat
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
import zlib

LC_ENCRYPTION_INFO = 0x21
LC_ENCRYPTION_INFO_64 = 0x2C
CPU_TYPE_ARM64 = 0x0100000C

DEV = '/dev/block/platform/155a0000.ufs/by-name/USERDATA'
BLOCK = 4096
LOG_BLOCKS = 1 + (4 << 20) // BLOCK
DROP_BLOCKS = 32768
PREFIX = '/private/var/herolte/'
MAX_PATH_BYTES = 255
MAX_FAT_SLICES = 16
ZONE_MAGIC = b'HERODRP2'
DEFAULT_GENERATION = 1


class DropError(Exception):
    """A source or package cannot safely be represented in DROP."""


def fail(message):
    raise DropError(message)


def validate_relpath(path, *, allow_trailing_slash=False):
    """Validate a canonical relative POSIX path; never normalize unsafe input."""
    if not isinstance(path, str) or not path:
        fail('empty destination path')
    if '\x00' in path or '\\' in path:
        fail(f'invalid NUL or backslash in path: {path!r}')
    if path.startswith('/') or path.startswith('//'):
        fail(f'absolute path is not allowed: {path!r}')

    candidate = path[:-1] if allow_trailing_slash and path.endswith('/') else path
    if not candidate:
        fail(f'invalid path: {path!r}')
    parts = candidate.split('/')
    if any(part in ('', '.', '..') for part in parts):
        fail(f'non-canonical path component in: {path!r}')
    if parts[0].startswith('.drop'):
        fail(f'reserved name (the DROP protocol keeps its state in .drop*): {path!r}')
    try:
        encoded = candidate.encode('utf-8', 'strict')
    except UnicodeEncodeError:
        fail(f'path is not valid UTF-8: {path!r}')
    if len((PREFIX + candidate).encode('utf-8')) > MAX_PATH_BYTES:
        fail(f'path exceeds {MAX_PATH_BYTES} UTF-8 bytes: {path!r}')
    return candidate


def _open_regular_file(path, label):
    """Open a regular file without following a final symlink or blocking on a FIFO."""
    flags = os.O_RDONLY
    flags |= getattr(os, 'O_NOFOLLOW', 0)
    flags |= getattr(os, 'O_NONBLOCK', 0)
    try:
        fd = os.open(path, flags)
        mode = os.fstat(fd).st_mode
        if not stat.S_ISREG(mode):
            os.close(fd)
            fail(f'{label}: refusing non-regular file {path!r}')
        return os.fdopen(fd, 'rb')
    except DropError:
        raise
    except OSError as exc:
        fail(f'{label}: cannot safely open {path!r}: {exc}')


def _read_regular_file(path, label):
    try:
        with _open_regular_file(path, label) as stream:
            return stream.read()
    except DropError:
        raise
    except OSError as exc:
        fail(f'{label}: cannot read {path!r}: {exc}')


def macho_slices(data):
    """Return (cputype, cpusubtype, slice_offset) for valid-looking Mach-O slices."""
    if len(data) < 4:
        return []
    magic_be = struct.unpack_from('>I', data, 0)[0]

    if magic_be in (0xCAFEBABE, 0xCAFEBABF):
        if len(data) < 8:
            fail('truncated universal Mach-O header')
        count = struct.unpack_from('>I', data, 4)[0]
        if count == 0 or count > MAX_FAT_SLICES:
            fail(f'invalid universal Mach-O slice count: {count}')
        wide = magic_be == 0xCAFEBABF
        entry_size = 32 if wide else 20
        table_end = 8 + count * entry_size
        if table_end > len(data):
            fail('truncated universal Mach-O architecture table')
        result = []
        for index in range(count):
            pos = 8 + index * entry_size
            if wide:
                cputype, subtype, offset, size = struct.unpack_from('>IIQQ', data, pos)
            else:
                cputype, subtype, offset, size = struct.unpack_from('>IIII', data, pos)
            if size == 0 or offset > len(data) or size > len(data) - offset:
                fail(f'universal Mach-O slice {index} is out of bounds')
            result.append((cputype, subtype & 0xFFFFFF, offset))
        return result

    magic_le = struct.unpack_from('<I', data, 0)[0]
    if magic_le in (0xFEEDFACE, 0xFEEDFACF):
        header_size = 28 if magic_le == 0xFEEDFACE else 32
        if len(data) < header_size:
            fail('truncated thin Mach-O header')
        cputype, subtype = struct.unpack_from('<II', data, 4)
        return [(cputype, subtype & 0xFFFFFF, 0)]
    return []


def macho_encrypted(data, off):
    """Inspect load commands with strict bounds checks."""
    if off < 0 or off > len(data) - 4:
        fail('Mach-O slice offset is out of bounds')
    magic = struct.unpack_from('<I', data, off)[0]
    if magic == 0xFEEDFACF:
        header_size = 32
        if len(data) - off < header_size:
            fail('truncated 64-bit Mach-O header')
        ncmds, sizeofcmds = struct.unpack_from('<II', data, off + 16)
    elif magic == 0xFEEDFACE:
        header_size = 28
        if len(data) - off < header_size:
            fail('truncated 32-bit Mach-O header')
        ncmds, sizeofcmds = struct.unpack_from('<II', data, off + 16)
    else:
        fail('unsupported or malformed Mach-O slice magic')

    commands_start = off + header_size
    if sizeofcmds > len(data) - commands_start:
        fail('Mach-O load-command area exceeds file bounds')
    commands_end = commands_start + sizeofcmds
    if ncmds > sizeofcmds // 8:
        fail('Mach-O command count cannot fit in load-command area')

    pos = commands_start
    for _ in range(ncmds):
        if pos > commands_end - 8:
            fail('truncated Mach-O load command')
        cmd, cmdsize = struct.unpack_from('<II', data, pos)
        if cmdsize < 8 or cmdsize > commands_end - pos:
            fail('invalid Mach-O load-command size')
        if cmd in (LC_ENCRYPTION_INFO, LC_ENCRYPTION_INFO_64):
            if cmdsize < 20:
                fail('truncated Mach-O encryption-info command')
            cryptid = struct.unpack_from('<I', data, pos + 16)[0]
            if cryptid != 0:
                return True
        pos += cmdsize
    if pos != commands_end:
        fail('Mach-O load-command sizes do not match sizeofcmds')
    return False


def _safe_app_name(name, source):
    try:
        validate_relpath(name)
    except DropError as exc:
        fail(f'{source}: invalid app bundle name: {exc}')
    if '/' in name or not name.endswith('.app'):
        fail(f'{source}: expected a single NAME.app bundle, got {name!r}')
    return name


def _directory_app_items(src):
    name = _safe_app_name(os.path.basename(os.path.normpath(src)), src)
    if not os.path.isdir(src) or os.path.islink(src):
        fail(f'{src}: app source must be a real directory')

    files = []
    for root, dirs, names in os.walk(src, topdown=True, followlinks=False):
        kept_dirs = []
        for dirname in dirs:
            full = os.path.join(root, dirname)
            try:
                mode = os.lstat(full).st_mode
            except OSError as exc:
                fail(f'{src}: cannot inspect {full!r}: {exc}')
            if stat.S_ISLNK(mode):
                continue
            if not stat.S_ISDIR(mode):
                fail(f'{src}: refusing non-directory entry {full!r}')
            kept_dirs.append(dirname)
        dirs[:] = kept_dirs

        for filename in names:
            full = os.path.join(root, filename)
            try:
                mode = os.lstat(full).st_mode
            except OSError as exc:
                fail(f'{src}: cannot inspect {full!r}: {exc}')
            if stat.S_ISLNK(mode):
                continue
            if not stat.S_ISREG(mode):
                fail(f'{src}: refusing non-regular entry {full!r}')
            rel = os.path.relpath(full, src).replace(os.sep, '/')
            validate_relpath(rel)
            data = _read_regular_file(full, f'{src} app member')
            if data is None:
                continue
            files.append((rel, data))
    return name, files


def _zip_app_items(src):
    try:
        source_mode = os.lstat(src).st_mode
    except OSError as exc:
        fail(f'{src}: cannot inspect IPA/ZIP source: {exc}')
    if stat.S_ISLNK(source_mode) or not stat.S_ISREG(source_mode):
        fail(f'{src}: IPA/ZIP source must be a regular non-symlink file')

    source_stream = None
    try:
        source_stream = _open_regular_file(src, 'IPA/ZIP source')
        archive = zipfile.ZipFile(source_stream, 'r')
    except (OSError, zipfile.BadZipFile, EOFError, DropError) as exc:
        if source_stream is not None:
            try:
                source_stream.close()
            except OSError:
                pass
        fail(f'{src}: invalid or unreadable IPA/ZIP: {exc}')

    try:
        with archive:
            infos = archive.infolist()
            app_names = set()
            for info in infos:
                raw = info.filename
                if '\x00' in raw or '\\' in raw or raw.startswith('/'):
                    fail(f'{src}: unsafe ZIP member path {raw!r}')
                parts = raw.split('/')
                if len(parts) >= 2 and parts[0] == 'Payload' and parts[1].endswith('.app'):
                    _safe_app_name(parts[1], src)
                    app_names.add(parts[1])
            if len(app_names) != 1:
                fail(f'{src}: expected one Payload/NAME.app, found {sorted(app_names)}')
            name = next(iter(app_names))
            prefix = f'Payload/{name}/'
            files = []
            seen = set()

            for info in infos:
                raw = info.filename
                if not raw.startswith(prefix):
                    continue
                relative = raw[len(prefix):]
                if info.is_dir():
                    if relative:
                        validate_relpath(relative, allow_trailing_slash=True)
                    continue
                relative = validate_relpath(relative)
                if relative in seen:
                    fail(f'{src}: duplicate ZIP member path {relative!r}')
                seen.add(relative)

                unix_mode = (info.external_attr >> 16) & 0xFFFF
                file_type = stat.S_IFMT(unix_mode) if info.create_system == 3 else 0
                if file_type == stat.S_IFLNK:
                    continue
                if file_type not in (0, stat.S_IFREG):
                    fail(f'{src}: refusing special ZIP member {raw!r}')
                if info.flag_bits & 0x1:
                    fail(f'{src}: encrypted ZIP member is not supported: {raw!r}')
                if info.file_size > (DROP_BLOCKS - 1) * BLOCK:
                    fail(f'{src}: ZIP member exceeds DROP capacity: {raw!r}')
                expanded_size = sum(len(item[1]) for item in files)
                if expanded_size > (DROP_BLOCKS - 1) * BLOCK - info.file_size:
                    fail(f'{src}: expanded app exceeds DROP capacity')
                try:
                    data = archive.read(info)
                except (RuntimeError, zipfile.BadZipFile, EOFError, OSError,
                        NotImplementedError, zlib.error) as exc:
                    fail(f'{src}: cannot safely read ZIP member {raw!r}: {exc}')
                if len(data) != info.file_size:
                    fail(f'{src}: size mismatch in ZIP member {raw!r}')
                files.append((relative, data))
    except (zipfile.BadZipFile, EOFError, OSError, RuntimeError,
            NotImplementedError, zlib.error, ValueError) as exc:
        fail(f'{src}: malformed or unreadable IPA/ZIP: {exc}')
    finally:
        source_stream.close()
    return name, files


def app_items(src):
    """Return [(destination, bytes, mode)] for a validated .app or .ipa."""
    if os.path.isdir(src) and not os.path.islink(src):
        name, files = _directory_app_items(src)
    else:
        name, files = _zip_app_items(src)

    if not files:
        fail(f'{src}: app bundle contains no regular files')

    macho_count = 0
    for rel, data in files:
        slices = macho_slices(data)
        if not slices:
            continue
        macho_count += 1
        arm64 = [item for item in slices
                 if item[0] == CPU_TYPE_ARM64 and item[1] != 2]
        if not arm64:
            fail(f'{name}/{rel}: no plain arm64 code; it cannot run on the S7')
        for _, _, offset in arm64:
            if macho_encrypted(data, offset):
                fail(f'{name}/{rel}: encrypted (FairPlay); this port cannot run it')
    if macho_count == 0:
        fail(f'{src}: no executable found')

    total = sum(len(data) for _, data in files)
    print(f'app {name}: {len(files)} files, {macho_count} Mach-O, {total >> 10} KiB')
    result = []
    for rel, data in files:
        destination = validate_relpath(f'apps/{name}/{rel}')
        result.append((destination, data, 0o755 if macho_slices(data) else 0o644))
    return result


def adb(tool, *args, data=None):
    return subprocess.run([tool, *args], check=True, capture_output=True,
                          input=data).stdout


def pack(items, generation=None):
    """Serialize validated files into a HERODRP2 zone image (header block + payload)."""
    files = []
    for dest, src in items:
        if dest == 'app':
            files.extend(app_items(src))
            continue
        destination = validate_relpath(dest)
        data = _read_regular_file(src, 'source file')
        if data is None:
            fail(f'source file is a symlink: {src!r}')
        mode = 0o755 if os.access(src, os.X_OK) or destination == 'autorun' else 0o644
        files.append((destination, data, mode))

    if not files:
        fail('package contains no files')

    entries = []
    directories = set()
    occupied = {}
    for dest, data, mode in files:
        dest = validate_relpath(dest)
        if mode not in (0o644, 0o755):
            fail(f'invalid file mode for {dest!r}')
        parts = dest.split('/')
        for index in range(1, len(parts)):
            directory = '/'.join(parts[:index])
            previous = occupied.get(directory)
            if previous == 'file':
                fail(f'path conflict: {directory!r} is both a file and a directory')
            occupied[directory] = 'dir'
            if directory not in directories:
                directories.add(directory)
                entries.append((PREFIX + directory, 0, b''))
        previous = occupied.get(dest)
        if previous == 'dir' or previous == 'file':
            fail(f'duplicate or conflicting destination: {dest!r}')
        occupied[dest] = 'file'
        full_path = PREFIX + dest
        if len(full_path.encode('utf-8')) > MAX_PATH_BYTES:
            fail(f'path exceeds {MAX_PATH_BYTES} UTF-8 bytes: {dest!r}')
        entries.append((full_path, mode, data))

    if len(entries) > 0xFFFFFFFF:
        fail('too many package entries')

    payload = bytearray()
    for path, mode, data in entries:
        encoded_path = path.encode('utf-8', 'strict')
        if not encoded_path or len(encoded_path) > MAX_PATH_BYTES:
            fail(f'invalid encoded destination path: {path!r}')
        payload += struct.pack('<IIQ', len(encoded_path), mode, len(data))
        payload += encoded_path
        payload += b'\0' * (-len(payload) % 8)
        payload += data
        payload += b'\0' * (-len(payload) % 8)

    maximum_payload = (DROP_BLOCKS - 1) * BLOCK
    if len(payload) > maximum_payload:
        fail(f'package too large: {len(payload)} bytes')

    if generation is None:
        generation = DEFAULT_GENERATION
    if not 0 <= generation < 1 << 64:
        fail(f'generation out of range: {generation}')
    # Identity shown to the user: first 64 bits of SHA-256(payload), not a signature.
    ident = int.from_bytes(hashlib.sha256(payload).digest()[:8], 'big')
    blob = build_header(len(entries), bytes(payload), generation) + bytes(payload)
    blob += b'\0' * (-len(blob) % BLOCK)
    return blob, entries, ident


def build_header(count, payload, generation):
    """Block 0 of a HERODRP2 zone (xnu/drop-v2/herolte_drop_core.c, hdc_zone_header)."""
    header = bytearray(BLOCK)
    header[0:8] = ZONE_MAGIC
    struct.pack_into('<IIQQ', header, 8, 2, count, len(payload), generation)
    header[32:64] = hashlib.sha256(payload).digest()
    header[BLOCK - 32:] = hashlib.sha256(bytes(header[:BLOCK - 32])).digest()
    return bytes(header)


def _sha_of_zone(tool, block, count):
    out = adb(tool, 'shell',
              f'dd if={DEV} bs={BLOCK} skip={block} count={count} 2>/dev/null | sha256sum')
    return out.split()[0].decode()


def _dd_in(tool, workdir, name, data, block):
    """Push `data` (a whole number of blocks) and dd it to zone block `block`, with fsync."""
    local = os.path.join(workdir, name)
    remote = f'/tmp/{name}'
    with open(local, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    adb(tool, 'push', local, remote)
    try:
        adb(tool, 'shell', f'dd if={remote} of={DEV} bs={BLOCK} seek={block} conv=fsync')
    finally:
        try:
            adb(tool, 'shell', f'rm -f {remote}')
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass


def write_zone(tool, first, blob):
    """Write a package so that a valid header never sits over a half-written payload.

    Order: erase the header, write and verify the payload, then write and verify the
    header alone. Any failure erases the header again. Returns True only when both
    read back identical (read-back may come from the page cache; see the README).
    """
    header, body = blob[:BLOCK], blob[BLOCK:]
    zero = f'dd if=/dev/zero of={DEV} bs={BLOCK} seek={first} count=1 conv=fsync'
    ok = False
    try:
        with tempfile.TemporaryDirectory(prefix='herolte-drop-') as workdir:
            adb(tool, 'shell', zero)
            _dd_in(tool, workdir, 'drop-body.bin', body, first + 1)
            if _sha_of_zone(tool, first + 1, len(body) // BLOCK) != hashlib.sha256(body).hexdigest():
                return False
            _dd_in(tool, workdir, 'drop-head.bin', header, first)
            ok = _sha_of_zone(tool, first, 1) == hashlib.sha256(header).hexdigest()
            return ok
    finally:
        if not ok:
            try:
                adb(tool, 'shell', zero)
            except (subprocess.CalledProcessError, FileNotFoundError, OSError):
                pass


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('adb')
    parser.add_argument('items', nargs='*', help='DEST=SRC')
    parser.add_argument('--clear', action='store_true',
                        help='erase the package header')
    parser.add_argument('--generation', type=int, default=DEFAULT_GENERATION,
                        help='package generation; the same content and generation is installed '
                             'once, and a package abandoned after repeated failures needs a new one')
    parser.add_argument('--force', action='store_true',
                        help='use a new generation (milliseconds since the epoch) so the '
                             'same content is installed again')
    args = parser.parse_args()

    try:
        size = int(adb(args.adb, 'shell',
                       f'blockdev --getsize64 {DEV}').strip())
        first = size // BLOCK - LOG_BLOCKS - DROP_BLOCKS
        if first < 0:
            fail('USERDATA device is too small for the configured DROP layout')
        if args.clear:
            adb(args.adb, 'shell',
                f'dd if=/dev/zero of={DEV} bs={BLOCK} seek={first} '
                f'count=1 conv=fsync')
            print('drop zone cleared')
            return 0
        if not args.items:
            parser.error('nothing to drop')

        parsed_items = []
        for item in args.items:
            if '=' not in item:
                fail(f'item must be DEST=SRC: {item!r}')
            destination, source = item.split('=', 1)
            if not destination or not source:
                fail(f'item must have non-empty DEST and SRC: {item!r}')
            parsed_items.append((destination, source))

        generation = int(time.time() * 1000) if args.force else args.generation
        blob, entries, ident = pack(parsed_items, generation)
        ok = write_zone(args.adb, first, blob)

        shown = [entry for entry in entries if '/apps/' not in entry[0]]
        for path, mode, data in shown:
            print(f'  {"dir " if mode == 0 else oct(mode)} {path} {len(data)} bytes')
        if len(shown) != len(entries):
            print(f'  ... and {len(entries) - len(shown)} entries of apps/')
        print(f'package {ident}: {len(blob)} bytes at block {first} '
              f'-> {"verified" if ok else "MISMATCH"}')
        return 0 if ok else 1
    except (DropError, OSError, ValueError, struct.error,
            subprocess.CalledProcessError) as exc:
        print(f'herolte-drop: error: {exc}', file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            detail = exc.stderr.decode(errors='replace').strip()
            if detail:
                print(detail, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

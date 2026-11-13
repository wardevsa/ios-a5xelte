#!/usr/bin/env python3
"""Verify a HEROLTE XNU BOOT image candidate on the PC. Read-only: never opens a block device, never writes the image.

  herolte-verify-boot.py BOOT.img [--kernel KERNEL] [--loader xnu_boot.Image] [--stock STOCK_BOOT.img]
                                  [--partition-size 41943040] [--expect-arg ARG ...] [--forbid-arg ARG ...] [--profile n2-readonly]

Checks (each prints PASS/FAIL, exit status 1 if any FAIL):
  header   ANDROID! header, sizes inside the file, SHA-1 id recomputed, SEANDROIDENFORCE tail, fits the partition
  loader   arm64 Image header, image_size as herolte-pack-boot.py writes it, payload at the 4 KiB-aligned end of the loader
           (with --loader: the loader bytes equal the given file apart from the patched header fields)
  payload  SWEETXNU container: segment table inside the payload, no overlaps, entry inside a segment, kernel_end,
           ADT parses and its dram-base/dram-size equal the payload's phys_base/mem_size, command line < 608 and printable
  rebuild  with --kernel: mkpayload.build(kernel, embedded ADT, embedded cmdline) gives EXACTLY the embedded payload
  stock    with --stock: DTBH and ramdisk equal the stock BOOT's, header fields other than sizes/id/cmdline unchanged
--profile n2-readonly (test ladder step N2, docs/estado-y-camino-a-flashear.md): USERDATA (Android) must stay untouched. The kernel writes
only when ufsrw != 0 (su.writable = (rw != 0), patches 0030/0204) and mounts root read-write when rootrw != 0 (0031), so ANY form that is
not exactly "=0" counts as enabling: ufsrw=1, ufsrw=2, ufsrw=0x1, ufsrw=abc and a bare ufsrw. The profile
  - FAILs if ufsrw, rootrw or emmcwrite is enabled in the effective command line (payload) or anywhere outside the kernel segments
    (header command line, loader, ADT, ramdisk, DTBH, second, tail),
  - requires the explicit read-only arguments ufsrw=0 herolog=0 herodrop=0 (belt and braces: herolog and herodrop only write with ufsrw)
    and the N2 arguments rd=ufsroot0 ufsroot=USERDATA cpus=8,
  - FAILs on a duplicated argument name (a repeated or contradictory argument, e.g. ufsrw=0 ufsrw=1) and on an ADT /chosen boot-args property
    (the shim takes the command line from the payload only; a second source would be an unreviewed one).
This does not prove the image boots; it proves the image is what the build chain says it is and is internally consistent.
"""
import argparse, hashlib, importlib.util, os, struct, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import adt  # noqa: E402
import mkpayload  # noqa: E402

PART = 41943040
PAGE16 = 0x4000


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fname))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


class R:
    def __init__(self): self.fail = 0; self.lines = []

    def ok(self, cond, msg):
        self.lines.append(('PASS ' if cond else 'FAIL ') + msg)
        if not cond: self.fail += 1
        return cond

    def info(self, msg): self.lines.append('     ' + msg)


def parse_boot(boot):
    if boot[:8] != b'ANDROID!':
        return None
    ks, ka, rs, ra, ss, sa, ta, page, dts, unused = struct.unpack_from('<10I', boot, 8)
    al = lambda n: (n + page - 1) // page * page
    ko = page; ro = ko + al(ks); so = ro + al(rs); do = so + al(ss)
    return dict(kernel_size=ks, ramdisk_size=rs, second_size=ss, dt_size=dts, page=page, align=al, unused=unused,
                kernel_addr=ka, ramdisk_addr=ra, second_addr=sa, tags_addr=ta,
                kernel=boot[ko:ko + ks], ramdisk=boot[ro:ro + rs], second=boot[so:so + ss], dt=boot[do:do + dts],
                end=do + al(dts), id=boot[576:596], name=boot[48:64], cmdline=boot[64:576])


import re

WRITE_ARGS = ('ufsrw', 'rootrw', 'emmcwrite')
READONLY_FORBID = ()           # kept for callers; the profile now uses write_enabled()
N2_REQUIRE = ('ufsrw=0', 'herolog=0', 'herodrop=0', 'rd=ufsroot0', 'ufsroot=USERDATA', 'cpus=8')
WRITE_RE = re.compile(rb'(ufsrw|rootrw|emmcwrite)(=[^\s\x00]*)?')   # no look-behind: text glued to other bytes is still reported


def tokens(cmdline):
    out = []
    for t in cmdline.split():
        name, eq, val = t.partition('=')
        out.append((t, name, bool(eq), val))
    return out


def write_enabled(name, has_eq, val):
    # conservative: only an explicit "=0" disables; a bare name, =1, =2, =0x1, =abc, = (empty) all count as enabling
    return name in WRITE_ARGS and not (has_eq and val == '0')


def write_hits(blob):
    return [m for m in WRITE_RE.finditer(blob) if write_enabled(m.group(1).decode(), m.group(2) is not None, (m.group(2) or b'')[1:].decode('latin1'))]


def verify(boot_path, kernel=None, loader=None, stock=None, partition=PART, expect_args=(), forbid_args=(), profile=None):
    r = R()
    boot = open(boot_path, 'rb').read()
    r.info('image %s  %d bytes  sha256 %s' % (os.path.basename(boot_path), len(boot), hashlib.sha256(boot).hexdigest()))
    b = parse_boot(boot)
    if not r.ok(b is not None, 'header: magic ANDROID!'):
        return r
    r.ok(b['page'] in (2048, 4096), 'header: page size %d' % b['page'])
    r.ok(b['end'] <= len(boot) and b['kernel_size'] > 0 and b['ramdisk_size'] > 0, 'header: kernel/ramdisk/dt sizes lie inside the file')
    sha = hashlib.sha1()
    for part in (b['kernel'], b['ramdisk'], b['second'], b['dt']):
        sha.update(part); sha.update(struct.pack('<I', len(part)))
    r.ok(sha.digest() == b['id'], 'header: SHA-1 id matches kernel/ramdisk/second/dt')
    r.ok(boot[b['end']:] == b'SEANDROIDENFORCE', 'header: tail is exactly SEANDROIDENFORCE')
    r.ok(len(boot) <= partition, 'header: %d bytes fit the %d-byte BOOT partition' % (len(boot), partition))
    r.ok(b['dt'][:4] == b'DTBH', 'header: device tree is a DTBH container')

    k = b['kernel']
    r.ok(len(k) > 64 and k[56:60] == b'ARMd', 'loader: arm64 Image header (ARMd)')
    if len(k) > 64:
        text_off, image_size, flags = struct.unpack_from('<3Q', k, 8)
        r.ok(image_size == (len(k) + 0x10000 + 0xfff) & ~0xfff, 'loader: image_size %#x = file size + 64 KiB headroom, 4 KiB rounded' % image_size)
    pos = -1
    off = 0
    while True:
        off = k.find(b'SWEETXNU', off)
        if off < 0: break
        if off % 4096 == 0: pos = off; break
        off += 1
    if not r.ok(pos > 0, 'loader: SWEETXNU payload at a 4 KiB-aligned offset'):
        return r
    r.info('loader %d bytes, payload at %#x (%d bytes)' % (pos, pos, len(k) - pos))
    ld = k[:pos].rstrip(b'\0') if False else k[:pos]
    if loader:
        want = open(loader, 'rb').read()
        exp_pos = (len(want) + 4095) & ~4095
        r.ok(exp_pos == pos, 'loader: payload offset equals the 4 KiB-rounded end of %s' % os.path.basename(loader))
        got = ld[:len(want)]
        r.ok(len(got) == len(want) and got[:8] == want[:8] and got[32:] == want[32:] and set(ld[len(want):]) <= {0},
             'loader: bytes equal %s apart from the patched header fields, padding is zeros' % os.path.basename(loader))
    pay = k[pos:]
    r.ok(len(pay) >= mkpayload.SEG_TABLE, 'payload: container at least as large as its header')
    if len(pay) < mkpayload.SEG_TABLE:
        return r
    magic, version, nsegs = struct.unpack_from('<8sII', pay, 0)
    virt_base, entry, adt_off, adt_size, kernel_end, phys_base, mem_size = struct.unpack_from('<7Q', pay, 0x10)
    r.ok(magic == b'SWEETXNU' and version == 1 and 1 <= nsegs <= 64, 'payload: SWEETXNU version 1, %d segments' % nsegs)
    hdr = mkpayload.SEG_TABLE + 32 * nsegs
    segs = [struct.unpack_from('<4Q', pay, mkpayload.SEG_TABLE + 32 * i) for i in range(nsegs)] if hdr <= len(pay) else []
    r.ok(len(segs) == nsegs, 'payload: segment table inside the payload')
    inside = all(fo >= hdr and fo + fs <= adt_off and fs <= vs for _, vs, fo, fs in segs) and adt_off + adt_size <= len(pay)
    r.ok(inside, 'payload: every segment is inside the file region (header .. ADT) and file_size <= vmsize; ADT inside the payload')
    r.ok(all(va % PAGE16 == 0 for va, _, _, _ in segs), 'payload: segment addresses 16 KiB aligned')
    srt = sorted((va, va + vs) for va, vs, _, _ in segs)
    r.ok(all(srt[i][1] <= srt[i + 1][0] for i in range(len(srt) - 1)), 'payload: segments do not overlap in virtual memory')
    r.ok(any(va <= entry < va + vs for va, vs, _, _ in segs), 'payload: entry %#x lies inside a segment' % entry)
    if segs:
        r.ok(kernel_end >= max(va + vs for va, vs, _, _ in segs) and kernel_end % PAGE16 == 0, 'payload: kernel_end %#x covers all segments, 16 KiB aligned' % kernel_end)
        r.ok(virt_base <= min(va for va, _, _, _ in segs) and virt_base % 0x2000000 == 0, 'payload: virt_base %#x 32 MiB aligned, below the first segment' % virt_base)
    cl = pay[mkpayload.CMDLINE:mkpayload.CMDLINE + mkpayload.BOOT_LINE_LENGTH]
    nul = cl.find(b'\0')
    r.ok(nul >= 0 and nul < mkpayload.BOOT_LINE_LENGTH - 1 and all(32 <= c < 127 for c in cl[:nul]), 'payload: command line is printable ASCII, NUL-terminated (%d of 607 characters)' % max(nul, 0))
    cmdline = cl[:max(nul, 0)].decode('ascii', 'replace')
    r.info('cmdline: ' + cmdline)
    for a in expect_args:
        r.ok(a in cmdline.split(), 'payload: command line contains %r' % a)
    toks = tokens(cmdline)
    names = [t[1] for t in toks]
    dups = sorted({n for n in names if names.count(n) > 1})
    r.ok(not dups, 'payload: no duplicated argument names%s' % (' (repeated: %s)' % ', '.join(dups) if dups else ''))
    for a in forbid_args:
        r.ok(a not in cmdline.split(), 'payload: command line does NOT contain %r' % a)
    n2 = profile == 'n2-readonly'
    enabled = [t[0] for t in toks if write_enabled(t[1], t[2], t[3])]
    if n2:
        r.ok(not enabled, 'n2: no write-enabling argument in the effective command line%s' % (' (found: %s)' % ' '.join(enabled) if enabled else ''))
        for a in N2_REQUIRE:
            r.ok(a in cmdline.split(), 'n2: required argument %r is present' % a)
    else:
        r.info('write-enabling arguments in the command line: %s' % (' '.join(enabled) or 'none'))
    adt_blob = pay[adt_off:adt_off + adt_size]
    try:
        base, size = mkpayload.adt_dram(adt_blob)
        r.ok((base, size) == (phys_base, mem_size), 'payload: ADT dram-base/size %#x/%#x equal phys_base/mem_size' % (base, size))
        root, _ = adt.parse(adt_blob)
        r.ok(any(c.name == 'chosen' for c in root.children), 'payload: ADT has /chosen')
    except Exception as e:  # noqa: BLE001
        r.ok(False, 'payload: ADT parses (%s)' % e)
    seg_lo = hdr
    regions = [('BOOT header page', boot[:b['page']]), ('loader', ld), ('payload header+segment table', pay[:hdr]), ('ADT', adt_blob),
               ('ramdisk', b['ramdisk']), ('second', b['second']), ('DTBH', b['dt']), ('tail', boot[b['end']:])]
    for name, blob in regions:
        if name == 'payload header+segment table':
            blob = blob[:mkpayload.CMDLINE] + b'\0' * mkpayload.BOOT_LINE_LENGTH + blob[mkpayload.SEG_TABLE:]   # the command line is judged above
        hits = write_hits(blob)
        if n2:
            r.ok(not hits, 'n2: no write-enabling argument inside the %s%s' % (name, ' (found: %s)' % b', '.join(m.group(0) for m in hits).decode('latin1') if hits else ''))
        elif hits:
            r.info('write-enabling text inside the %s: %s' % (name, b', '.join(m.group(0) for m in hits).decode('latin1')))
    kern_hits = write_hits(pay[seg_lo:adt_off]) if segs else []
    r.info('kernel segments: %d occurrences of write-enabling argument text (the kernel carries its own boot-arg names/messages; not an argument)' % len(kern_hits))
    try:
        root2, _ = adt.parse(adt_blob)
        chosen = next(c for c in root2.children if c.name == 'chosen')
        has_ba = any(pn in ('boot-args', 'bootargs') for pn, *_ in chosen.props)
        r.ok(not has_ba, 'payload: ADT /chosen has no boot-args property (the command line has a single source)')
    except Exception as e:  # noqa: BLE001
        r.ok(False, 'payload: ADT /chosen readable (%s)' % e)
    if kernel:
        r.info('kernel %s sha256 %s' % (os.path.basename(kernel), hashlib.sha256(open(kernel, 'rb').read()).hexdigest()))
        with tempfile.TemporaryDirectory(prefix='verify-boot.') as d:
            ap = os.path.join(d, 'embedded.adt'); open(ap, 'wb').write(adt_blob)
            try:
                rebuilt, _ = mkpayload.build(kernel, ap, cmdline)
                n = len(rebuilt)
                r.ok(pay[:n] == rebuilt and set(pay[n:]) <= {0}, 'rebuild: mkpayload(kernel, embedded ADT, embedded cmdline) reproduces the embedded payload byte for byte (%d bytes)' % n)
            except Exception as e:  # noqa: BLE001
                r.ok(False, 'rebuild: mkpayload failed (%s)' % e)
    if stock:
        s = parse_boot(open(stock, 'rb').read())
        if r.ok(s is not None, 'stock: is an ANDROID! image'):
            r.ok(s['dt'] == b['dt'], 'stock: DTBH identical to the stock BOOT')
            r.ok(s['ramdisk'] == b['ramdisk'], 'stock: ramdisk identical to the stock BOOT')
            r.ok(s['second'] == b['second'] and (s['kernel_addr'], s['ramdisk_addr'], s['second_addr'], s['tags_addr'], s['page'], s['name']) ==
                 (b['kernel_addr'], b['ramdisk_addr'], b['second_addr'], b['tags_addr'], b['page'], b['name']), 'stock: load addresses, page size, name unchanged')
            r.ok(s['cmdline'] == b['cmdline'], 'stock: BOOT header command line unchanged (the XNU command line is in the payload)')
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('boot'); ap.add_argument('--kernel'); ap.add_argument('--loader'); ap.add_argument('--stock')
    ap.add_argument('--partition-size', type=int, default=PART); ap.add_argument('--expect-arg', action='append', default=[]); ap.add_argument('--forbid-arg', action='append', default=[])
    ap.add_argument('--profile', choices=['n2-readonly'])
    a = ap.parse_args()
    if not os.path.isfile(a.boot):
        print('herolte-verify-boot: %s: not a file' % a.boot, file=sys.stderr); return 2
    r = verify(a.boot, a.kernel, a.loader, a.stock, a.partition_size, a.expect_arg, a.forbid_arg, a.profile)
    print('\n'.join(r.lines))
    print('RESULTADO: %d fallos' % r.fail)
    return 1 if r.fail else 0


if __name__ == '__main__':
    sys.exit(main())

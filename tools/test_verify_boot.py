#!/usr/bin/env python3
"""Tests of herolte-verify-boot.py. Positive case: the real N2 candidate built by herolte-build-n2.sh. Negative cases: copies manipulated in
arguments, header, sizes, payload and trailing bytes; the header SHA-1 is recomputed where the aim is to trip ONE specific check.
Skipped (not passed) when the device-day kit or the stock BOOT backup is absent.   python3 -W ignore tools/test_verify_boot.py"""
import hashlib, importlib.util, os, shutil, struct, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.expanduser('~/HackiOS/builds/device-day')
BACK = os.path.expanduser('~/HackiOS/backups/device-herolte/2026-11-12/BOOT.img')
N2 = KIT + '/boot-candidates-n2'
IMG = N2 + '/xnu-boot-v2-n2ro-clang-20261113.img'
OLD = [KIT + '/boot-candidates/xnu-boot-v2-clang.img', N2 + '/xnu-boot-v2-n2-readonly-clang.img', N2 + '/xnu-boot-v2-n2-console-clang.img']
KERNEL = KIT + '/artifacts/kernel-0334-v2-herolte-drop-v2/kernel.development.herolte'
K0332 = KIT + '/artifacts/kernel-0332-fork-8d1cf43/kernel.development.herolte'
LOADER = KIT + '/loader-clang/xnu_boot.Image'
VERIFY = os.path.join(HERE, 'herolte-verify-boot.py')
spec = importlib.util.spec_from_file_location('vb', VERIFY)
vb = importlib.util.module_from_spec(spec); spec.loader.exec_module(vb)
sys.path.insert(0, HERE)
import adt, mkpayload  # noqa: E402
HAVE = all(os.path.exists(p) for p in [IMG, KERNEL, LOADER, BACK] + OLD)
CMD_OFF = mkpayload.CMDLINE


def pay_off(): return 2048 + ((os.path.getsize(LOADER) + 4095) & ~4095)
def fails(r): return [l for l in r.lines if l.startswith('FAIL')]
def ftext(r): return '\n'.join(fails(r))


def fix_sha(b):
    p = vb.parse_boot(bytes(b)); h = hashlib.sha1()
    for part in (p['kernel'], p['ramdisk'], p['second'], p['dt']): h.update(part); h.update(struct.pack('<I', len(part)))
    b[576:596] = h.digest()


@unittest.skipUnless(HAVE, 'device-day kit, N2 candidate or stock BOOT backup not present')
class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.d = tempfile.mkdtemp(prefix='vb-test.')

    @classmethod
    def tearDownClass(cls): shutil.rmtree(cls.d, ignore_errors=True)   # only this test's own temporary copies

    def _name(self, ext): return os.path.join(self.d, 't%d.%s' % (len(os.listdir(self.d)), ext))

    def img(self, fn, sha=True):
        b = bytearray(open(IMG, 'rb').read()); fn(b)
        if sha: fix_sha(b)
        p = self._name('img'); open(p, 'wb').write(b); return p

    def cmd(self, text, sha=True):
        def f(b):
            o = pay_off() + CMD_OFF; b[o:o + mkpayload.BOOT_LINE_LENGTH] = b'\0' * mkpayload.BOOT_LINE_LENGTH; b[o:o + len(text)] = text.encode('latin1')
        return self.img(f, sha)

    def run_v(self, p, **kw):
        kw.setdefault('kernel', KERNEL); kw.setdefault('loader', LOADER); kw.setdefault('stock', BACK); kw.setdefault('profile', 'n2-readonly')
        return vb.verify(p, **kw)

    def good_cmd(self):
        b = open(IMG, 'rb').read(); o = pay_off() + CMD_OFF
        return b[o:o + mkpayload.BOOT_LINE_LENGTH].split(b'\0')[0].decode()

    def cli(self, p, *extra):
        return subprocess.run([sys.executable, '-I', VERIFY, p, '--kernel', KERNEL, '--loader', LOADER, '--stock', BACK, '--profile', 'n2-readonly', *extra],
                              capture_output=True, text=True)


class Positive(Base):
    def test_candidate_passes_all(self):
        r = self.run_v(IMG, expect_args=('cpus=8',)); self.assertEqual(fails(r), [], r.lines); self.assertGreaterEqual(sum(l.startswith('PASS') for l in r.lines), 45)

    def test_cli_exit_codes_and_summary(self):
        c = self.cli(IMG); self.assertEqual(c.returncode, 0, c.stdout); self.assertIn('RESULTADO: 0 fallos', c.stdout)
        c = self.cli(self.cmd(self.good_cmd().replace('ufsrw=0', 'ufsrw=1'))); self.assertEqual(c.returncode, 1); self.assertIn('FAIL n2: no write-enabling', c.stdout)
        c = self.cli(os.path.join(self.d, 'nope.img')); self.assertEqual(c.returncode, 2)

    def test_never_modifies_the_image(self):
        h = hashlib.sha256(open(IMG, 'rb').read()).hexdigest(); self.run_v(IMG)
        self.assertEqual(h, hashlib.sha256(open(IMG, 'rb').read()).hexdigest())

    def test_previous_candidates_are_rejected_by_n2_profile_not_waved_through(self):
        for p in OLD:
            self.assertTrue(fails(self.run_v(p, stock=None)), p)
        self.assertIn('ufsrw=1', ftext(self.run_v(OLD[0], stock=None)))   # the daily image really has the write-enabling arguments


class Arguments(Base):
    def assertFail(self, text, needle, **kw):
        r = self.run_v(self.cmd(text), **kw); self.assertIn(needle, ftext(r), (text, r.lines))

    def test_every_write_enabling_form_is_rejected(self):
        g = self.good_cmd()
        for form in ('ufsrw=1', 'ufsrw=2', 'ufsrw=0x1', 'ufsrw=abc', 'ufsrw=', 'ufsrw=00', 'ufsrw=-1', 'ufsrw=0x0', 'ufsrw'):
            self.assertFail(g.replace('ufsrw=0', form), 'no write-enabling')
        for extra in ('rootrw=1', 'rootrw', 'rootrw=2', 'emmcwrite=1', 'emmcwrite'):
            self.assertFail(g + ' ' + extra, 'no write-enabling')

    def test_explicit_zero_for_rootrw_and_emmcwrite_is_accepted(self):
        r = self.run_v(self.cmd(self.good_cmd() + ' rootrw=0 emmcwrite=0')); self.assertEqual(fails(r), [], r.lines)

    def test_missing_required_arguments(self):
        g = self.good_cmd()
        for a in ('ufsrw=0', 'herolog=0', 'herodrop=0', 'rd=ufsroot0', 'ufsroot=USERDATA', 'cpus=8'):
            self.assertFail(' '.join(t for t in g.split() if t != a), "required argument '%s'" % a)
        self.assertFail(g.replace('herodrop=0', 'herodrop=1'), "required argument 'herodrop=0'")
        self.assertFail(g.replace('herolog=0', 'herolog'), "required argument 'herolog=0'")
        self.assertFail(g.replace('cpus=8', 'cpus=4'), "required argument 'cpus=8'")

    def test_duplicates_and_contradictions(self):
        g = self.good_cmd()
        self.assertFail(g + ' ufsrw=1', 'duplicated argument names (repeated: ufsrw)')
        self.assertFail(g + ' ufsrw=0', 'repeated: ufsrw')                  # even a harmless repeat is an ambiguity
        self.assertFail(g + ' cpus=1', 'repeated: cpus')
        self.assertFail(g + ' -noprogress', 'repeated: -noprogress')
        self.assertFail('ufsrw=1 ' + g, 'repeated: ufsrw')

    def test_command_line_limits_and_characters(self):
        g = self.good_cmd()
        self.assertFail(g + ' ' + 'x' * 700, 'NUL-terminated')
        self.assertFail(g + '\x01', 'printable ASCII')
        self.assertFail(g + '\xe9', 'printable ASCII')
        ok = self.cmd(g + ' ' + 'y' * (606 - len(g) - 1))
        self.assertEqual([x for x in fails(self.run_v(ok)) if 'printable' in x or 'NUL' in x], [])   # 606 characters still fit

    def test_write_text_outside_the_kernel_is_found(self):
        pad_off = 2048 + len(open(LOADER, 'rb').read()) + 100          # zero padding after the loader, before the payload
        def loader(b): b[pad_off:pad_off + 8] = b'ufsrw=1\0'
        self.assertIn('inside the loader', ftext(self.run_v(self.img(loader))))
        def hdr(b): b[64:64 + 12] = b'rootrw=1\0\0\0\0'
        r = self.run_v(self.img(hdr)); self.assertIn('BOOT header page', ftext(r)); self.assertIn('header command line unchanged', ftext(r))
        def ramdisk(b):
            p = vb.parse_boot(bytes(b)); ro = p['page'] + p['align'](p['kernel_size']) + p['ramdisk_size'] - 30
            b[ro:ro + 8] = b'ufsrw=1 '
        r = self.run_v(self.img(ramdisk)); self.assertIn('inside the ramdisk', ftext(r)); self.assertIn('ramdisk identical', ftext(r))

    def test_adt_boot_args_property_is_rejected(self):
        b = open(IMG, 'rb').read(); o = pay_off()
        off, size = struct.unpack_from('<2Q', b, o + 0x20); blob = b[o + off:o + off + size]
        root, _ = adt.parse(blob); ch = next(c for c in root.children if c.name == 'chosen')
        ch.props.append(('boot-args', 0, b'ufsrw=1\0'.ljust(16, b'\0')))
        ap = self._name('adt'); open(ap, 'wb').write(adt.serialize(root))
        payload, _ = mkpayload.build(KERNEL, ap, self.good_cmd())
        pp = self._name('bin'); open(pp, 'wb').write(payload); out = self._name('img')
        subprocess.run([sys.executable, '-I', os.path.join(HERE, 'herolte-pack-boot.py'), 'pack', BACK, LOADER, out, '--append', pp,
                        '--partition-size', '41943040'], check=True, capture_output=True)
        r = self.run_v(out); self.assertIn('no boot-args property', ftext(r)); self.assertIn('inside the ADT', ftext(r))


class Header(Base):
    def test_magic_page_sizes_and_sha1(self):
        self.assertIn('magic', ftext(self.run_v(self.img(lambda b: b.__setitem__(0, 0x58), sha=False))))
        self.assertIn('SHA-1 id', ftext(self.run_v(self.img(lambda b: b.__setitem__(576, b[576] ^ 1), sha=False))))
        self.assertIn('SHA-1 id', ftext(self.run_v(self.img(lambda b: b.__setitem__(pay_off() + 0x3000, b[pay_off() + 0x3000] ^ 1), sha=False))))

    def test_odd_page_size_is_rejected(self):
        p = self.img(lambda b: struct.pack_into('<I', b, 36, 1000), sha=False)
        self.assertIn('page size', ftext(self.run_v(p)))

    def test_sizes_inside_the_file(self):
        for off in (8, 16, 24, 40):
            def big(b, off=off): struct.pack_into('<I', b, off, 0x7fffffff)
            try: r = self.run_v(self.img(big, sha=False)); self.assertTrue(fails(r), off)
            except SystemExit: pass                                     # parse_boot refuses a truncated layout: also a rejection
        def zero(b): struct.pack_into('<I', b, 16, 0)
        self.assertIn('sizes lie inside', ftext(self.run_v(self.img(zero))))

    def test_trailing_bytes(self):
        self.assertIn('SEANDROIDENFORCE', ftext(self.run_v(self.img(lambda b: b.__delitem__(slice(len(b) - 16, None))))))
        self.assertIn('SEANDROIDENFORCE', ftext(self.run_v(self.img(lambda b: b.extend(b'X')))))
        self.assertIn('SEANDROIDENFORCE', ftext(self.run_v(self.img(lambda b: b.__setitem__(len(b) - 1, 0x46)))))
        self.assertIn('SEANDROIDENFORCE', ftext(self.run_v(self.img(lambda b: b.__delitem__(slice(len(b) - 1, None))))))
        p = self._name('img'); open(p, 'wb').write(open(IMG, 'rb').read()[:100000])
        try: self.assertTrue(fails(self.run_v(p)))
        except SystemExit: pass

    def test_partition_limit_and_kernel_header(self):
        self.assertIn('fit the', ftext(self.run_v(IMG, partition=1000000)))
        self.assertIn('fit the', ftext(self.run_v(IMG, partition=os.path.getsize(IMG) - 1)))
        self.assertEqual([x for x in fails(self.run_v(IMG, partition=os.path.getsize(IMG))) if 'fit the' in x], [])
        self.assertIn('arm64 Image header', ftext(self.run_v(self.img(lambda b: b.__setitem__(2048 + 56, 0)))))
        self.assertIn('image_size', ftext(self.run_v(self.img(lambda b: struct.pack_into('<Q', b, 2048 + 16, 0x1234)))))

    def _dt_off(self, b):
        p = vb.parse_boot(bytes(b)); return p['page'] + p['align'](p['kernel_size']) + p['align'](p['ramdisk_size']) + p['align'](p['second_size'])

    def test_dtbh_ramdisk_and_load_addresses_against_stock(self):
        self.assertIn('DTBH identical', ftext(self.run_v(self.img(lambda b: b.__setitem__(self._dt_off(b) + 0x40, b[self._dt_off(b) + 0x40] ^ 1)))))
        self.assertIn('load addresses', ftext(self.run_v(self.img(lambda b: struct.pack_into('<I', b, 12, 0x10008001)))))
        self.assertIn('header command line', ftext(self.run_v(self.img(lambda b: b.__setitem__(64, ord('x'))))))
        self.assertIn('DTBH container', ftext(self.run_v(self.img(lambda b: b.__setitem__(self._dt_off(b), 0x58)))))


class Payload(Base):
    def f(self, off, fmt, val):
        def g(b): struct.pack_into(fmt, b, pay_off() + off, val)
        return self.run_v(self.img(g))

    def q(self, off): return struct.unpack_from('<Q', open(IMG, 'rb').read(), pay_off() + off)[0]

    def test_container_fields(self):
        self.assertIn('SWEETXNU payload', ftext(self.f(0, '<8s', b'SWEETXXU')))      # the loader can no longer find the container at all
        self.assertIn('SWEETXNU version 1', ftext(self.f(8, '<I', 2)))
        self.assertIn('SWEETXNU version 1', ftext(self.f(12, '<I', 0)))
        self.assertIn('SWEETXNU version 1', ftext(self.f(12, '<I', 65)))

    def test_segment_table_and_addresses(self):
        t = mkpayload.SEG_TABLE
        self.assertIn('16 KiB aligned', ftext(self.f(t, '<Q', self.q(t) + 8)))
        self.assertIn('inside the file region', ftext(self.f(t + 16, '<Q', 0x7fffffff)))      # file_off beyond the ADT
        self.assertIn('inside the file region', ftext(self.f(t + 24, '<Q', 0x7fffffff)))      # file_size beyond vmsize
        self.assertIn('inside the file region', ftext(self.f(t + 16, '<Q', 0)))               # overlaps the header
        self.assertIn('do not overlap', ftext(self.f(t, '<Q', self.q(t + 32))))               # two segments at the same address

    def test_entry_kernel_end_virt_base_and_adt_coherence(self):
        self.assertIn('entry', ftext(self.f(0x18, '<Q', 0xfffffff000000000)))
        self.assertIn('kernel_end', ftext(self.f(0x30, '<Q', 0xfffffff006004000)))
        self.assertIn('kernel_end', ftext(self.f(0x30, '<Q', self.q(0x30) + 1)))
        self.assertIn('virt_base', ftext(self.f(0x10, '<Q', self.q(0x10) + 0x4000)))
        self.assertIn('phys_base', ftext(self.f(0x38, '<Q', 0x800000000)))
        self.assertIn('phys_base', ftext(self.f(0x40, '<Q', 0x40000000)))
        self.assertTrue(fails(self.f(0x20, '<Q', 0x10)))                                       # ADT offset into the header
        self.assertTrue(fails(self.f(0x28, '<Q', 0x7fffffff)))                                 # ADT size beyond the payload

    def test_payload_content_is_reproducible_from_kernel(self):
        pos = pay_off() + 0x3000
        self.assertIn('rebuild', ftext(self.run_v(self.img(lambda b: b.__setitem__(pos, b[pos] ^ 1)))))      # SHA-1 recomputed: only rebuild can see it
        self.assertIn('SHA-1 id', ftext(self.run_v(self.img(lambda b: b.__setitem__(pos, b[pos] ^ 1), sha=False))))
        if os.path.exists(K0332): self.assertIn('rebuild', ftext(self.run_v(IMG, kernel=K0332)))
        self.assertIn('loader', ftext(self.run_v(IMG, loader=KIT + '/loader-clang/probe.Image')))

    def test_adt_header_destroyed(self):
        o = pay_off(); b = open(IMG, 'rb').read(); off, size = struct.unpack_from('<2Q', b, o + 0x20)
        self.assertTrue(fails(self.run_v(self.img(lambda x: x.__setitem__(slice(o + off, o + off + 8), b'\xff' * 8)))))


if __name__ == '__main__':
    unittest.main(verbosity=1)

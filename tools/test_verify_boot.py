#!/usr/bin/env python3
"""Tests of herolte-verify-boot.py against the real PC-built candidates (skipped if the kit is absent) and tampered copies."""
import hashlib, importlib.util, os, struct, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.expanduser('~/HackiOS/builds/device-day')
BACK = os.path.expanduser('~/HackiOS/backups/device-herolte/2026-11-12/BOOT.img')
IMG = KIT + '/boot-candidates-n2/xnu-boot-v2-n2-console-clang.img'
IMG_DAILY = KIT + '/boot-candidates/xnu-boot-v2-clang.img'
KERNEL = KIT + '/artifacts/kernel-0334-v2-herolte-drop-v2/kernel.development.herolte'
LOADER = KIT + '/loader-clang/xnu_boot.Image'
spec = importlib.util.spec_from_file_location('vb', os.path.join(HERE, 'herolte-verify-boot.py'))
vb = importlib.util.module_from_spec(spec); spec.loader.exec_module(vb)
HAVE = all(os.path.exists(p) for p in (IMG, IMG_DAILY, KERNEL, LOADER, BACK))


def pay_off():  # payload = page-aligned kernel start (2048) + loader rounded up to 4 KiB
    return 2048 + ((os.path.getsize(LOADER) + 4095) & ~4095)


def fails(r): return [l for l in r.lines if l.startswith('FAIL')]


@unittest.skipUnless(HAVE, 'device-day kit or stock BOOT backup not present')
class T(unittest.TestCase):
    def setUp(self): self.d = tempfile.mkdtemp(prefix='vb-test.')

    def tamper(self, fn):
        b = bytearray(open(IMG, 'rb').read()); fn(b)
        p = os.path.join(self.d, 't.img'); open(p, 'wb').write(b); return p

    def run_v(self, p, **kw):
        kw.setdefault('kernel', KERNEL); kw.setdefault('loader', LOADER); kw.setdefault('stock', BACK)
        kw.setdefault('forbid_args', vb.READONLY_FORBID)
        return vb.verify(p, **kw)

    def test_good_candidate_passes_everything(self):
        r = self.run_v(IMG, expect_args=('cpus=8', 'ufsroot=USERDATA')); self.assertEqual(fails(r), [], r.lines)
        self.assertGreaterEqual(len(r.lines), 30)
        self.assertEqual(open(IMG, 'rb').read()[pay_off():pay_off() + 8], b'SWEETXNU')   # the helper really points at the payload

    def test_daily_candidate_is_flagged_as_not_read_only(self):
        r = self.run_v(IMG_DAILY, stock=None); f = fails(r)
        self.assertEqual(len(f), 2, f); self.assertTrue(all('ufsrw=1' in x or 'rootrw=1' in x for x in f))

    def test_payload_byte_flip_is_caught_by_sha1_and_rebuild(self):
        pos = pay_off() + 0x3000
        f = '\n'.join(fails(self.run_v(self.tamper(lambda b: b.__setitem__(pos, b[pos] ^ 1)))))
        self.assertIn('SHA-1 id', f); self.assertIn('rebuild', f)

    def test_flip_with_recomputed_sha1_is_still_caught_by_rebuild(self):
        def fix(b):
            o = pay_off() + 0x3000; b[o] ^= 1
            p = vb.parse_boot(bytes(b)); import hashlib
            h = hashlib.sha1()
            for part in (p['kernel'], p['ramdisk'], p['second'], p['dt']): h.update(part); h.update(struct.pack('<I', len(part)))
            b[576:596] = h.digest()
        f = '\n'.join(fails(self.run_v(self.tamper(fix))))
        self.assertNotIn('SHA-1 id', f); self.assertIn('rebuild', f)

    def test_missing_tail_truncated_and_bad_magic(self):
        self.assertIn('SEANDROIDENFORCE', '\n'.join(fails(self.run_v(self.tamper(lambda b: b.__delitem__(slice(len(b) - 16, None)))))))
        p = os.path.join(self.d, 'short.img'); open(p, 'wb').write(open(IMG, 'rb').read()[:100000])
        self.assertTrue(fails(self.run_v(p)))
        self.assertIn('magic', '\n'.join(fails(self.run_v(self.tamper(lambda b: b.__setitem__(0, 0x58))))))

    def test_cmdline_change_in_payload_is_caught(self):
        def edit(b):
            o = pay_off() + 0x48; assert b[o:o + 5] == b'debug'; b[o:o + 5] = b'zzzzz'
        p = self.tamper(edit)
        self.assertIn('SHA-1 id', '\n'.join(fails(self.run_v(p))))
        # rebuild uses the embedded cmdline, so a consistent edit is only visible through the expected-argument checks
        self.assertIn("contains 'debug=0xc'", '\n'.join(fails(self.run_v(p, expect_args=('debug=0xc',)))))

    def test_header_cmdline_and_dtbh_differences_from_stock_are_caught(self):
        self.assertIn('header command line', '\n'.join(fails(self.run_v(self.tamper(lambda b: b.__setitem__(64, ord('x')))))))
        def dtb(b):
            p = vb.parse_boot(bytes(b)); ko = p['page']; do = ko + p['align'](p['kernel_size']) + p['align'](p['ramdisk_size']) + p['align'](p['second_size'])
            b[do + 0x40] ^= 1
        self.assertIn('DTBH identical', '\n'.join(fails(self.run_v(self.tamper(dtb), stock=BACK))))

    def test_partition_too_small_and_wrong_loader_and_wrong_kernel(self):
        self.assertIn('fit the', '\n'.join(fails(self.run_v(IMG, partition=1000000))))
        self.assertIn('loader', '\n'.join(fails(self.run_v(IMG, loader=KIT + '/loader-clang/probe.Image'))))
        k0332 = KIT + '/artifacts/kernel-0332-fork-8d1cf43/kernel.development.herolte'
        if os.path.exists(k0332): self.assertIn('rebuild', '\n'.join(fails(self.run_v(IMG, kernel=k0332))))

    def test_never_modifies_the_image(self):
        h = hashlib.sha256(open(IMG, 'rb').read()).hexdigest(); self.run_v(IMG)
        self.assertEqual(h, hashlib.sha256(open(IMG, 'rb').read()).hexdigest())


if __name__ == '__main__':
    unittest.main(verbosity=2)

#!/usr/bin/env python3
import os, subprocess, sys, tempfile, unittest
T = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'herolte-diag-patch-check.py')
def run(*a): return subprocess.run([sys.executable, '-I', T, *a], capture_output=True, text=True)
class C(unittest.TestCase):
    def mk(self, files):
        fd, p = tempfile.mkstemp(suffix='.patch'); os.write(fd, ''.join('--- a/%s\n+++ b/%s\n@@ -1 +1 @@\n-x\n+y\n' % (f, f) for f in files).encode()); os.close(fd); self.addCleanup(os.unlink, p); return p
    def test_allowed(self): self.assertEqual(run(self.mk(['osfmk/arm/arm_init.c', 'osfmk/arm64/sweet_early.c'])).returncode, 0)
    def test_other_file_rejected(self): r = run(self.mk(['osfmk/arm/arm_init.c', 'bsd/dev/herolte_gpu.c'])); self.assertEqual(r.returncode, 1); self.assertIn('herolte_gpu.c', r.stdout)
    def test_empty_rejected(self): self.assertEqual(run(self.mk([])).returncode, 1)
    def test_usage(self): self.assertEqual(run().returncode, 2)
    def test_real_diag_patches_pass(self):
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'xnu', 'patches')
        ps = [os.path.join(d, n) for n in sorted(os.listdir(d)) if n[:4] in ('0338', '0339', '0340', '0341', '0342', '0343', '0344')]
        self.assertTrue(ps); self.assertEqual(run(*ps).returncode, 0)
    def mkhook(self, added):
        fd, p = tempfile.mkstemp(suffix='.patch'); os.write(fd, ('--- a/bsd/kern/kdebug.c\n+++ b/bsd/kern/kdebug.c\n@@ -1 +1 @@\n' + ''.join('+%s\n' % l for l in added)).encode()); os.close(fd); self.addCleanup(os.unlink, p); return p
    def test_hook_only_accepts_drawing_hooks(self): self.assertEqual(run(self.mkhook(['#if defined(A5XELTE)', 'extern void sweet_early_phase(const char *message);', '#endif', '\tsweet_early_phase(message);'])).returncode, 0)
    def test_hook_only_rejects_other_code(self):
        r = run(self.mkhook(['\tsweet_early_phase(message);', '\tmem_size = 0;'])); self.assertEqual(r.returncode, 1); self.assertIn('mem_size', r.stdout)
    def test_real_0349_passes_after_d0045(self): self.assertEqual(run(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'xnu', 'patches', '0414-herolte-min14-phase-names.patch')).returncode, 0)
    def test_real_non_diag_patches_fail(self):
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'xnu', 'patches')
        self.assertEqual(run(os.path.join(d, '0402-herolte-drop-v2.patch')).returncode, 1)
if __name__ == '__main__': unittest.main()

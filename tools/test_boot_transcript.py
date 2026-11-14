#!/usr/bin/env python3
"""Pruebas del clasificador de transcripciones (texto sintético). python3 -I tools/test_boot_transcript.py"""
import os, sys, importlib.util, unittest, tempfile
spec = importlib.util.spec_from_file_location('tc', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'herolte-boot-transcript-check.py')); tc = importlib.util.module_from_spec(spec); spec.loader.exec_module(tc)
A = 'HEROLTE XNU LOADER\nENTRY\nBOOTARGS debug=0xc ...\nJUMP TO XNU\nXNU ENTRY\nXNU MMU ON\nDarwin Kernel Version 22.6.0\ncpus=8\ncannot mount root, errno = 6\n'


class T(unittest.TestCase):
    def test_complete_n2(self): r = tc.classify(A, True); self.assertEqual(r['resultado'], 'A'); self.assertEqual(r['prohibidos'], [])
    def test_partial_stops_at_mmu_on(self): r = tc.classify('HEROLTE XNU LOADER\nJUMP TO XNU\nXNU ENTRY\nXNU MMU ON\n'); self.assertEqual(r['resultado'], 'B'); self.assertEqual(r['etapas'][-1], 'mmu_on')
    def test_panic_is_partial(self): self.assertEqual(tc.classify('XNU ENTRY\npanic(cpu 0 caller 0x1): x\n')['resultado'], 'B')
    def test_loader_failure(self): r = tc.classify('HEROLTE XNU LOADER\nLOADER FAIL: BAD SWEETXNU PAYLOAD\nTWRP EN 30 S\n'); self.assertEqual(r['resultado'], 'C'); self.assertIn('BAD SWEETXNU PAYLOAD', r['motivo'])
    def test_empty_is_black_screen(self): self.assertEqual(tc.classify('\n  \n')['resultado'], 'D')
    def test_unrecognised_text_is_not_a_success(self): self.assertEqual(tc.classify('hola mundo\n')['resultado'], 'D')
    def test_reboot_loop(self): self.assertEqual(tc.classify('reboot\nreboot\nreboot\n')['resultado'], 'E')
    def test_forbidden_prefixes_flagged_only_for_the_minimal_variant(self):
        t = A + 'HEROLTE WIFI: the firmware\'s files after 0 ms\nHEROLTE GPU: probe\n'
        self.assertEqual(sorted(tc.classify(t, True)['prohibidos']), ['HEROLTE GPU', 'HEROLTE WIFI']); self.assertEqual(tc.classify(t, False)['prohibidos'], [])
    def test_cli_exit_codes(self):
        d = tempfile.mkdtemp(); p = os.path.join(d, 't.txt'); open(p, 'w').write(A); self.assertEqual(tc.main(['x', p, '--min']), 0)
        open(p, 'w').write('XNU ENTRY\n'); self.assertEqual(tc.main(['x', p]), 1); self.assertEqual(tc.main(['x']), 2)


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""Pruebas de herolte-trim-dd-tail.py con ficheros SINTÉTICOS (nunca toca copias reales). python3 -I tools/test_trim_dd_tail.py"""
import os, sys, tempfile, shutil, hashlib, importlib.util, unittest
spec = importlib.util.spec_from_file_location('trim', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'herolte-trim-dd-tail.py')); trim = importlib.util.module_from_spec(spec); spec.loader.exec_module(trim)
DATA = bytes(range(256)) * 40            # 10240 bytes
TAIL = b'20+0 records in\n20+0 records out\n10240 bytes (10.0KB) copied, 0.001 seconds, 9.8MB/s\n'


class T(unittest.TestCase):
    def setUp(self): self.d = tempfile.mkdtemp(prefix='trim.')
    def tearDown(self): shutil.rmtree(self.d, ignore_errors=True)
    def mk(self, name, data): p = os.path.join(self.d, name); open(p, 'wb').write(data); return p

    def test_report_only_by_default_and_apply_trims_exactly(self):
        p = self.mk('A.img', DATA + TAIL); self.assertEqual(trim.main(['x', p]), 0); self.assertEqual(os.path.getsize(p), len(DATA) + len(TAIL))
        self.assertEqual(trim.main(['x', '--apply', p]), 0); self.assertEqual(open(p, 'rb').read(), DATA)
        self.assertEqual(open(p + '.trimmed.sha256').read().split()[0], hashlib.sha256(DATA).hexdigest())

    def test_clean_image_is_left_alone(self):
        p = self.mk('B.img', DATA); self.assertEqual(trim.analyse(p)['status'], 'SIN-COLA'); trim.main(['x', '--apply', p]); self.assertEqual(open(p, 'rb').read(), DATA)

    def test_inconsistent_size_is_refused_without_touching(self):
        p = self.mk('C.img', DATA[:-5] + TAIL); self.assertEqual(trim.analyse(p)['status'], 'TAMANO-INCOHERENTE')
        self.assertEqual(trim.main(['x', '--apply', p]), 1); self.assertEqual(open(p, 'rb').read(), DATA[:-5] + TAIL)

    def test_records_mismatch_is_refused(self):
        p = self.mk('D.img', DATA + TAIL.replace(b'20+0 records out', b'19+0 records out')); self.assertEqual(trim.analyse(p)['status'], 'RECORDS-DISTINTOS')

    def test_data_that_looks_like_dd_text_in_the_middle_is_not_trimmed(self):
        p = self.mk('E.img', TAIL + DATA); self.assertEqual(trim.analyse(p)['status'], 'SIN-COLA')

    def test_directory_mode_only_img_files(self):
        self.mk('A.img', DATA + TAIL); self.mk('notes.txt', DATA + TAIL); trim.main(['x', '--apply', self.d])
        self.assertEqual(os.path.getsize(os.path.join(self.d, 'notes.txt')), len(DATA) + len(TAIL))


if __name__ == '__main__':
    unittest.main()

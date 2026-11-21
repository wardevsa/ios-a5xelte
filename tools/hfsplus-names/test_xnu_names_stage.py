#!/usr/bin/env python3
"""Pruebas de xnu_names_stage (D-0017/T-0024). Solo árboles temporales; no monta nada. python3 -I tools/hfsplus-names/test_xnu_names_stage.py"""
import os, sys, tempfile, shutil, unittest, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xnu_names_stage as s, hfs_names as h

NFC_E = 'café.txt'                 # é precompuesto: XNU lo guarda descompuesto
ASCII = 'plain.txt'
KO = '/lib/modules/%s/kernel/fs/hfsplus/hfsplus.ko.zst' % os.uname().release


class T(unittest.TestCase):
    def setUp(self): self.t = tempfile.mkdtemp(prefix='xns.')
    def tearDown(self): shutil.rmtree(self.t, ignore_errors=True)
    def touch(self, *p):
        f = os.path.join(self.t, *p); os.makedirs(os.path.dirname(f), exist_ok=True); open(f, 'w').close(); return f

    def test_plan_is_read_only_and_apply_renames_to_xnu_form(self):
        self.touch('d', NFC_E); self.touch('d', ASCII)
        before = sorted(os.listdir(os.path.join(self.t, 'd'))); p = s.plan(self.t)
        self.assertEqual(sorted(os.listdir(os.path.join(self.t, 'd'))), before)            # plan no cambia nada
        self.assertEqual([(o, n) for _, o, n in p['renames']], [(NFC_E, unicodedata.normalize('NFD', NFC_E))])
        self.assertEqual(s.apply(self.t, p), 1)
        self.assertIn(unicodedata.normalize('NFD', NFC_E), os.listdir(os.path.join(self.t, 'd'))); self.assertIn(ASCII, os.listdir(os.path.join(self.t, 'd')))

    def test_ascii_tree_is_untouched(self):
        self.touch('a', 'b.txt'); p = s.plan(self.t); self.assertEqual(p['renames'], []); self.assertEqual(s.apply(self.t, p), 0)

    def test_collision_refuses_to_apply(self):
        self.touch('d', 'café'); self.touch('d', 'café')                         # misma forma XNU
        p = s.plan(self.t); self.assertTrue(p['collisions'])
        with self.assertRaises(SystemExit): s.apply(self.t, p)
        self.assertEqual(sorted(os.listdir(os.path.join(self.t, 'd'))), sorted(['café', 'café']))

    def test_directory_that_would_change_aborts(self):
        self.touch('dé', 'x'); p = s.plan(self.t); self.assertTrue(p['dir_changes'])
        with self.assertRaises(SystemExit): s.apply(self.t, p)
        self.assertTrue(os.path.isdir(os.path.join(self.t, 'dé')))

    def test_too_long_aborts(self):
        self.touch('d', '\u01d6' * 127); p = s.plan(self.t); self.assertTrue(p['too_long'])      # 254 bytes en ext4, 381 unidades UTF-16 en forma XNU
        with self.assertRaises(SystemExit): s.apply(self.t, p)

    def test_does_not_follow_or_rename_symlinks_out_of_tree(self):
        outside = tempfile.mkdtemp(prefix='xns-out.')
        try:
            open(os.path.join(outside, NFC_E), 'w').close(); os.symlink(outside, os.path.join(self.t, 'lnk'))
            p = s.plan(self.t); self.assertEqual(os.listdir(outside), [NFC_E])
            self.assertEqual([r for r in p['renames'] if r[1] == NFC_E], [])               # no entró por el enlace
            s.apply(self.t, p); self.assertEqual(os.listdir(outside), [NFC_E])
        finally: shutil.rmtree(outside, ignore_errors=True)

    def test_colon_names_are_never_turned_into_paths(self):
        # el ':' POSIX lo convierte en '/' el hfsplus de Linux al escribir; renombrar a 'a/b' movería el fichero a un subdirectorio
        self.touch('d', 'a:b'); self.touch('d', 'caf\u00e9:x'); p = s.plan(self.t)
        self.assertEqual([(o, n) for _, o, n in p['renames']], [('caf\u00e9:x', unicodedata.normalize('NFD', 'caf\u00e9') + ':x')])
        s.apply(self.t, p); self.assertEqual(sorted(os.listdir(os.path.join(self.t, 'd'))), sorted(['a:b', unicodedata.normalize('NFD', 'caf\u00e9') + ':x']))
        self.assertEqual([e for e in os.listdir(self.t)], ['d'])

    @unittest.skipUnless(os.path.exists(KO), 'sin hfsplus.ko del kernel en ejecución')
    def test_thai_sara_am_still_needs_nodecompose(self):
        self.touch('d', 'xำ'); p = s.plan(self.t, h.linux_table(KO))                  # U+0E33: XNU lo conserva, la tabla de Linux lo descompone
        self.assertEqual(len(p['needs_nodecompose']), 1, p)

    @unittest.skipUnless(os.path.exists(KO), 'sin hfsplus.ko del kernel en ejecución')
    def test_exclude_list_names_only_the_names_that_need_nodecompose_and_deletes_nothing(self):
        self.touch('d', 'x\u0e33'); self.touch('d', NFC_E); self.touch('d', ASCII)
        out = os.path.join(tempfile.mkdtemp(prefix='xns-ex.'), 'excl.txt')
        try:
            r = s.main.__globals__['sys']; old = r.argv; r.argv = ['x', 'plan', self.t, '--ko', KO, '--exclude-list', out]
            try: s.main()
            finally: r.argv = old
            self.assertEqual(open(out, encoding='utf-8').read().split('\n')[:-1], [os.path.join('d', 'x\u0e33')])
            self.assertEqual(sorted(os.listdir(os.path.join(self.t, 'd'))), sorted(['x\u0e33', NFC_E, ASCII]))   # plan no toca nada
        finally: shutil.rmtree(os.path.dirname(out), ignore_errors=True)


if __name__ == '__main__':
    unittest.main()

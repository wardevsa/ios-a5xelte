#!/usr/bin/env python3
"""Pruebas del adaptador de nombres y de la copia del laboratorio (D-0024/T-0025). Solo árboles y manifiestos sintéticos: no monta, no usa sudo.
python3 -I tools/ios-root-lab/test_adapter.py"""
import os, sys, json, tempfile, shutil, subprocess, unittest, unicodedata, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import xnu_name_adapter as a

NFC = 'café'; NFD = unicodedata.normalize('NFD', NFC); THAI = 'xำ'
KO = '/lib/modules/%s/kernel/fs/hfsplus/hfsplus.ko.zst' % os.uname().release


def ent(path, typ='reg', **kw):
    d = dict(path=path, type=typ, uid=0, gid=0, mode=0o644, mtime_ns=None, atime_ns=None, bsd_flags=0, size=1, nlink=1, inode=1, target=None); d.update(kw); return d


class Adapter(unittest.TestCase):
    def test_component_translation(self):
        self.assertEqual(a.translate_component('plain.txt'), 'plain.txt')
        self.assertEqual(a.translate_component(NFC), NFD)
        self.assertEqual(a.translate_component('a:b'), 'a:b')                                   # el ':' lo trata Linux
        self.assertEqual(a.translate_component('bad\udcff'), 'bad\udcff')                       # bytes no UTF-8: intactos

    def test_path_translation_is_per_component(self):
        self.assertEqual(a.translate_path('d/' + NFC + '/' + NFC + ':x'), 'd/' + NFD + '/' + NFD + ':x')

    def test_manifest_translation_excludes_and_keeps_original_path(self):
        m = [ent('d', 'dir'), ent('d/' + NFC), ent('d/' + THAI), ent('d/keep')]
        out = a.translate_manifest(m, {'d/' + THAI})
        self.assertEqual([e['path'] for e in out], ['d', 'd/' + NFD, 'd/keep'])
        self.assertEqual(out[1]['path_manifest'], 'd/' + NFC)
        self.assertEqual(len(m), 4)                                                              # no muta la entrada

    def test_an_excluded_directory_excludes_its_content(self):
        out = a.translate_manifest([ent('p', 'dir'), ent('p/q'), ent('r')], {'p'}); self.assertEqual([e['path'] for e in out], ['r'])

    def test_hardlink_groups_survive_translation(self):
        m = [ent('a/' + NFC, nlink=2, inode=7), ent('b/' + NFC, nlink=2, inode=7)]
        out = a.translate_manifest(m, set()); self.assertEqual({e['inode'] for e in out}, {7}); self.assertEqual(len(out), 2)

    def test_collision_after_translation_aborts(self):
        with self.assertRaises(SystemExit): a.translate_manifest([ent('d/' + NFC), ent('d/' + NFD)], set())

    def test_symlink_targets_are_not_translated(self):
        out = a.translate_manifest([ent('l', 'lnk', target='../' + NFC)], set()); self.assertEqual(out[0]['target'], '../' + NFC)

    def test_missing_exclusion_file_aborts(self):
        with self.assertRaises(SystemExit): a.load_exclusions('/nonexistent/xnu_excluded_paths.txt')

    def test_exclusions_file_roundtrip(self):
        d = tempfile.mkdtemp(prefix='adp.')
        try:
            f = os.path.join(d, 'ex.txt'); open(f, 'w', encoding='utf-8').write('d/' + THAI + '\n\n'); self.assertEqual(a.load_exclusions(f), {'d/' + THAI})
        finally: shutil.rmtree(d, ignore_errors=True)

    def test_cli_writes_anchored_rsync_exclude_file(self):
        d = tempfile.mkdtemp(prefix='adp.')
        try:
            os.makedirs(os.path.join(d, 'out')); open(os.path.join(d, 'out', 'xnu_excluded_paths.txt'), 'w', encoding='utf-8').write('d/' + THAI + '\n')
            env = dict(os.environ, IOS_ROOT_LAB=d); r = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'xnu_name_adapter.py'), 'rsync-exclude-file', os.path.join(d, 'out')], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr); self.assertEqual(open(r.stdout.strip(), encoding='utf-8').read(), '/d/' + THAI + '\n')
        finally: shutil.rmtree(d, ignore_errors=True)


class Q3libIsTheSinglePoint(unittest.TestCase):
    def setUp(self):
        self.lab = tempfile.mkdtemp(prefix='lab.'); os.makedirs(os.path.join(self.lab, 'out'))
        with open(os.path.join(self.lab, 'out', 'man_os.jsonl'), 'w', encoding='utf-8') as f:
            for e in (ent('d', 'dir'), ent('d/' + NFC), ent('d/' + THAI)): f.write(json.dumps(e) + '\n')
        open(os.path.join(self.lab, 'out', 'xnu_excluded_paths.txt'), 'w', encoding='utf-8').write('d/' + THAI + '\n')

    def tearDown(self): shutil.rmtree(self.lab, ignore_errors=True)

    def run_py(self, code, **env):
        return subprocess.run([sys.executable, '-I', '-c', 'import sys; sys.path.insert(0, %r); ' % HERE + code], env=dict(IOS_ROOT_LAB=self.lab, PATH=os.environ['PATH'], **env), capture_output=True, text=True)

    def test_load_manifest_returns_xnu_names_without_exclusions(self):
        r = self.run_py('import q3lib; print(json.dumps([d["path"] for d in q3lib.load_manifest("os")], ensure_ascii=True))'.replace('json.dumps', '__import__("json").dumps'))
        self.assertEqual(r.returncode, 0, r.stderr); self.assertEqual(json.loads(r.stdout), ['d', 'd/' + NFD])

    def test_without_lab_env_it_refuses_instead_of_guessing_a_path(self):
        r = subprocess.run([sys.executable, '-I', '-c', 'import sys; sys.path.insert(0, %r); import q3lib' % HERE], env={'PATH': os.environ['PATH']}, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)

    def test_no_absolute_lab_or_home_paths_in_the_copies(self):
        for f in os.listdir(HERE):
            if f.endswith(('.py', '.sh')) and f != 'test_adapter.py':
                s = open(os.path.join(HERE, f), encoding='utf-8').read()
                for bad in ('/home/pioxi', '/tmp/claude', 'scratchpad'): self.assertNotIn(bad, s, '%s contiene %s' % (f, bad))

    def test_siblings_are_called_through_TOOLS_not_through_the_lab_tools_dir(self):
        for f in ('populate_image.sh', 'verify_image.sh', 'img_common.sh'):
            self.assertNotIn('$R3/tools', open(os.path.join(HERE, f), encoding='utf-8').read(), f)

    def test_python_and_shell_copies_parse(self):
        for f in os.listdir(HERE):
            p = os.path.join(HERE, f)
            if f.endswith('.py'): compile(open(p, encoding='utf-8').read(), p, 'exec')
            if f.endswith('.sh'): self.assertEqual(subprocess.run(['bash', '-n', p]).returncode, 0, f)

    def test_the_populate_script_excludes_through_the_adapter(self):
        s = open(os.path.join(HERE, 'populate_image.sh'), encoding='utf-8').read()
        self.assertIn('--exclude-from=$XNU_EXCL', s); self.assertIn('xnu_name_adapter.py rsync-exclude-file', s)


@unittest.skipUnless(os.path.exists(KO), 'sin hfsplus.ko del kernel en ejecución')
class LinuxStability(unittest.TestCase):
    def test_translated_names_are_stable_under_linux_default_mount_except_thai_sara_am(self):
        sys.path.insert(0, os.path.join(HERE, '..', 'hfsplus-names')); import hfs_names as h
        t = h.linux_table(KO); names = [NFC, 'naïve', 'Ångström', '가나', 'xำ']
        unstable = [n for n in names if h.linux_nfd(a.translate_component(n), t) != a.translate_component(n)]
        self.assertEqual(unstable, ['xำ'])


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""Types and structures: plutil_lite changes ONE key and everything else must come out equal, with the same types."""
import datetime, os, plistlib, subprocess, sys, tempfile, unittest

PL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plutil_lite.py")
RICH = {'s': 'texto é中', 'i': 7, 'big': 2 ** 40, 'neg': -3, 'f': 1.5, 't': True, 'f2': False, 'data': b'\x00\x01\xff',
        'date': datetime.datetime(2024, 5, 6, 7, 8, 9), 'arr': [1, 'a', {'k': [True, b'z']}], 'dict': {'a': {'b': {'c': 1}}},
        'tochange': 'old'}


def run(*args):
    return subprocess.run([sys.executable, PL, *args], capture_output=True, text=True)


def same_types(a, b, path=''):
    assert type(a) is type(b), (path, type(a), type(b))
    if isinstance(a, dict):
        assert a.keys() == b.keys(), path
        for k in a: same_types(a[k], b[k], path + '/' + k)
    elif isinstance(a, list):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)): same_types(x, y, '%s[%d]' % (path, i))


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='plutil-lite-test.')
        self.f = os.path.join(self.d, 'x.plist')

    def write(self, data, fmt):
        with open(self.f, 'wb') as fh: plistlib.dump(data, fh, fmt=fmt)

    def read(self):
        with open(self.f, 'rb') as fh: raw = fh.read()
        return plistlib.loads(raw), (plistlib.FMT_BINARY if raw.startswith(b'bplist') else plistlib.FMT_XML)

    def test_replace_changes_one_key_everything_else_equal_and_same_types(self):
        for fmt in (plistlib.FMT_BINARY, plistlib.FMT_XML):
            self.write(RICH, fmt)
            before, _ = self.read()
            self.assertEqual(run('-replace', 'tochange', '-string', 'new', self.f).returncode, 0)
            after, f2 = self.read()
            self.assertEqual(f2, fmt, 'format kept')
            self.assertEqual(after.pop('tochange'), 'new'); before.pop('tochange')
            self.assertEqual(before, after); same_types(before, after)
            self.assertIs(after['t'], True); self.assertIs(after['f2'], False); self.assertIs(type(after['i']), int)

    def test_value_types_written(self):
        self.assertEqual(run('-create', 'xml1', self.f).returncode, 0)
        for args in (('a', '-bool', 'YES'), ('b', '-bool', 'NO'), ('c', '-integer', '11'), ('d', '-string', '480w-853h@3x~iphone'),
                     ('e', '-json', '{"com.apple.purplebuddy":100}')):
            self.assertEqual(run('-replace', *args, self.f).returncode, 0, args)
        d, _ = self.read()
        self.assertEqual(d, {'a': True, 'b': False, 'c': 11, 'd': '480w-853h@3x~iphone', 'e': {'com.apple.purplebuddy': 100}})
        self.assertIs(d['a'], True); self.assertIs(type(d['c']), int)
        xml = open(self.f).read()
        self.assertIn('<key>a</key>\n\t<true/>', xml); self.assertIn('<key>c</key>\n\t<integer>11</integer>', xml)
        self.assertIn('<integer>100</integer>', xml)   # JSON numbers become plist integers, as with Apple's plutil

    def test_convert_xml1_keeps_content_and_types(self):
        self.write(RICH, plistlib.FMT_BINARY)
        before, _ = self.read()
        self.assertEqual(run('-convert', 'xml1', self.f).returncode, 0)
        after, fmt = self.read()
        self.assertEqual(fmt, plistlib.FMT_XML); self.assertEqual(before, after); same_types(before, after)

    def test_file_mode_kept_and_no_temp_files_left(self):
        self.write({'k': 1}, plistlib.FMT_BINARY); os.chmod(self.f, 0o640)
        self.assertEqual(run('-replace', 'k', '-integer', '2', self.f).returncode, 0)
        self.assertEqual(os.stat(self.f).st_mode & 0o777, 0o640)
        self.assertEqual(os.listdir(self.d), ['x.plist'])

    def test_failures_do_not_touch_the_file(self):
        self.write({'k': 1}, plistlib.FMT_XML)
        raw = open(self.f, 'rb').read()
        for args in (('-replace', 'k', '-bool', 'maybe'), ('-replace', 'k', '-integer', '1x'), ('-replace', 'k', '-json', '{'),
                     ('-replace', 'k', '-data', 'abc'), ('-replace', 'k', '-float', '1.5'), ('-replace', 'a.b', '-string', 'x'),
                     ('-convert', 'binary1'), ('-create', 'xml1'), ('-replace', 'k', '-string')):
            r = run(*args, self.f)
            self.assertNotEqual(r.returncode, 0, args)
            self.assertEqual(open(self.f, 'rb').read(), raw, args)
        self.assertEqual(os.listdir(self.d), ['x.plist'])

    def test_top_level_array_is_refused(self):
        self.write([1, 2], plistlib.FMT_XML)
        self.assertNotEqual(run('-replace', 'k', '-string', 'x', self.f).returncode, 0)

    def test_missing_and_corrupt_file(self):
        self.assertNotEqual(run('-replace', 'k', '-string', 'x', os.path.join(self.d, 'nope.plist')).returncode, 0)
        open(self.f, 'wb').write(b'not a plist')
        self.assertNotEqual(run('-replace', 'k', '-string', 'x', self.f).returncode, 0)
        self.assertEqual(open(self.f, 'rb').read(), b'not a plist')


if __name__ == '__main__':
    unittest.main(verbosity=1)

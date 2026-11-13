#!/usr/bin/env python3
"""Tests of the XNU/Linux HFS+ name models. Synthetic and read-only: nothing is mounted, no image is opened.
Differential tests need gcc and the CI build tree (buildtree.tgz) to compile XNU's own utfconv; the evidence regression needs the T04-R audit
catalog. Both are skipped (not passed) when absent.
    python3 -W ignore tools/hfsplus-names/test_hfs_names.py"""
import glob, json, os, random, shutil, subprocess, sys, tempfile, unittest, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import hfs_names as H  # noqa: E402

BUILDTREE = os.path.expanduser('~/HackiOS/builds/device-day/artifacts/buildtree-0332-fork-8d1cf43/buildtree.tgz')
KO = '/lib/modules/%s/kernel/fs/hfsplus/hfsplus.ko.zst' % os.uname().release
AUDIT = glob.glob('/tmp/claude-1000/*/*/scratchpad/t04r/audit/catalog.jsonl')
OUT = glob.glob('/tmp/claude-1000/*/*/scratchpad/t04r/r3/out')


def build_harness():
    if not (os.path.exists(BUILDTREE) and shutil.which('gcc') and shutil.which('tar')): return None
    d = tempfile.mkdtemp(prefix='xnu-nfd.')
    r = subprocess.run([os.path.join(HERE, 'build_xnu_nfd.sh'), BUILDTREE, d], capture_output=True, text=True)
    return os.path.join(d, 'xnu_nfd') if r.returncode == 0 else None


HARNESS = build_harness()


def xnu_real(strings):
    p = subprocess.run([HARNESS], input='\n'.join(strings) + '\n', capture_output=True, text=True, check=True)
    out = []
    for line in p.stdout.splitlines():
        f = line.split(); out.append(None if f[0] != '0' else ''.join(chr(int(x, 16)) for x in f[1:]))
    return out


class Models(unittest.TestCase):
    def test_xnu_model_known_vectors(self):
        self.assertEqual(H.xnu_nfd('café'), 'café')
        self.assertEqual(H.xnu_nfd('إ'), 'إ')                     # alef with hamza below
        self.assertEqual(H.xnu_nfd('șț'), 'șț')             # Romanian comma-below letters
        self.assertEqual(H.xnu_nfd('ί'), 'ί')                     # Greek iota with tonos -> U+0301
        self.assertEqual(H.xnu_nfd('ำ'), 'ำ')                           # Thai SARA AM is NOT decomposed by XNU
        self.assertEqual(H.xnu_nfd('Ω'), 'Ω')                           # excluded range: OHM SIGN stays
        self.assertEqual(H.xnu_nfd('각'), '각')               # Hangul syllable
        self.assertEqual(H.xnu_nfd('ạ́'), 'ạ́')             # canonical ordering of marks
        self.assertEqual(H.xnu_nfd('plain ascii.txt'), 'plain ascii.txt')

    def test_xnu_model_is_idempotent_and_ascii_safe(self):
        rnd = random.Random(7)
        for _ in range(500):
            s = ''.join(chr(rnd.choice([rnd.randrange(0x20, 0x7f), rnd.randrange(0xc0, 0x500), rnd.randrange(0x600, 0x700), 0x2126, 0x0301, 0x0323]))
                        for _ in range(rnd.randrange(1, 12)))
            self.assertEqual(H.xnu_nfd(H.xnu_nfd(s)), H.xnu_nfd(s))
        self.assertEqual(H.hfs_component('a:b'), 'a/b')                            # ':' in a POSIX name is '/' on HFS+

    def test_collisions_and_length(self):
        self.assertEqual(H.find_collisions(['é', 'é', 'x']), [('é', 'é')])      # NFC and NFD of the same name collapse
        self.assertEqual(H.find_collisions(['a', 'b', 'é', 'e']), [])
        self.assertFalse(H.too_long('a' * 255)); self.assertTrue(H.too_long('a' * 256)); self.assertTrue(H.too_long('é' * 128))   # 128 e-acute = 256 units


@unittest.skipUnless(HARNESS, 'XNU utfconv harness not built (needs gcc and the CI build tree)')
class DifferentialAgainstXnu(unittest.TestCase):
    def test_every_bmp_character(self):
        cps = [c for c in range(0x80, 0x10000) if not 0xD800 <= c <= 0xDFFF]
        real = xnu_real([chr(c) for c in cps]); bad = []
        for c, r in zip(cps, real):
            if r is None: continue                                                  # U+FFFE/U+FFFF: XNU rejects them
            if H.xnu_nfd(chr(c)) != r: bad.append(c)
        self.assertEqual([hex(c) for c in bad], ['0x2400'])                         # U+2400 is XNU's alternative NUL (maps to '/'): an API artefact

    def test_colon_is_mapped_by_xnu_itself_and_sara_am_is_kept(self):
        r = xnu_real(['a:b', 'x\u00e9:y', '\u0e04\u0e33', '\u0625', '\u03af'])
        self.assertEqual(r, ['a/b', 'xe\u0301/y', '\u0e04\u0e33', '\u0627\u0655', '\u03b9\u0301'])   # altslash ':' as in hfs_catalog.c:3530; U+0E33 untouched

    def test_xnu_rejects_only_the_two_noncharacters_in_the_bmp(self):
        r = xnu_real([chr(0xfffe), chr(0xffff), chr(0xfeff)]); self.assertEqual([x is None for x in r], [True, True, False])

    def test_random_strings_with_combining_marks(self):
        rnd = random.Random(1); pool = list(range(0x41, 0x7b)) + list(range(0xc0, 0x180)) + list(range(0x300, 0x340)) + [0x623, 0x625, 0x627, 0x654, 0x655,
              0x219, 0x21b, 0x3ac, 0x3af, 0x385, 0xe33, 0xe4d, 0xe32, 0xf71, 0xf72, 0xf73, 0x2126, 0xac01, 0x1100, 0x1161, 0x11a8, 0x95c, 0x921, 0x93c]
        strs = [''.join(chr(rnd.choice(pool)) for _ in range(rnd.randrange(1, 10))) for _ in range(3000)]
        real = xnu_real(strs)
        for s, r in zip(strs, real):
            self.assertEqual(H.xnu_nfd(s), r, ' '.join('%04X' % ord(c) for c in s))


@unittest.skipUnless(os.path.exists(KO), 'no hfsplus.ko of the running kernel')
class LinuxTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.T = H.linux_table(KO)

    def test_known_linux_results(self):
        L = lambda s: H.linux_nfd(s, self.T)
        self.assertEqual(L('é'), 'é')                                    # the common case works (why the 1-name mini tests passed)
        self.assertEqual(L('إ'), 'إ')                                     # Linux leaves alef-with-hamza composed ...
        self.assertEqual(L('ș'), 'ș')                                     # ... and the Romanian comma-below letters
        self.assertEqual(L('ί'), 'ι̍')                               # Greek tonos becomes U+030D, not U+0301
        self.assertEqual(L('ำ'), 'ํา')                               # Thai SARA AM is decomposed, which XNU does not do
        self.assertEqual(L('각'), '각')

    def test_linux_and_xnu_differ_exactly_where_the_audit_found(self):
        for ch in ('أ', 'إ', 'ș', 'ț', 'ά', 'ί', 'ำ', 'ཱི'):
            self.assertNotEqual(H.linux_nfd(ch, self.T), H.xnu_nfd(ch), hex(ord(ch)))
        for ch in ('é', 'ü', 'À', 'ñ', 'ç', '각'):
            self.assertEqual(H.linux_nfd(ch, self.T), H.xnu_nfd(ch), hex(ord(ch)))

    @unittest.skipUnless(HARNESS, 'needs the XNU harness')
    def test_number_of_bmp_characters_that_differ(self):
        cps = [c for c in range(0x80, 0x10000) if not 0xD800 <= c <= 0xDFFF]; real = xnu_real([chr(c) for c in cps])
        n = sum(1 for c, r in zip(cps, real) if r is not None and H.linux_nfd(chr(c), self.T) != r)
        self.assertEqual(n, 144)                                                    # recorded 2026-11-13; a different kernel table would change it


@unittest.skipUnless(AUDIT and OUT and os.path.exists(KO), 'T04-R audit catalog or hfsplus.ko not available')
class EvidenceRegression(unittest.TestCase):
    def test_linux_table_explains_every_name_on_the_lab_image_and_xnu_differs_in_32(self):
        T = H.linux_table(KO)
        recs = [json.loads(l) for l in open(AUDIT[0])]
        disk = set(bytes.fromhex(r['raw']).decode('utf-16-be', 'surrogatepass') for r in recs)
        names = set()
        for v in ('os', 'systemos', 'appos'):
            for l in open('%s/man_%s.jsonl' % (OUT[0], v)):
                last = json.loads(l)['path'].rpartition('/')[2]
                if any(ord(c) > 127 for c in last): names.add(last.replace(':', '/'))
        self.assertEqual(len(names), 329)
        self.assertTrue(all(H.linux_nfd(n, T) in disk for n in names))              # 329 of 329: Linux's table is the whole story
        missing_in_xnu_form = [n for n in names if H.xnu_nfd(n) not in disk]
        self.assertEqual(len(missing_in_xnu_form), 32)
        self.assertEqual(H.find_collisions(sorted(names)), [])

    def test_the_32_differences_by_equivalence_class(self):
        import unicodedata as u
        T = H.linux_table(KO); recs = [json.loads(l) for l in open(AUDIT[0])]
        names = set()
        for v in ('os', 'systemos', 'appos'):
            for l in open('%s/man_%s.jsonl' % (OUT[0], v)):
                last = json.loads(l)['path'].rpartition('/')[2]
                if any(ord(c) > 127 for c in last): names.add(last.replace(':', '/'))
        kinds = {'canonical': 0, 'compat_only': 0, 'different': 0}
        for n in names:
            L, X = H.linux_nfd(n, T), H.xnu_nfd(n)
            if L == X: continue
            if u.normalize('NFC', L) == u.normalize('NFC', X): kinds['canonical'] += 1
            elif u.normalize('NFKC', L) == u.normalize('NFKC', X): kinds['compat_only'] += 1
            else: kinds['different'] += 1
        # Arabic (9) + Romanian (6) differ in normalisation LEVEL only; Thai (2) by a compatibility decomposition; Greek (15): U+030D is another character
        self.assertEqual(kinds, {'canonical': 15, 'compat_only': 2, 'different': 15})


if __name__ == '__main__':
    unittest.main(verbosity=1)

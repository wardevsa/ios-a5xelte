#!/usr/bin/env python3
"""Pruebas de herolte-flash-boot.sh con un adb FALSO (un script de Python que emula TWRP). NUNCA se llama al adb real ni se toca el teléfono.
Necesita el BOOT original verificado (E-0009) en su ruta habitual; si no está, las pruebas se omiten. python3 -I tools/test_flash_boot.py"""
import os, sys, re, json, shutil, subprocess, tempfile, hashlib, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
STOCK = os.path.expanduser('~/HackiOS/backups/device-herolte/2026-11-12/BOOT.img')
FAKE_ADB = r'''#!/usr/bin/env python3
import sys, os, json, hashlib, shutil
S = os.environ['FAKE_DIR']; st = json.load(open(S + '/state.json'))
def save(): json.dump(st, open(S + '/state.json', 'w'))
open(S + '/calls.log', 'a').write(' '.join(sys.argv[1:]) + '\n')
a = sys.argv[1:]
def sha(p, n=None):
    d = open(p, 'rb').read(); return hashlib.sha256(d if n is None else d[:n]).hexdigest()
if a[0] == 'devices':
    print('List of devices attached'); [print('%s\t%s' % (d, 'recovery')) for d in st['devices']]
elif a[0] == 'push':
    shutil.copy(a[1], S + '/pushed.img'); print('1 file pushed')
elif a[0] == 'shell':
    c = a[1]
    if c.startswith('readlink -f'): print(st['bootlink'])
    elif c.startswith('blockdev'): print(st['bootsize'])
    elif 'dev/block/sda3' in c: print(st['efs'] + '  -'); st['efs_reads'] = st.get('efs_reads', 0) + 1; save() if True else None;
    elif c.startswith('sha256sum /tmp/boot-new.img'): print(sha(S + '/pushed.img') if not st.get('lie_hash') else '0' * 64, ' /tmp/boot-new.img')
    elif c.startswith('dd if=/tmp/boot-new.img'):
        d = open(S + '/pushed.img', 'rb').read()
        if st.get('corrupt'): d = d[:-1] + bytes([d[-1] ^ 1])
        open(S + '/boot.bin', 'wb').write(d)
        if st.get('efs_changes'): st['efs'] = 'f' * 64; save()
    elif c.startswith('head -c'):
        n = int(c.split()[2]); print(sha(S + '/boot.bin', n), ' -')
    else: print('comando no previsto: ' + c, file=sys.stderr); sys.exit(9)
else: sys.exit(9)
'''


@unittest.skipUnless(os.path.exists(STOCK), 'sin el BOOT original verificado de E-0009')
class Flash(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp(prefix='flash.'); self.r = self.t + '/repo'; os.makedirs(self.r + '/tools'); self.f = self.t + '/fake'; os.makedirs(self.f)
        shutil.copytree(REPO + '/governance', self.r + '/governance', ignore=shutil.ignore_patterns('__pycache__'))
        for n in ('governance.py', 'herolte-flash-boot.sh'): shutil.copy(REPO + '/tools/' + n, self.r + '/tools/' + n)
        shutil.copy(REPO + '/AGENTS.md', self.r)
        self.img = self.t + '/img.bin'; open(self.img, 'wb').write(os.urandom(1 << 20)); self.sha = hashlib.sha256(open(self.img, 'rb').read()).hexdigest()
        open(self.f + '/adb', 'w').write(FAKE_ADB); os.chmod(self.f + '/adb', 0o755)
        self.state(devices=['SERIAL1'], bootlink='/dev/block/sda5', bootsize='41943040', efs='a' * 64)

    def tearDown(self): shutil.rmtree(self.t, ignore_errors=True)

    def state(self, **kw):
        p = self.f + '/state.json'; st = json.load(open(p)) if os.path.exists(p) else {}; st.update(kw); json.dump(st, open(p, 'w'))

    def authorize(self):
        with open(self.r + '/governance/data/decisions.toml', 'a') as o:
            o.write('\n[[decision]]\nid = "D-9001"\ntitle = "t"\ndate = "2026-11-14"\nscope = "operation"\nstatus = "APPROVED"\nproposer = "ingeniero"\napproved_by = "director"\napproval_date = "2026-11-14"\napproval_ref = "prueba"\nrationale = "r"\nreversal = "x"\nauthorizes = ["device-write-boot", "device-read"]\nvalid_until = "2099-01-01"\n')
        p = self.r + '/governance/data/tasks.toml'; t = open(p).read(); i = t.index('id = "T-0012"'); j = t.index('[[task]]', i)
        blk = t[i:j].rstrip('\n') + '\nauthorization_ref = "D-9001"\n\n'; open(p, 'w').write(t[:i] + blk + t[j:])

    def run_flash(self, *extra, sha=None):
        env = dict(os.environ, ADB=self.f + '/adb', FAKE_DIR=self.f)
        return subprocess.run(['bash', self.r + '/tools/herolte-flash-boot.sh', self.img, sha or self.sha] + list(extra), capture_output=True, text=True, env=env)

    def calls(self): return open(self.f + '/calls.log').read().splitlines() if os.path.exists(self.f + '/calls.log') else []

    def test_dry_run_never_calls_adb(self):
        r = self.run_flash(); self.assertEqual(r.returncode, 0, r.stderr); self.assertIn('ENSAYO', r.stdout); self.assertEqual(self.calls(), [])

    def test_execute_is_refused_without_a_recorded_authorization_and_adb_is_never_called(self):
        r = self.run_flash('--execute'); self.assertNotEqual(r.returncode, 0); self.assertIn('NO registra una autorización', r.stderr); self.assertEqual(self.calls(), [])
        self.assertFalse(os.path.exists(self.f + '/boot.bin'))

    def test_wrong_hash_is_refused_before_anything(self):
        self.authorize(); r = self.run_flash('--execute', sha='0' * 64); self.assertNotEqual(r.returncode, 0); self.assertEqual(self.calls(), [])

    def test_image_too_big_is_refused(self):
        open(self.img, 'wb').write(b'x' * (41943040 + 1)); sha = hashlib.sha256(open(self.img, 'rb').read()).hexdigest()
        self.authorize(); r = self.run_flash('--execute', sha=sha); self.assertNotEqual(r.returncode, 0); self.assertIn('no cabe', r.stderr); self.assertEqual(self.calls(), [])

    def test_successful_write_with_authorization(self):
        self.authorize(); r = self.run_flash('--execute'); self.assertEqual(r.returncode, 0, r.stderr); self.assertIn('OK: BOOT escrito', r.stdout)
        self.assertEqual(open(self.f + '/boot.bin', 'rb').read(), open(self.img, 'rb').read())
        self.assertTrue(all('sda3' not in c or 'of=' not in c for c in self.calls()))               # EFS: nunca con of=
        self.assertEqual(sum('of=/dev/block/platform/155a0000.ufs/by-name/BOOT' in c for c in self.calls()), 1)

    def test_wrong_partition_mapping_aborts_before_pushing(self):
        self.authorize(); self.state(bootlink='/dev/block/sda6'); r = self.run_flash('--execute'); self.assertNotEqual(r.returncode, 0)
        self.assertFalse(any(c.startswith('push') for c in self.calls())); self.assertFalse(os.path.exists(self.f + '/boot.bin'))

    def test_wrong_size_aborts(self):
        self.authorize(); self.state(bootsize='1234'); r = self.run_flash('--execute'); self.assertNotEqual(r.returncode, 0); self.assertFalse(os.path.exists(self.f + '/boot.bin'))

    def test_two_devices_abort(self):
        self.authorize(); self.state(devices=['A', 'B']); r = self.run_flash('--execute'); self.assertNotEqual(r.returncode, 0); self.assertFalse(os.path.exists(self.f + '/boot.bin'))

    def test_hash_on_the_phone_must_match_before_writing(self):
        self.authorize(); self.state(lie_hash=True); r = self.run_flash('--execute'); self.assertNotEqual(r.returncode, 0); self.assertFalse(os.path.exists(self.f + '/boot.bin'))

    def test_readback_mismatch_is_reported_with_the_rollback_pointer(self):
        self.authorize(); self.state(corrupt=True); r = self.run_flash('--execute'); self.assertNotEqual(r.returncode, 0); self.assertIn('LECTURA DE VUELTA', r.stderr); self.assertIn('S7GE_ROLLBACK_PLAN', r.stderr)

    def test_efs_change_is_detected(self):
        self.authorize(); self.state(efs_changes=True); r = self.run_flash('--execute'); self.assertNotEqual(r.returncode, 0); self.assertIn('EFS CAMBIÓ', r.stderr)

    def test_expected_efs_hash_is_enforced_before_writing(self):
        self.authorize(); env = dict(os.environ, ADB=self.f + '/adb', FAKE_DIR=self.f, EFS_SHA256='b' * 64)
        r = subprocess.run(['bash', self.r + '/tools/herolte-flash-boot.sh', self.img, self.sha, '--execute'], capture_output=True, text=True, env=env)
        self.assertNotEqual(r.returncode, 0); self.assertFalse(os.path.exists(self.f + '/boot.bin'))

    def test_the_script_never_writes_anything_but_boot(self):
        s = open(REPO + '/tools/herolte-flash-boot.sh').read()
        self.assertEqual(len(re.findall(r'\bof=', s)), 2)                                           # una en el plan y una en la ejecución, ambas a $BOOTDEV
        self.assertNotIn('of=/dev/block/sda3', s); self.assertNotIn('RECOVERY', s.replace('S7GE_ROLLBACK_PLAN', ''))


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""Pruebas de herolte-backup-partition.py con un adb FALSO (lee de un fichero local; una desconexión y un trozo corrupto inyectados)."""
import hashlib, os, stat, subprocess, sys, tempfile, unittest, json
T = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'herolte-backup-partition.py')
FAKE = r'''#!/usr/bin/env python3
import os, sys, re, subprocess, hashlib
img, flag = os.environ['FAKE_IMG'], os.environ['FAKE_FLAG']
a = sys.argv[1:]
def blk(cmd):
    m = re.search(r'skip=(\d+) count=(\d+)', cmd); sk, ct = int(m.group(1)), int(m.group(2))
    d = open(img, 'rb'); d.seek(sk * 4096); return d.read(ct * 4096), sk
if a[0] == 'devices': print('List of devices attached\nFAKE\trecovery'); sys.exit(0)
if a[0] == 'reconnect': sys.exit(0)
if a[0] == 'shell' and 'getsize64' in a[1]: print(os.path.getsize(img)); sys.exit(0)
if a[0] == 'shell' and 'sha256sum' in a[1]:
    data, sk = blk(a[1]); print(hashlib.sha256(data).hexdigest() + '  -'); sys.exit(0)
if a[0] == 'exec-out':
    data, sk = blk(a[1])
    if sk == 2 * 32 and not os.path.exists(flag): open(flag, 'w').write('x'); data = data[:-1] + bytes([data[-1] ^ 1])   # un trozo corrupto, solo la primera vez
    sys.stdout.buffer.write(data); sys.exit(0)
sys.exit(1)
'''
class B(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.img = os.path.join(self.d, 'part.bin')
        open(self.img, 'wb').write(os.urandom(4096 * 100 + 4096 * 7))        # 107 unidades; trozo de 32 unidades (0,125 MiB)
        self.adb = os.path.join(self.d, 'adb'); open(self.adb, 'w').write(FAKE); os.chmod(self.adb, 0o755)
        self.env = dict(os.environ, BACKUP_TRANSPORT='exec', ADB=self.adb, FAKE_IMG=self.img, FAKE_FLAG=os.path.join(self.d, 'flag'))
    def run_(self, out): return subprocess.run([sys.executable, T, 'X', '/dev/block/fake', out, '--chunk-kib', '128'], env=self.env, capture_output=True, text=True)
    def test_copy_matches_and_corrupt_chunk_is_retried(self):
        # trozos de 128 KiB = 32 unidades: 4 trozos; el de skip=64 llega corrupto la primera vez y debe reintentarse
        out = os.path.join(self.d, 'o.img'); r = self.run_(out)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(open(out, 'rb').read(), open(self.img, 'rb').read())
        self.assertEqual(open(out + '.sha256').read().split()[0], hashlib.sha256(open(self.img, 'rb').read()).hexdigest())
        self.assertTrue(os.path.exists(os.path.join(self.d, 'flag')), 'el trozo corrupto no llegó a inyectarse')
        self.assertIn('intento 1', r.stdout)
    def test_resume_skips_done_chunks_and_rejects_mismatch(self):
        out = os.path.join(self.d, 'o.img'); self.assertEqual(self.run_(out).returncode, 0)
        st = json.load(open(out + '.state')); st['size'] += 4096; json.dump(st, open(out + '.state', 'w'))
        r = self.run_(out); self.assertEqual(r.returncode, 2)
    def test_no_write_commands_are_ever_used(self):
        src = open(T).read()
        for bad in ('of=', 'push', 'mkfs', 'wipe', 'rm ', 'mount'): self.assertNotIn(bad, src.replace("'adb'", ''))
if __name__ == '__main__': unittest.main()

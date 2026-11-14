#!/usr/bin/env python3
"""Pruebas de herolte-write-userdata.py con un adb FALSO: un disco de fichero, un listener TCP que hace de `nc -l | dd`, un trozo corrupto inyectado."""
import hashlib, json, os, stat, subprocess, sys, tempfile, unittest
T = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'herolte-write-userdata.py')
FAKE = r'''#!/usr/bin/env python3
import os, sys, re, socket, hashlib
disk, flag = os.environ['FAKE_DISK'], os.environ['FAKE_FLAG']
a = sys.argv[1:]
def out(s): sys.stdout.write(s + "\n"); sys.exit(0)
if a[0] == 'devices': out('List of devices attached\nFAKE\trecovery')
if a[0] in ('reconnect', 'forward'): sys.exit(0)
cmd = a[1] if len(a) > 1 else ''
if a[0] == 'shell':
    if cmd.startswith('killall'): sys.exit(0)
    if cmd.startswith('readlink'): out('/dev/block/' + os.environ.get('FAKE_BLOCK', 'sda18'))
    if 'getsize64' in cmd: out(str(os.path.getsize(disk)))
    if cmd.startswith('cat /proc/mounts'): out(os.environ.get('FAKE_MOUNTS', 'rootfs / rootfs rw 0 0'))
    m = re.search(r'nc -l -p (\d+) \| dd of=(\S+) bs=4096 seek=(\d+) count=(\d+)', cmd)
    if m:
        port, target, seek, count = int(m.group(1)), m.group(2), int(m.group(3)), int(m.group(4))
        s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(('127.0.0.1', port)); s.listen(1)
        c, _ = s.accept(); buf = b''
        while True:
            b = c.recv(1 << 20)
            if not b: break
            buf += b
        c.close(); s.close()
        if target == '/dev/null': sys.exit(0)
        if seek == 256 and not os.path.exists(flag): open(flag, 'w').write('x'); buf = buf[:-1] + bytes([buf[-1] ^ 1])
        with open(disk, 'r+b') as f: f.seek(seek * 4096); f.write(buf[:count * 4096])
        sys.exit(0)
    m = re.search(r'dd if=\S+ bs=(\d+) (?:skip=(\d+) )?count=(\d+) 2>/dev/null \| sha256sum', cmd)
    if m:
        bs, skip, count = int(m.group(1)), int(m.group(2) or 0), int(m.group(3))
        with open(disk, 'rb') as f: f.seek(skip * bs); out(hashlib.sha256(f.read(count * bs)).hexdigest() + '  -')
sys.exit(1)
'''
class W(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.img = os.path.join(self.d, 'root.img'); self.disk = os.path.join(self.d, 'disk.bin')
        data = os.urandom(4096 * 700 + 4096 * 3)                       # ~2,7 MiB: trozos de 1 MiB = 256 unidades (3 trozos); el 2.º (seek=256) llega corrupto la 1.ª vez
        open(self.img, 'wb').write(data); self.sha = hashlib.sha256(data).hexdigest()
        open(self.disk, 'wb').write(b'\xaa' * (4096 * 1024))            # "USERDATA": 4 MiB de basura de Android
        self.adb = os.path.join(self.d, 'adb'); open(self.adb, 'w').write(FAKE); os.chmod(self.adb, 0o755)
        self.env = dict(os.environ, ADB=self.adb, FAKE_DISK=self.disk, FAKE_FLAG=os.path.join(self.d, 'flag'), USERDATA_DEV='/dev/block/fake/USERDATA', USERDATA_BLOCK='sda18', USERDATA_SIZE=str(os.path.getsize(self.disk)))
    def run_(self, *extra, sha=None, env=None):
        return subprocess.run([sys.executable, T, self.img, sha or self.sha, '--chunk-mib', '1', '--port', '5589', *extra], env=dict(self.env, **(env or {})), capture_output=True, text=True, timeout=120)
    def test_rehearsal_writes_nothing(self):
        before = open(self.disk, 'rb').read(); r = self.run_(); self.assertEqual(r.returncode, 0, r.stdout + r.stderr); self.assertIn('ENSAYO', r.stdout); self.assertEqual(open(self.disk, 'rb').read(), before)
    def test_wrong_hash_aborts_before_anything(self):
        before = open(self.disk, 'rb').read(); r = self.run_('--execute', '--no-gate', sha='0' * 64); self.assertEqual(r.returncode, 2); self.assertEqual(open(self.disk, 'rb').read(), before)
    def test_without_authorization_the_gate_refuses(self):
        before = open(self.disk, 'rb').read(); r = self.run_('--execute', '--task', 'T-9999'); self.assertEqual(r.returncode, 4, r.stdout + r.stderr); self.assertEqual(open(self.disk, 'rb').read(), before)
    def test_wrong_partition_or_mounted_aborts(self):
        before = open(self.disk, 'rb').read()
        self.assertEqual(self.run_('--execute', '--no-gate', env={'FAKE_BLOCK': 'sda5'}).returncode, 3)
        self.assertEqual(self.run_('--execute', '--no-gate', env={'FAKE_MOUNTS': '/dev/block/sda18 /data ext4 rw 0 0'}).returncode, 3)
        self.assertEqual(open(self.disk, 'rb').read(), before)
    def test_write_verify_retry_and_final_hash(self):
        r = self.run_('--execute', '--no-gate'); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        n = os.path.getsize(self.img); disk = open(self.disk, 'rb').read(); self.assertEqual(disk[:n], open(self.img, 'rb').read()); self.assertEqual(disk[n:], b'\xaa' * (len(disk) - n))
        self.assertTrue(os.path.exists(os.path.join(self.d, 'flag')), 'el trozo corrupto no se inyectó'); self.assertIn('intento 1', r.stdout)
    def test_dry_transport_leaves_disk_alone(self):
        before = open(self.disk, 'rb').read(); r = self.run_('--execute', '--dry-transport'); self.assertEqual(r.returncode, 0, r.stdout + r.stderr); self.assertEqual(open(self.disk, 'rb').read(), before)
    def test_the_only_write_target_is_userdata(self):
        import re; src = open(T).read(); self.assertTrue(all(re.match(r'of=(%s|USERDATA)', src[m.start():]) for m in re.finditer(r'of=', src))); self.assertNotIn('mkfs', src); self.assertNotIn('wipe', src)
if __name__ == '__main__': unittest.main()

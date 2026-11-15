#!/usr/bin/env python3
"""Tests of herolte-wifi-extract.sh with a FAKE adb (no phone is touched)."""
import os, stat, subprocess, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, 'herolte-wifi-extract.sh')
FAKE = r'''#!/bin/bash
D="$(dirname "$0")"; echo "$@" >> "$D/calls.log"
case "$1" in
 devices) echo "List of devices attached"; echo "XXXX	recovery";;
 pull) printf 'data-%s' "$(basename "$2")" > "$3";;
 shell) case "$2" in
   "test -e "*) exit 0;;
   "readlink -f "*) echo "/dev/block/sda16";;
   "mount") echo "/dev/block/sda5 on /boot type vfat (rw)";;
   "grep ' /tmp/ven ' /proc/mounts") if [[ -e "$D/RW" ]]; then echo "/dev/block/sda16 /tmp/ven ext4 rw,relatime 0 0"; else echo "/dev/block/sda16 /tmp/ven ext4 ro,relatime 0 0"; fi;;
   *) exit 0;; esac;;
esac
'''


class Extract(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='wifi-extract.')
        self.adb = os.path.join(self.d, 'adb')
        with open(self.adb, 'w') as f:
            f.write(FAKE)
        os.chmod(self.adb, 0o755)
        self.out = os.path.join(self.d, 'out')

    def run_script(self, *extra):
        return subprocess.run(['bash', SCRIPT, self.adb, self.out, *extra], capture_output=True, text=True)

    def calls(self):
        p = os.path.join(self.d, 'calls.log')
        return open(p).read() if os.path.exists(p) else ''

    def test_dry_run_touches_nothing(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 0)
        self.assertFalse(os.path.exists(self.out))
        self.assertEqual(self.calls(), '')
        self.assertIn('mount -o ro', r.stdout)

    def test_execute_pulls_three_files_read_only(self):
        r = self.run_script('--execute')
        self.assertEqual(r.returncode, 0, r.stderr)
        for n in ('fw.bin', 'clm.blob', 'nvram.txt'):
            self.assertEqual(stat.S_IMODE(os.stat(os.path.join(self.out, n)).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.out).st_mode), 0o700)
        c = self.calls()
        self.assertIn('mount -o ro', c)
        self.assertNotIn('mount -o rw', c)
        self.assertNotIn(' dd ', c)
        self.assertIn('umount /tmp/ven', c)

    def test_refuses_and_unmounts_when_the_mount_is_not_read_only(self):
        open(os.path.join(self.d, 'RW'), 'w').close()
        r = self.run_script('--execute')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('not read-only', r.stderr)
        self.assertIn('umount /tmp/ven', self.calls())
        self.assertFalse(os.path.exists(os.path.join(self.out, 'fw.bin')))


if __name__ == '__main__':
    unittest.main()

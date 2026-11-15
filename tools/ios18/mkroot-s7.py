#!/usr/bin/env python3
"""The iOS 18.7.8 root for the Galaxy S7 (ARMv8.0): Bergamota's Renegade root build plus v80strip.

  RENEGADE_TARGET=ios18 mkroot-s7.py --renegade BERGAMOTA_CHECKOUT [mkroot-full.py options]

Renegade (github.com/ry-diffusion/Bergamota, tools/renegade/mkroot-full.py) builds the merged HFS+ root of
the iPhone XR's iOS 18.7.8 and rewrites its pointer-authentication code for a CPU without PAC. The S7's
cores also lack LSE atomics and RCpc, so two of its stages get one more pass here:
  macho   every Mach-O: pacstrip, then tools/ios18/v80strip.py (RCpc 4-for-4, LSE -> routines in the
          __TEXT padding), then Renegade's ad-hoc re-sign (identifier, entitlements, CS options kept)
  cache   pacstrip_cache.py, then tools/ios18/v80strip_cache.py (routines in the padding between
          images, runtime and UI first), then fips_rehmac.py (libcorecrypto's __text HMAC)
Everything else (copy, tweaks, seal, verify, simg) is Renegade's own.
"""
import importlib.util
import os
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import v80strip  # noqa: E402

REN = None
for i, arg in enumerate(sys.argv):
    if arg == '--renegade' and i + 1 < len(sys.argv):
        REN = os.path.abspath(sys.argv[i + 1])
        del sys.argv[i:i + 2]
        break
REN = REN or os.environ.get('RENEGADE_CHECKOUT')
if not REN:
    sys.exit('--renegade BERGAMOTA_CHECKOUT (or RENEGADE_CHECKOUT) is needed')
os.environ['RENEGADE_CHECKOUT'] = REN                      # for spawned pool workers
RTOOLS = os.path.join(REN, 'tools', 'renegade')
sys.path.insert(0, RTOOLS)
_spec = importlib.util.spec_from_file_location('mkroot_full', os.path.join(RTOOLS, 'mkroot-full.py'))
mk = importlib.util.module_from_spec(_spec)
sys.modules['mkroot_full'] = mk
_spec.loader.exec_module(mk)
pacstrip = mk.pacstrip


_seen = Counter()


def _progress(what):
    """mkroot-full.py logs only at file 0, 20000, ... and only when that file is a Mach-O: say something per worker."""
    _seen[what] += 1
    if what == 'files' and _seen['files'] % 5000 == 0:
        mk.log(f'  worker {os.getpid()}: {_seen["files"]} files, {_seen["rewritten"]} Mach-Os rewritten')


def macho_worker(path):
    """mkroot-full.py's macho_worker with v80strip between pacstrip and the re-sign."""
    _progress('files')
    try:
        with open(path, 'rb') as f:
            if f.read(4) not in mk.MAGICS:
                return path, None, None
        buf = bytearray(open(path, 'rb').read())
        if mk.rplat.is_linux() and mk.macho_filetype(buf) == 0xb:
            return path, 'kext', None
        orig = bytes(buf)
        counts, fj = Counter(), []
        v80 = Counter()
        for base in pacstrip.slices(buf):
            pacstrip.process_slice(buf, base, True, False, os.path.basename(path), counts, fj)
        for base in v80strip.slices(buf):
            v80strip.process(buf, base, True, True, True, v80)
        for k, n in v80.items():
            if k not in ('room bytes', 'routine bytes', 'dumped'):
                counts['v80 ' + k] += n
        if bytes(buf) == orig:
            return path, 'clean', dict(counts)
        os.chmod(path, os.stat(path).st_mode | 0o200)
        with open(path, 'wb') as f:
            f.write(buf)
        old = pacstrip.sign(path)
        _progress('rewritten')
        counts = dict(counts)
        counts['__ident'] = old
        return path, 'rewritten', counts
    except BaseException as e:
        return path, 'FAILED: ' + str(e)[:300], None


def stage_cache(a, root):
    mk.need_free('cache stage')
    d = os.path.join(root, 'System/Library/Caches/com.apple.dyld')
    mk.run([sys.executable, '-I', os.path.join(RTOOLS, 'pacstrip_cache.py'), d, '--jobs', str(a.jobs), '--stubs'])
    files = sorted((os.path.join(d, n) for n in os.listdir(d)
                    if n.startswith('dyld_shared_cache_arm64e') and not n.endswith(('.symbols', '.atlas', '.map'))),
                   key=lambda p: (len(p), p))
    mk.run([sys.executable, '-I', os.path.join(HERE, 'v80strip_cache.py')] + files)
    mk.run([sys.executable, '-I', os.path.join(RTOOLS, 'fips_rehmac.py'), d, '--patch'])


mk.macho_worker = macho_worker
mk.stage_cache = stage_cache

if __name__ == '__main__':
    mk.main()

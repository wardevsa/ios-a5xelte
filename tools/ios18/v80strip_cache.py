#!/usr/bin/env python3
"""v80strip for a whole iOS 18 dyld shared cache (main file + sub-caches), in place.

  v80strip_cache.py CACHE_FILE [CACHE_FILE ...] [--scan] [--no-resign]

The same rewrites as v80strip.py (tools/ios18/v80strip.py): RCpc 4 bytes for 4 everywhere; every LSE
atomic (and RCpc load/store with an offset) a B to a routine of its own. Routines live in the zero
padding between one image's last __TEXT section and the next image (checked: inside an r-x mapping,
outside every segment of every image, all zero); there are ~7.8 MiB of it in 18.7.8, room for a quarter
of the 464k sites. So sites are placed by priority, each in the nearest padding with room within
+-127 MiB:
  tier 0  the runtime every process runs (libobjc, libswiftCore, libsystem_*, libdispatch, libc++,
          CoreFoundation, Foundation, Swift Concurrency, libxpc ...) and the UI stack (QuartzCore,
          UIKitCore, CoreGraphics, BaseBoard/FrontBoard/BackBoard, SpringBoard*, CoreText ...)
  tier 1  /usr/lib and public frameworks, smallest images first
  tier 2  private frameworks, smallest first
  tier 3  big rarely used frameworks (3D capture, photogrammetry, USD, ML runtimes, baseband)
What finds no room stays an LSE instruction: the kernel's v80emu traps it (~1.4 us each).

The CodeDirectory page hashes of every changed page are recomputed in place (as Bergamota's
pacstrip_cache.py does). Run it before fips_rehmac.py (libcorecrypto's __text may change).
Only numbers are printed.
"""
import argparse, bisect, hashlib, mmap, os, struct, sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v80strip as v  # noqa: E402
import fp16  # noqa: E402

RANGE = (128 << 20) - (1 << 20)
PROT_EXEC = 4
CSMAGIC_EMBEDDED_SIGNATURE, CSMAGIC_CODEDIRECTORY = 0xFADE0CC0, 0xFADE0C02
HASH_NAMES = {1: 'sha1', 2: 'sha256', 3: 'sha256', 4: 'sha384'}

# Tier 0 in this order (the hottest first: retain/release, locks, malloc, dispatch).
TIER0 = ('libobjc.A.dylib', 'libswiftCore.dylib', 'libsystem_platform.dylib', 'libsystem_pthread.dylib',
         'libsystem_malloc.dylib', 'libdispatch.dylib', 'libsystem_kernel.dylib', 'libc++.1.dylib', 'libc++abi.dylib',
         'CoreFoundation', 'Foundation', 'FoundationEssentials', 'libswift_Concurrency.dylib', 'libxpc.dylib',
         'libsystem_trace.dylib', 'QuartzCore', 'UIKitCore', 'CoreGraphics',
         # iOS 26: SwiftUI draws through RenderBox; one of its FP16 words without a routine (tier 2 until then) was
         # SpringBoard's and iconservicesagent's SIGILL (23G90, boot 26k3)
         'RenderBox', 'libsystem_c.dylib',
         'libsystem_info.dylib', 'libsystem_notify.dylib', 'libsystem_blocks.dylib', 'libsystem_darwin.dylib',
         'libsystem_containermanager.dylib', 'libsystem_coreservices.dylib', 'libsystem_m.dylib',
         'libdispatch.dylib', 'libxpc.dylib', 'libc++.1.dylib', 'libc++abi.dylib', 'libdyld.dylib', 'dyld',
         'libswift_Concurrency.dylib', 'libswiftDispatch.dylib', 'libswiftObjectiveC.dylib', 'libswiftos.dylib',
         'libswift_StringProcessing.dylib', 'libsqlite3.dylib', 'libcorecrypto.dylib', 'libcommonCrypto.dylib',
         'libz.1.dylib', 'libbsm.0.dylib', 'libnetwork.dylib',
         'CoreFoundation', 'Foundation', 'FoundationEssentials', 'FoundationInternationalization',
         'CFNetwork', 'Security', 'IOKit', 'IOSurface', 'IOMobileFramebuffer', 'CoreServices', 'MobileCoreServices',
         'QuartzCore', 'UIKitCore', 'UIKit', 'CoreGraphics', 'CoreText', 'CoreUI', 'ImageIO', 'CoreImage',
         'BaseBoard', 'FrontBoardServices', 'FrontBoard', 'BackBoardServices', 'RunningBoardServices',
         'SpringBoard', 'SpringBoardFoundation', 'SpringBoardHome', 'SpringBoardServices', 'SpringBoardUIServices',
         'BoardServices', 'UIFoundation', 'UIKitServices', 'SwiftUI', 'SwiftUICore', 'Combine', 'AttributeGraph',
         'CoreAutoLayout', 'TextInput', 'TextInputCore', 'GraphicsServices', 'AppSupport', 'MobileGestalt',
         'libMobileGestalt.dylib', 'CoreData', 'CloudKit', 'Network', 'libsystem_networkextension.dylib',
         'CoreAnimation', 'Metal', 'MetalTools', 'IOAccelerator', 'OpenGLES', 'CoreVideo', 'CoreMedia',
         'AudioToolbox', 'CoreAudio', 'AVFAudio', 'MediaToolbox', 'libboringssl.dylib', 'libsystem_asl.dylib',
         'ManagedConfiguration', 'AppleAccount', 'Accounts', 'PersistentConnection', 'ProtocolBuffer',
         'LaunchServices', 'CoreDuet', 'BiomeStreams')
# Images whose __text is used as room for routines. WebGPU only runs in WebKit's GPU process on a Metal device, which
# the S7 does not have; it has no initializers (__init_offsets/__mod_init_func) and no +load classes (__objc_nlclslist),
# so loading it runs none of its code. Its 2 MiB lie within branch range of CoreGraphics, whose FP16 words (886 on the
# 22H352 cache) found no room otherwise, and of libobjc. Checked in find_pads' caller: no initializer section.
SACRIFICE = ('WebGPU',)
TIER0_RANK = {}
for _n in TIER0:
    TIER0_RANK.setdefault(_n, len(TIER0_RANK))
TIER3 = ('Recon3D', 'AppleCV3D', 'libusd_ms.dylib', 'VisualLogger', 'AppC3D', 'CorePhotogrammetry', 'Espresso',
         'TuriCore', 'GraphComputeRT', 'CoreRealityIO', 'LearnedFeatures', 'libBasebandManager.dylib',
         'libBasebandManagerICE.dylib', 'libIPTelephony.dylib', 'libBasebandManagerDAL.dylib', 'ABMHelper',
         'SiriTTS', 'VectorKit', 'MobileSpotlightIndex')


def tier(path):
    base = path.rsplit('/', 1)[-1]
    if base in TIER0:
        return 0
    if base in TIER3:
        return 3
    if path.startswith('/usr/lib/') or path.startswith('/System/Library/Frameworks/'):
        return 1
    return 2


class Cache:
    def __init__(self, paths, write):
        self.maps, self.images, self.bufs, self.hdrs = [], [], {}, {}
        for p in paths:
            f = open(p, 'r+b' if write else 'rb')
            b = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_WRITE if write else mmap.ACCESS_READ)
            if not bytes(b[:7]) == b'dyld_v1':
                continue
            self.bufs[p] = b
            moff, mcount = struct.unpack_from('<II', b, 0x10)
            for i in range(mcount):
                addr, size, foff, maxp, initp = struct.unpack_from('<QQQII', b, moff + 32 * i)
                self.maps.append((addr, size, foff, initp, p))
            ioff, icount = struct.unpack_from('<II', b, 0x1C0)
            if icount == 0:
                ioff, icount = struct.unpack_from('<II', b, 0x18)
            if icount and not self.images:
                for i in range(icount):
                    addr, _, _, poff, _ = struct.unpack_from('<QQQII', b, ioff + 32 * i)
                    end = b.find(b'\0', poff)
                    self.images.append((addr, bytes(b[poff:end]).decode(errors='replace')))
        self.maps.sort()
        self.starts = [m[0] for m in self.maps]

    def where(self, addr, length=1):
        i = bisect.bisect_right(self.starts, addr) - 1
        if i < 0:
            return None
        a, size, foff, prot, p = self.maps[i]
        if addr + length > a + size:
            return None
        return p, foff + addr - a, prot, a + size

    def read(self, addr, length):
        w = self.where(addr, length)
        return None if w is None else self.bufs[w[0]][w[1]:w[1] + length]

    def macho(self, addr):
        """[(segname, vmaddr, vmsize)], [(sect addr, size, exec?)] of the image at addr."""
        head = self.read(addr, 32)
        if not head or struct.unpack_from('<I', head, 0)[0] != 0xFEEDFACF:
            return [], []
        ncmds, sizeofcmds = struct.unpack_from('<II', head, 16)
        cmds = self.read(addr + 32, sizeofcmds) or b''
        segs, sects, off = [], [], 0
        for _ in range(ncmds):
            cmd, size = struct.unpack_from('<II', cmds, off)
            if cmd == 0x19:
                name = bytes(cmds[off + 8:off + 24]).split(b'\0')[0]
                vmaddr, vmsize = struct.unpack_from('<QQ', cmds, off + 24)
                segs.append((name, vmaddr, vmsize))
                for s in range(struct.unpack_from('<I', cmds, off + 64)[0]):
                    so = off + 72 + 80 * s
                    sa, ss = struct.unpack_from('<QQ', cmds, so + 32)
                    flags = struct.unpack_from('<I', cmds, so + 64)[0]
                    if name == b'__TEXT':
                        sects.append((sa, ss, bool(flags & (v.S_ATTR_PURE_INSTRUCTIONS | v.S_ATTR_SOME_INSTRUCTIONS))))
            off += size
        return segs, sects


def sacrifice_ok(cache, addr):
    """True when loading the image at addr runs none of its code: no initializers, no +load classes or categories."""
    head = cache.read(addr, 32)
    ncmds, sizeofcmds = struct.unpack_from('<II', head, 16)
    cmds = cache.read(addr + 32, sizeofcmds)
    off = 0
    for _ in range(ncmds):
        cmd, size = struct.unpack_from('<II', cmds, off)
        if cmd in (0x1A, 0x11):                       # LC_ROUTINES_64 / LC_ROUTINES
            return False
        if cmd == 0x19:
            for s in range(struct.unpack_from('<I', cmds, off + 64)[0]):
                so = off + 72 + 80 * s
                sect = bytes(cmds[so:so + 16]).split(b'\0')[0]
                flags = struct.unpack_from('<I', cmds, so + 64)[0]
                if struct.unpack_from('<Q', cmds, so + 40)[0] and (
                        sect in (b'__init_offsets', b'__mod_init_func', b'__objc_nlclslist', b'__objc_nlcatlist')
                        or flags & 0xFF in (0x09, 0x16)):   # S_MOD_INIT_FUNC_POINTERS, S_INIT_FUNC_OFFSETS
                    return False
        off += size
    return True


def find_pads(cache, info):
    """Zero ranges after each image's last __TEXT section, up to the next thing in its r-x mapping."""
    taken = sorted((va, va + size) for segs, sects, _ in info for name, va, size in segs if size)
    starts = [t[0] for t in taken]
    pads = []
    for segs, sects, path in info:
        if not sects:
            continue
        last = (max(a + s for a, s, _ in sects) + 15) & ~15
        w = cache.where(last - 16)
        if w is None or not (w[2] & PROT_EXEC):
            continue
        stop = w[3]                                   # end of the mapping
        i = bisect.bisect_right(starts, last)
        if i < len(starts):
            stop = min(stop, starts[i])               # the next segment of any image
        if i > 0:
            last = max(last, (taken[i - 1][1] + 15) & ~15)   # past a segment that started before
        if stop - last < 64:
            continue
        data = cache.read(last, stop - last)
        if data is None:
            continue
        arr = np.frombuffer(bytes(data), dtype=np.uint8)
        nz = np.nonzero(arr)[0]
        if len(nz):                                   # keep only the zero tail (alignment fill)
            last = (last + int(nz[-1]) + 1 + 15) & ~15
        if stop - last >= 64:
            pads.append([last, stop])
    # the zero tail of every r-x mapping (the stub sub-caches between the big ones), outside every image
    for a, size, foff, prot, p in cache.maps:
        if not (prot & PROT_EXEC):
            continue
        end = a + size
        span = min(size, 4 << 20)
        data = np.frombuffer(bytes(cache.bufs[p][foff + size - span:foff + size]), dtype=np.uint8)
        nz = np.nonzero(data)[0]
        lo = ((end - span + int(nz[-1]) + 1) if len(nz) else end - span) + 16
        lo = (lo + 15) & ~15
        i = bisect.bisect_right(starts, lo)
        if i > 0:
            lo = max(lo, (taken[i - 1][1] + 15) & ~15)
        hi = min(end, starts[i]) if i < len(starts) else end
        if hi - lo >= 64 and not any(s <= lo < e or s < hi <= e for s, e in pads):
            pads.append([lo, hi])
            print(f'  mapping tail {lo:#x}..{hi:#x} ({(hi - lo) >> 10} KiB) in {os.path.basename(p)}')
    # Images whose code cannot run on the S7, given up whole as room (see SACRIFICE); their own sites are not rewritten
    for segs, sects, path in info:
        if path.rsplit('/', 1)[-1] in SACRIFICE:
            for sa, ss, ex in sects:
                lo, hi = (sa + 15) & ~15, (sa + ss) & ~15
                if ex and hi - lo >= 64:
                    pads.append([lo, hi])
                    print(f'  sacrificed {lo:#x}..{hi:#x} ({(hi - lo) >> 10} KiB) of {path}')
    # Several images can compute the same zero tail (the loop above does not check overlaps). Two list entries for one
    # range handed the same bytes to two sites, and the second routine overwrote the first: in the 2026-11-16 root,
    # libobjc's _selLock lock in map_images_nolock jumped into another site's unlock routine, and launchd died in
    # os_unfair_lock_unowned_abort. Merge every overlap into one range before anything is placed.
    merged = []
    for s, e in sorted(pads):
        if merged and s < merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    if len(merged) != len(pads):
        print(f'  {len(pads) - len(merged)} overlapping pad entries merged')
    return merged


def fix_signature(buf, pages4k):
    off, size = struct.unpack_from('<QQ', buf, 0x28)
    if not size:
        return 0
    magic, length, count = struct.unpack_from('>III', buf, off)
    if magic != CSMAGIC_EMBEDDED_SIGNATURE:
        return 0
    n = 0
    for i in range(count):
        typ, boff = struct.unpack_from('>II', buf, off + 12 + 8 * i)
        cd = off + boff
        cmagic, clen, ver, flags, hashOff, identOff, nSpecial, nCode, codeLimit = struct.unpack_from('>IIIIIIIII', buf, cd)
        if cmagic != CSMAGIC_CODEDIRECTORY:
            continue
        hsize, htype, _, plog = struct.unpack_from('>BBBB', buf, cd + 36)
        if htype not in HASH_NAMES:
            continue
        ps = 1 << plog
        pages = {p for p4 in pages4k for p in range((p4 << 12) // ps, (((p4 + 1) << 12) - 1) // ps + 1)}
        for p in pages:
            if p < nCode:
                d = hashlib.new(HASH_NAMES[htype], buf[p * ps:min((p + 1) * ps, codeLimit)]).digest()[:hsize]
                ho = cd + hashOff + p * hsize
                buf[ho:ho + hsize] = d
                n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('files', nargs='+')
    ap.add_argument('--scan', action='store_true', help='plan and count only, write nothing')
    ap.add_argument('--no-resign', action='store_true')
    ap.add_argument('--island', nargs=2, metavar=('SIZE', 'FILE'),
                    help='also place routines in SIZE bytes just below the cache (the herolte kernel maps FILE there, '
                         'xnu 9201): room within branch range of libobjc, QuartzCore, CoreGraphics and CoreText')
    a = ap.parse_args()
    cache = Cache([f for f in a.files if not f.endswith(('.symbols', '.atlas', '.map'))], not a.scan)
    info = []
    for addr, path in cache.images:
        segs, sects = cache.macho(addr)
        info.append((segs, sects, path))
        if path.rsplit('/', 1)[-1] in SACRIFICE and not sacrifice_ok(cache, addr):
            sys.exit(f'v80strip_cache: {path} has initializers or +load classes, it cannot be given up as room')
    pads = find_pads(cache, info)
    # The routine island (xnu 9201): the shared region between its base and the cache's first mapping is empty (dyld's
    # slide); the kernel maps the island file there, read+execute, ISLAND bytes below the first mapping. The first
    # sub-cache holds the hottest code and its padding is used up first (23G90: CoreGraphics' FP16 words, 7000 tier-0
    # atomics of libobjc, QuartzCore, CoreText left).
    island = None
    if a.island:
        isize = int(a.island[0], 0)
        assert isize > 0 and isize % 16384 == 0, 'island size: a multiple of 16 KiB'
        ibase = min(m[0] for m in cache.maps)
        island = (ibase - isize, ibase, bytearray(isize))
        pads.insert(0, [ibase - isize, ibase])
        print(f'  island {ibase - isize:#x}..{ibase:#x} ({isize >> 10} KiB) -> {a.island[1]}')
    print(f'{len(cache.bufs)} files, {len(cache.images)} images, {len(pads)} pads, '
          f'{sum(e - s for s, e in pads) >> 10} KiB of room')

    counts, per_tier, left_hot = Counter(), Counter(), Counter()
    sites = []                                       # (tier, image site count, addr, word, image)
    changed = {}
    for (segs, sects, path) in info:
        if path.rsplit('/', 1)[-1] in SACRIFICE:      # its text is room now: a branch written there breaks a routine
            continue
        mine = []
        fp16_sites = []
        for sa, ss, ex in sects:
            if not ex or not ss:
                continue
            w = cache.where(sa, ss)
            if w is None:
                continue
            p, foff = w[0], w[1]
            buf = cache.bufs[p]
            words = np.frombuffer(buf, dtype='<u4', count=ss // 4, offset=foff)
            ldapr = (words & 0x3FFFFC00) == 0x38BFC000
            rcpc = ((words & 0x3F200C00) == 0x19000000) | ldapr
            cas = (words & 0x3FA07C00) == 0x08A07C00
            casp = (words & 0xBFA07C00) == 0x08207C00
            ldop = ((words & 0x3F200C00) == 0x38200000) & ~ldapr & ((((words >> 15) & 1) == 0) | (((words >> 12) & 7) == 0))
            half = fp16.candidate_masks(np, words)
            for i in np.nonzero(rcpc | cas | casp | ldop | half)[0]:
                word = int(words[i])
                at = sa + 4 * int(i)
                if v.data_like(words, int(i)):          # a constant table in __text (SHA-256 K, libm), not code
                    counts['left (data-like)'] += 1
                    continue
                if half[i] and not (rcpc[i] or cas[i] or casp[i] or ldop[i]):
                    r, why = fp16.fp16_routine(word, 0, 0)
                    if r is None:                       # FCVT H<->S and friends are ARMv8.0: not a site
                        if why not in ('not fp16', 'fcvt'):
                            counts[f'fp16 left ({why})'] += 1
                        continue
                    fp16_sites.append((at, word))
                    continue
                if v.is_ldapr(word) or v.is_rcpc_imm(word):
                    nw = v.rcpc_rewrite(word)
                    if nw is not None:
                        counts['rcpc 4-for-4'] += 1
                        if not a.scan:
                            struct.pack_into('<I', buf, foff + 4 * int(i), nw)
                            changed.setdefault(p, set()).add((foff + 4 * int(i)) >> 12)
                        continue
                mine.append((at, word))
        t = tier(path)
        rank = TIER0_RANK.get(path.rsplit('/', 1)[-1], 0) if t == 0 else len(mine)
        # Order (odd keys are FP16): FP16 of tier 0, atomics of tier 0, FP16 of tier 1, atomics of tier 1, ...
        # A FP16 word left in place is SIGILL while an atomic left in place is only a v80emu trap; and libBNNS's and
        # VideoToolbox's tens of thousands of FP16 words must not take the room of CoreGraphics' FP16. (Tried on the
        # 22H352 cache: every tier-0 FP16 word placed; 510 libobjc atomics go to v80emu. Placing the six hottest
        # libraries' atomics first instead left 1243 of CoreGraphics' FP16 words, i.e. crashes.)
        for at, word in mine:
            sites.append((2 * t, rank, at, word, path))
        for at, word in fp16_sites:
            sites.append((2 * t - 1, rank, at, word, path))
    sites.sort()
    print(f'sites needing a routine: {len(sites)}, FP16 {sum(1 for s in sites if s[0] % 2)}')

    starts = [p[0] for p in pads]
    placed = []                                      # (site, routine address, routine words), checked after the loop
    for t, n, at, word, path in sites:
        if t % 2:                                    # odd keys are FP16 sites
            gen = fp16.fp16_routine
        else:
            gen = v.rcpc_routine if (v.is_ldapr(word) or v.is_rcpc_imm(word)) else v.lse_routine
        words, why = gen(word, at, at)               # size and feasibility only
        if words is None:
            counts[f'left ({why})'] += 1
            continue
        need = 4 * len(words)
        i = bisect.bisect_left(starts, at)
        best = None
        lo, hi = i - 1, i
        while lo >= 0 or hi < len(pads):
            cand = []
            if lo >= 0:
                cand.append(lo)
            if hi < len(pads):
                cand.append(hi)
            for k in cand:
                s, e = pads[k]
                if e - s >= need and abs(s - at) < RANGE:
                    best = k
                    break
            if best is not None:
                break
            dl = at - pads[lo][1] if lo >= 0 else 1 << 62
            dh = pads[hi][0] - at if hi < len(pads) else 1 << 62
            if min(dl, dh) > RANGE:
                break
            lo -= 1
            hi += 1
        label = f'tier {(t + 1) // 2} ' + ('fp16' if t % 2 else 'atomic')
        if best is None:
            per_tier[label + ' left'] += 1
            if t % 2 or t == 0:                       # FP16 left in place crashes (SIGILL): the kernel has no FP16
                left_hot[('FP16 ' if t % 2 else '') + path.rsplit('/', 1)[-1]] += 1
            continue
        dst = pads[best][0]
        words, why = gen(word, at, dst)
        placed.append((at, dst, words))
        pads[best][0] += need
        starts[best] = pads[best][0]
        if pads[best][1] - pads[best][0] < 48:       # full: out of the search
            del pads[best]
            del starts[best]
        per_tier[label + ' placed'] += 1
        counts[f'routine {why}'] += 1
        counts['routine bytes'] += need
        if island and island[0] <= dst < island[1]:
            per_tier[label + ' island'] += 1
        if not a.scan:
            ws = cache.where(at, 4)
            if island and island[0] <= dst < island[1]:
                struct.pack_into(f'<{len(words)}I', island[2], dst - island[0], *words)
            else:
                wd = cache.where(dst, need)
                struct.pack_into(f'<{len(words)}I', cache.bufs[wd[0]], wd[1], *words)
                changed.setdefault(wd[0], set()).update(range(wd[1] >> 12, (wd[1] + need - 1 >> 12) + 1))
            struct.pack_into('<I', cache.bufs[ws[0]], ws[1], v.b(at, dst))
            changed.setdefault(ws[0], set()).add(ws[1] >> 12)
    print('placement:', dict(sorted(per_tier.items())))
    print('counts:', dict(sorted(counts.items())))
    # every routine must still hold the words generated for its own site, and no two routines may overlap
    spans = sorted((dst, dst + 4 * len(words), at) for at, dst, words in placed)
    clash = [(a[2], b[2]) for a, b in zip(spans, spans[1:]) if b[0] < a[1]]
    if clash:
        sys.exit(f'v80strip_cache: {len(clash)} routines overlap, first sites {clash[0][0]:#x} / {clash[0][1]:#x}')
    if not a.scan:
        bad = 0
        for at, dst, words in placed:
            ws = cache.where(at, 4)
            if island and island[0] <= dst < island[1]:
                got = list(struct.unpack_from(f'<{len(words)}I', island[2], dst - island[0]))
            else:
                wd = cache.where(dst, 4 * len(words))
                got = list(struct.unpack_from(f'<{len(words)}I', cache.bufs[wd[0]], wd[1]))
            branch = struct.unpack_from('<I', cache.bufs[ws[0]], ws[1])[0]
            if got != list(words) or branch != v.b(at, dst):
                bad += 1
                if bad <= 5:
                    print(f'  site {at:#x} -> routine {dst:#x}: routine or branch changed after placement')
        if bad:
            sys.exit(f'v80strip_cache: {bad} of {len(placed)} placed routines do not match their site')
        print(f'verified: {len(placed)} routines intact, each site branches to its own')
    if left_hot:
        print('tier 0 sites left to the kernel:', dict(left_hot.most_common(30)))
    if island and not a.scan:
        used = max((dst + 4 * len(w) for at, dst, w in placed if island[0] <= dst < island[1]), default=island[0])
        os.makedirs(os.path.dirname(os.path.abspath(a.island[1])), exist_ok=True)
        with open(a.island[1], 'wb') as f:
            f.write(island[2])
        print(f'  island: {used - island[0]} of {island[1] - island[0]} bytes used, written to {a.island[1]}')
    if not a.scan:
        for p, pages in sorted(changed.items()):
            n = 0 if a.no_resign else fix_signature(cache.bufs[p], pages)
            cache.bufs[p].flush()
            print(f'  {os.path.basename(p)}: {len(pages)} pages changed, {n} hashes updated')


if __name__ == '__main__':
    main()

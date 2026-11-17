#!/usr/bin/env python3
"""v80strip: rewrite ARMv8.1+ atomics and RCpc loads of Mach-O code for the S7's ARMv8.0 cores.

The Exynos 8890 (Mongoose M1 + Cortex-A53) has no LSE atomics (CAS, CASP, LDADD..., SWP) and no RCpc
(LDAPR, LDAPUR/STLUR). iOS 18's arm64e code is full of them (objc_retain/release, swift_retain/release,
os_unfair_lock, ...); the kernel's trap emulation (v80emu) costs ~1.4 us each, 105x a native LL/SC.

  LDAPR{B,H,,X} Rt,[Rn]            -> LDAR  Rt,[Rn]                   4 bytes for 4 (stronger: RCsc)
  LDAPUR/STLUR Rt,[Rn] (offset 0)  -> LDAR/STLR                       4 bytes for 4
  LDAPUR*/STLUR with an offset,    -> B to a routine: LDUR*+DMB ISHLD / DMB ISH+STUR, B back
  LDAPURS* (sign extending)
  CAS*, CASP*, LD<op>*, ST<op>*,   -> B to a routine of its own: the LDXR/STXR (LDAXR/STLXR for the
  SWP*                                acquire/release forms) loop, B back to the next instruction

A routine saves the scratch registers it needs below the 128-byte red zone (SUB SP first), so no register,
no flag and no stack byte of the caller changes beyond what the instruction itself writes. Routines go into
zero padding of an executable mapping within +-128 MiB of the site (B range): in a standalone Mach-O the
tail of __TEXT after its last section and the slack after the load commands. Left as they are (the kernel's
v80emu still traps them): sites with Rn = SP, and sites for which no room was found.

  v80strip.py [--scan] [--no-rcpc] [--no-lse] IN [OUT]      (OUT defaults to IN; sign it afterwards)

Only executable sections are read (S_ATTR_PURE_INSTRUCTIONS / S_ATTR_SOME_INSTRUCTIONS), minus
LC_DATA_IN_CODE ranges. Fat files: every arm64/arm64e slice.
"""
import argparse
import struct
import sys
from collections import Counter

try:
    import numpy as np
except ImportError:                                  # fall back to a plain word-by-word scan
    np = None

import fp16                                          # noqa: E402  FP16 arithmetic -> FP32 routines (tools/ios18/fp16.py)

MH_MAGIC_64 = 0xFEEDFACF
FAT_MAGIC, FAT_MAGIC_64 = 0xCAFEBABE, 0xCAFEBABF
CPU_TYPE_ARM64 = 0x0100000C
LC_SEGMENT_64, LC_DATA_IN_CODE = 0x19, 0x29
S_ATTR_PURE_INSTRUCTIONS, S_ATTR_SOME_INSTRUCTIONS = 0x80000000, 0x00000400
S_ZEROFILL_TYPES = (0x1, 0xC, 0x12)

FRAME = 160                  # 128-byte red zone + 32 bytes for up to four scratch registers
SCRATCH = (16, 17, 15, 14, 13, 12, 11, 10, 9, 8)
B_RANGE = 128 << 20
DUMP = 0


# --- classification ------------------------------------------------------------------------------------------
def is_cas(w):
    return (w & 0x3FA07C00) == 0x08A07C00


def is_casp(w):
    return (w & 0xBFA07C00) == 0x08207C00


def is_ldapr(w):
    return (w & 0x3FFFFC00) == 0x38BFC000


def is_ldop(w):            # LD<op>/ST<op>/SWP: size 111 0 00 A R 1 Rs o3 opc 00 Rn Rt (minus LDAPR)
    return (w & 0x3F200C00) == 0x38200000 and not is_ldapr(w) and \
        ((w >> 15) & 1 == 0 or (w >> 12) & 7 == 0)


def is_rcpc_imm(w):        # LDAPUR*/STLUR: size 011001 opc 0 imm9 00 Rn Rt
    return (w & 0x3F200C00) == 0x19000000


def is_lse(w):
    return is_cas(w) or is_casp(w) or is_ldop(w)


# --- encoders ------------------------------------------------------------------------------------------------
def b(src, dst):
    off = dst - src
    assert -B_RANGE <= off < B_RANGE and off % 4 == 0, (hex(src), hex(dst))
    return 0x14000000 | ((off >> 2) & 0x3FFFFFF)


def cbnz(src, dst, rt, sf):
    off = (dst - src) >> 2
    assert -(1 << 18) <= off < (1 << 18)
    return (sf << 31) | 0x35000000 | ((off & 0x7FFFF) << 5) | rt


def sub_sp(imm):
    return 0xD10003FF | imm << 10


def add_sp(imm):
    return 0x910003FF | imm << 10


def stp_sp(a, b_, off):
    return 0xA9000000 | ((off // 8) & 0x7F) << 15 | b_ << 10 | 31 << 5 | a


def ldp_sp(a, b_, off):
    return 0xA9400000 | ((off // 8) & 0x7F) << 15 | b_ << 10 | 31 << 5 | a


def str_sp(rt, off):
    return 0xF90003E0 | (off // 8) << 10 | rt


def ldr_sp(rt, off):
    return 0xF94003E0 | (off // 8) << 10 | rt


def ldxr(size, acq, rt, rn):
    return size << 30 | 0x085F7C00 | acq << 15 | rn << 5 | rt


def stxr(size, rel, rs, rt, rn):
    return size << 30 | 0x08007C00 | rs << 16 | rel << 15 | rn << 5 | rt


def ldxp(sz, acq, rt, rt2, rn):
    return 0x887F0000 | sz << 30 | acq << 15 | rt2 << 10 | rn << 5 | rt


def stxp(sz, rel, rs, rt, rt2, rn):
    return 0x88200000 | sz << 30 | rs << 16 | rel << 15 | rt2 << 10 | rn << 5 | rt


def alu(op, sf, rd, rn, rm):
    base = {'add': 0x0B000000, 'bic': 0x0A200000, 'eor': 0x4A000000, 'orr': 0x2A000000, 'and': 0x0A000000}[op]
    return sf << 31 | base | rm << 16 | rn << 5 | rd


def mov(sf, rd, rm):
    return sf << 31 | 0x2A0003E0 | rm << 16 | rd


def cmp_(sf, rn, rm):
    return sf << 31 | 0x6B00001F | rm << 16 | rn << 5


def csel(sf, rd, rn, rm, cond):
    return sf << 31 | 0x1A800000 | rm << 16 | cond << 12 | rn << 5 | rd


def ext(signed, size, rd, rn):          # SXTB/SXTH/UXTB/UXTH (W)
    return (0x13000000 if signed else 0x53000000) | (7 if size == 0 else 15) << 10 | rn << 5 | rd


MRS_NZCV, MSR_NZCV = 0xD53B4200, 0xD51B4200
CLREX = 0xD5033F5F
DMB_ISHLD, DMB_ISH = 0xD50339BF, 0xD5033BBF
COND = {'gt': 0xC, 'lt': 0xB, 'hi': 0x8, 'lo': 0x3}


# --- routines ------------------------------------------------------------------------------------------------
class Asm:
    def __init__(self, base):
        self.base, self.words, self.fix = base, [], []

    def pc(self):
        return self.base + 4 * len(self.words)

    def emit(self, w):
        self.words.append(w)

    def label(self):
        return self.pc()

    def later(self, fn):                       # a word whose target is not known yet
        self.fix.append((len(self.words), fn))
        self.words.append(0)

    def done(self):
        for i, fn in self.fix:
            self.words[i] = fn(self.base + 4 * i)
        return self.words


def save_regs(a, regs):
    for i in range(0, len(regs), 2):
        a.emit(stp_sp(regs[i], regs[i + 1], 8 * i) if i + 1 < len(regs) else str_sp(regs[i], 8 * i))


def restore_regs(a, regs):
    for i in reversed(range(0, len(regs), 2)):
        a.emit(ldp_sp(regs[i], regs[i + 1], 8 * i) if i + 1 < len(regs) else ldr_sp(regs[i], 8 * i))


def scratch(avoid, n):
    out = [r for r in SCRATCH if r not in avoid][:n]
    assert len(out) == n
    return out


def lse_routine(w, site, base):
    """Words of the routine for LSE word w at address site, placed at base; None to leave the site alone."""
    rt, rn, rs = w & 31, (w >> 5) & 31, (w >> 16) & 31
    if rn == 31:
        return None, 'Rn=SP'
    a = Asm(base)
    back = site + 4
    if is_casp(w):
        sz = (w >> 30) & 1
        acq, rel = (w >> 22) & 1, (w >> 15) & 1
        o1, o2, t, c = scratch({rs, rs + 1, rt, rt + 1, rn}, 4)
        a.emit(sub_sp(FRAME)); a.emit(stp_sp(o1, o2, 0)); a.emit(stp_sp(t, c, 16))
        loop = a.label()
        a.emit(ldxp(sz, acq, o1, o2, rn))
        a.emit(alu('eor', sz, t, o1, rs))
        fail1 = len(a.words); a.emit(0)
        a.emit(alu('eor', sz, t, o2, rs + 1))
        fail2 = len(a.words); a.emit(0)
        a.emit(stxp(sz, rel, c, rt, rt + 1, rn))
        a.later(lambda pc: cbnz(pc, loop, c, 0))
        to_done = len(a.words); a.emit(0)
        fail = a.label()
        # a failed compare still needs the pair read single-copy atomic: write the same values back
        a.emit(stxp(sz, rel, c, o1, o2, rn))
        a.later(lambda pc: cbnz(pc, loop, c, 0))
        done = a.label()
        a.emit(mov(sz, rs, o1)); a.emit(mov(sz, rs + 1, o2))
        a.emit(ldp_sp(t, c, 16)); a.emit(ldp_sp(o1, o2, 0)); a.emit(add_sp(FRAME))
        a.later(lambda pc: b(pc, back))
        a.words[fail1] = cbnz(base + 4 * fail1, fail, t, sz)
        a.words[fail2] = cbnz(base + 4 * fail2, fail, t, sz)
        a.words[to_done] = b(base + 4 * to_done, done)
        return a.done(), 'casp'
    size = w >> 30
    sf = 1 if size == 3 else 0
    if is_cas(w):
        acq, rel = (w >> 22) & 1, (w >> 15) & 1
        o, t, c = scratch({rs, rt, rn}, 3)
        a.emit(sub_sp(FRAME)); a.emit(stp_sp(o, t, 0)); a.emit(str_sp(c, 16))
        loop = a.label()
        a.emit(ldxr(size, acq, o, rn))
        a.emit(alu('eor', sf, t, o, rs))
        if size < 2:
            a.emit(ext(False, size, t, t))
        fail_i = len(a.words); a.emit(0)
        a.emit(stxr(size, rel, c, rt, rn))
        a.later(lambda pc: cbnz(pc, loop, c, 0))
        to_done = len(a.words); a.emit(0)
        fail = a.label()
        a.emit(CLREX)
        done = a.label()
        a.emit(mov(sf, rs, o))
        a.emit(ldr_sp(c, 16)); a.emit(ldp_sp(o, t, 0)); a.emit(add_sp(FRAME))
        a.later(lambda pc: b(pc, back))
        a.words[fail_i] = cbnz(base + 4 * fail_i, fail, t, sf)
        a.words[to_done] = b(base + 4 * to_done, done)
        return a.done(), 'cas'
    # LD<op> / ST<op> / SWP
    acq, rel = (w >> 23) & 1, (w >> 22) & 1
    swp = (w >> 15) & 1
    opc = (w >> 12) & 7
    flags = not swp and opc >= 4
    # The old value is loaded straight into Rt when Rt is none of Rs, Rn, ZR (one scratch and the MOV less).
    own = rt not in (31, rs, rn)
    need = (0 if own else 1) + (0 if swp else 1) + 1 + (1 if flags else 0)
    regs = scratch({rs, rt, rn}, need)
    it = iter(regs)
    o = rt if own else next(it)
    t = None if swp else next(it)
    c = next(it)
    f = next(it) if flags else None
    a.emit(sub_sp(FRAME))
    save_regs(a, regs)
    if flags:
        a.emit(MRS_NZCV | f)
    loop = a.label()
    a.emit(ldxr(size, acq, o, rn))
    if swp:
        data = rs
    else:
        data = t
        if opc < 4:
            a.emit(alu(('add', 'bic', 'eor', 'orr')[opc], sf, t, o, rs))
        else:
            signed = opc in (4, 5)
            cond = COND[{4: 'gt', 5: 'lt', 6: 'hi', 7: 'lo'}[opc]]
            if size < 2:                              # compare the sub-word values, extended
                a.emit(ext(signed, size, t, o))
                a.emit(ext(signed, size, c, rs))
                a.emit(cmp_(0, t, c))
                a.emit(csel(0, t, o, c, cond))
            else:
                a.emit(cmp_(sf, o, rs))
                a.emit(csel(sf, t, o, rs, cond))
    a.emit(stxr(size, rel, c, data, rn))
    a.later(lambda pc: cbnz(pc, loop, c, 0))
    if flags:
        a.emit(MSR_NZCV | f)
    if rt != 31 and not own:
        a.emit(mov(sf, rt, o))
    restore_regs(a, regs)
    a.emit(add_sp(FRAME))
    a.later(lambda pc: b(pc, back))
    return a.done(), ('swp' if swp else ('ld', 'ld', 'ld', 'ld', 'ldmax', 'ldmax', 'ldmax', 'ldmax')[opc])


def rcpc_rewrite(w):
    """4-for-4 replacement of an RCpc word, or None when it needs a routine."""
    if is_ldapr(w):
        return 0x08DFFC00 | (w & 0xC00003FF)                    # LDAR, same size, Rn, Rt
    if is_rcpc_imm(w) and (w >> 12) & 0x1FF == 0:
        opc = (w >> 22) & 3
        if opc == 1:
            return 0x08DFFC00 | (w & 0xC00003FF)                # LDAPUR #0 -> LDAR
        if opc == 0:
            return 0x089FFC00 | (w & 0xC00003FF)                # STLUR #0 -> STLR
    return None


def rcpc_routine(w, site, base):
    plain = (w & ~0x3F000000) | 0x38000000                       # the same LDUR*/STUR (size, opc, imm9, Rn, Rt)
    if (w >> 22) & 3 == 0:
        words = [DMB_ISH, plain]
    else:
        words = [plain, DMB_ISHLD]
    return words + [b(base + 4 * len(words), site + 4)], 'rcpc'


# --- Mach-O --------------------------------------------------------------------------------------------------
def slices(buf):
    magic = struct.unpack_from('>I', buf, 0)[0]
    if magic in (FAT_MAGIC, FAT_MAGIC_64):
        n = struct.unpack_from('>I', buf, 4)[0]
        for i in range(n):
            if magic == FAT_MAGIC:
                ct, cs, off, size, al = struct.unpack_from('>iiIII', buf, 8 + i * 20)
            else:
                ct, cs, off, size, al = struct.unpack_from('>iiQQI', buf, 8 + i * 32)[:5]
            if ct == CPU_TYPE_ARM64:
                yield off
    elif struct.unpack_from('<I', buf, 0)[0] == MH_MAGIC_64:
        yield 0


def layout(buf, base):
    """Code ranges [(fileoff, end)], their VM address bias, and free zero ranges inside __TEXT."""
    magic, cputype, cpusub, ftype, ncmds, sizeofcmds = struct.unpack_from('<IiiIII', buf, base)
    assert magic == MH_MAGIC_64
    off = base + 32
    code, dice, text_secs = [], [], []
    text = None
    for _ in range(ncmds):
        cmd, size = struct.unpack_from('<II', buf, off)
        if cmd == LC_SEGMENT_64:
            seg = buf[off + 8:off + 24].split(b'\0')[0]
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from('<QQQQ', buf, off + 24)
            nsects = struct.unpack_from('<I', buf, off + 64)[0]
            if seg == b'__TEXT':
                text = (vmaddr, fileoff, filesize)
            for i in range(nsects):
                so = off + 72 + 80 * i
                addr, ssize, foff = struct.unpack_from('<QQI', buf, so + 32)
                flags = struct.unpack_from('<I', buf, so + 64)[0]
                if seg == b'__TEXT' and foff:
                    text_secs.append((foff, foff + ssize))
                if flags & (S_ATTR_PURE_INSTRUCTIONS | S_ATTR_SOME_INSTRUCTIONS) and (flags & 0xFF) not in S_ZEROFILL_TYPES and foff:
                    code.append((base + foff, base + foff + ssize, addr - foff))
        elif cmd == LC_DATA_IN_CODE:
            dataoff, datasize = struct.unpack_from('<II', buf, off + 8)
            for j in range(datasize // 8):
                o, ln, kind = struct.unpack_from('<IHH', buf, base + dataoff + 8 * j)
                dice.append((base + o, base + o + ln))
        off += size
    ranges = []
    for s, e, bias in code:
        pos = s
        for ds, de in sorted(d for d in dice if d[0] < e and d[1] > s):
            if ds > pos:
                ranges.append((pos, ds, bias))
            pos = max(pos, de)
        if pos < e:
            ranges.append((pos, e, bias))
    free = []
    if text and text_secs:
        vmaddr, fileoff, filesize = text
        hdr_end = (32 + sizeofcmds + 256 + 15) & ~15          # leave 256 bytes for load commands codesign may grow
        first = min(s for s, e in text_secs)
        last = (max(e for s, e in text_secs) + 15) & ~15
        for lo, hi in ((last, fileoff + filesize), (hdr_end, first)):
            if hi - lo >= 16 and not any(buf[base + lo:base + hi]):
                free.append([base + lo, base + hi, vmaddr - fileoff])
    return ranges, free


NEIGHBOURS = 8
_md = None
_decodes = {}


def decodable(w):
    """capstone >= 5 decodes w (LSE and PAC included); cached per word value."""
    global _md
    r = _decodes.get(w)
    if r is None:
        if _md is None:
            import capstone
            if int(capstone.__version__.split('.')[0]) < 5:
                raise SystemExit('v80strip needs capstone >= 5 (4.x does not decode LSE or PAC, every site would look like data)')
            _md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
        r = _decodes[w] = next(_md.disasm_lite(struct.pack('<I', w), 0), None) is not None
    return r


def data_like(words, i):
    """True when a word within NEIGHBOURS of words[i] does not decode: a constant table inside __text, not code.
    corecrypto's SHA-256 K table sits in __text and K[57] = 0x78a5636f encodes LDUMAXAH; rewriting it broke every
    SHA-256 (2026-11-16, cc_fips_test). Such words stay as they are (the kernel's v80emu traps the rare real one)."""
    lo, hi = max(0, i - NEIGHBOURS), min(len(words), i + NEIGHBOURS + 1)
    return any(not decodable(int(words[j])) for j in range(lo, hi) if j != i)


def candidates(buf, s, e):
    """Offsets in [s, e) (step 4) whose word may be CAS/CASP/LD<op>/SWP/LDAPR/LDAPUR/STLUR, in order. A superset:
    process() still applies the exact tests. numpy keeps the whole-root macho stage from walking every word in
    Python (ios18-root run 43755727940: hours on 196k files)."""
    n = (e - s) // 4
    if n <= 0:
        return []
    if np is None:
        return range(s, s + 4 * n, 4)
    w = np.frombuffer(buf, dtype='<u4', count=n, offset=s)
    m = (((w & 0x3FA07C00) == 0x08A07C00) | ((w & 0xBFA07C00) == 0x08207C00) |
         ((w & 0x3F200C00) == 0x38200000) | ((w & 0x3F200C00) == 0x19000000) | fp16.candidate_masks(np, w))
    return (s + 4 * np.nonzero(m)[0]).tolist()


def process(buf, base, write, do_rcpc, do_lse, counts):
    ranges, free = layout(buf, base)
    room = sum(hi - lo for lo, hi, _ in free)
    counts['room bytes'] += room
    pending = []
    for s, e, bias in ranges:
        rw = memoryview(buf)[s:s + 4 * ((e - s) // 4)].cast('I')
        for p in candidates(buf, s, e):
            w = struct.unpack_from('<I', buf, p)[0]
            if data_like(rw, (p - s) // 4):
                counts['left (data-like)'] += 1
                continue
            if do_rcpc and (is_ldapr(w) or is_rcpc_imm(w)):
                nw = rcpc_rewrite(w)
                if nw is not None:
                    counts['rcpc 4-for-4'] += 1
                    if write:
                        struct.pack_into('<I', buf, p, nw)
                    continue
                kind, gen = 'rcpc routine', rcpc_routine
            elif do_lse and is_lse(w):
                kind, gen = 'lse', lse_routine
            elif do_lse and fp16.is_candidate(w):
                r, why = fp16.fp16_routine(w, 0, 0)
                if r is None:                                 # FCVT and friends match the masks too: ARMv8.0
                    if why not in ('not fp16', 'fcvt'):
                        counts[f'fp16 left ({why})'] += 1
                    continue
                kind, gen = 'fp16', fp16.fp16_routine
            else:
                continue
            pending.append((0 if kind == 'fp16' else 1, p, w, bias, kind, gen))
    # FP16 first: a FP16 word left behind is SIGILL, an atomic left behind is only a v80emu trap
    for _, p, w, bias, kind, gen in sorted(pending, key=lambda x: (x[0], x[1])):
            site = p - base + bias                       # VM address of the site
            placed = False
            for fr in free:
                lo, hi, fbias = fr
                at = lo - base + fbias                    # VM address of the free space
                words, why = gen(w, site, at)
                if words is None:
                    counts[f'{kind} left ({why})'] += 1
                    placed = True
                    break
                if hi - lo >= 4 * len(words) and abs(at - site) < B_RANGE - 64:
                    if DUMP and counts['dumped'] < DUMP:
                        counts['dumped'] += 1
                        print(f'site {site:#x} {w:08x} -> routine {at:#x}: ' + ' '.join(f'{x:08x}' for x in words))
                    if write:
                        struct.pack_into(f'<{len(words)}I', buf, lo, *words)
                        struct.pack_into('<I', buf, p, b(site, at))
                    fr[0] = lo + 4 * len(words)
                    counts[f'{kind} routine: {why}'] += 1
                    counts['routine bytes'] += 4 * len(words)
                    placed = True
                    break
            if not placed:
                counts[f'{kind} left (no room)'] += 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--scan', action='store_true')
    ap.add_argument('--no-rcpc', action='store_true')
    ap.add_argument('--no-lse', action='store_true')
    ap.add_argument('--dump', type=int, default=0, help='print the words of the first N routines')
    ap.add_argument('inp')
    ap.add_argument('out', nargs='?')
    a = ap.parse_args()
    global DUMP
    DUMP = a.dump
    buf = bytearray(open(a.inp, 'rb').read())
    counts = Counter()
    for base in slices(buf):
        process(buf, base, not a.scan, not a.no_rcpc, not a.no_lse, counts)
    print(f'{a.inp}: ' + ', '.join(f'{k} {v}' for k, v in sorted(counts.items())))
    if not a.scan:
        open(a.out or a.inp, 'wb').write(buf)
    left = sum(v for k, v in counts.items() if 'no room' in k)
    sys.exit(2 if left else 0)


if __name__ == '__main__':
    main()

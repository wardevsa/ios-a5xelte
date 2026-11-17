#!/usr/bin/env python3
"""FP16 (ARMv8.2 FEAT_FP16) arithmetic as FP32 routines, for the S7's ARMv8.0 cores.

The Exynos 8890 has the ARMv8.0 half-precision conversions (FCVT H<->S/D, FCVTL/FCVTN) but none of the half
precision arithmetic, compares or moves that iOS 18 code uses (QuartzCore's CA::OGL::prepare_layer_image killed
backboardd with `fmov h1, #imm`, 2026-11-17). Each such word becomes a B to a routine of its own (placed by
v80strip / v80strip_cache like the LSE routines) that

  scalar   FCVT the half inputs to single in scratch registers, runs the same operation on single, FCVT the result
           back to half (compares set NZCV from the single compare: the same flags);
  vector   FCVTL/FCVTL2 .4H/.8H -> .4S, the same operation on .4S, FCVTN/FCVTN2 back (compares: XTN of the lane
           masks; to integer: SQXTN/UQXTN, saturating like the half form; from integer: SXTL/UXTL first);
  FMOV #imm  MOVZ the half bit pattern into a scratch W, FMOV S / DUP .H.

Single has more than twice half's precision plus two bits, so +, -, *, /, sqrt and the conversions round exactly as
the half instruction would (no double-rounding error); fused multiply-add may differ in the last bit in rare cases.
NaN payloads follow single's rules. Scratch V registers (q16 and up, never one the instruction names) and the
general register used by FMOV are saved below the 128-byte red zone, like the LSE routines.

  fp16_routine(word, site, base) -> (words, kind) | (None, reason)
"""
import struct

FRAME_RED = 128

# --- encoders --------------------------------------------------------------------------------------------------
def _b(src, dst):
    off = dst - src
    assert -(128 << 20) <= off < (128 << 20) and off % 4 == 0
    return 0x14000000 | ((off >> 2) & 0x3FFFFFF)


def _sub_sp(imm):
    return 0xD10003FF | imm << 10


def _add_sp(imm):
    return 0x910003FF | imm << 10


def _str_q(rt, off):            # STR Qt, [SP, #off]
    return 0x3D8003E0 | (off // 16) << 10 | rt


def _ldr_q(rt, off):
    return 0x3DC003E0 | (off // 16) << 10 | rt


def _str_x(rt, off):
    return 0xF90003E0 | (off // 8) << 10 | rt


def _ldr_x(rt, off):
    return 0xF94003E0 | (off // 8) << 10 | rt


def fcvt_s_h(sd, hn):
    return 0x1EE24000 | hn << 5 | sd


def fcvt_h_s(hd, sn):
    return 0x1E23C000 | sn << 5 | hd


def fcvtl(vd, vn, hi):          # FCVTL{2} Vd.4S, Vn.4H/8H
    return (0x4E217800 if hi else 0x0E217800) | vn << 5 | vd


def fcvtn(vd, vn, hi):          # FCVTN{2} Vd.4H/8H, Vn.4S
    return (0x4E216800 if hi else 0x0E216800) | vn << 5 | vd


def xtn(vd, vn, hi):            # XTN{2} Vd.4H/8H, Vn.4S
    return (0x4E612800 if hi else 0x0E612800) | vn << 5 | vd


def sqxtn(vd, vn, hi):
    return (0x4E614800 if hi else 0x0E614800) | vn << 5 | vd


def uqxtn(vd, vn, hi):
    return (0x6E614800 if hi else 0x2E614800) | vn << 5 | vd


def sxtl(vd, vn, hi):           # SSHLL{2} Vd.4S, Vn.4H/8H, #0
    return (0x4F10A400 if hi else 0x0F10A400) | vn << 5 | vd


def uxtl(vd, vn, hi):
    return (0x6F10A400 if hi else 0x2F10A400) | vn << 5 | vd


def movz_w(rd, imm16):
    return 0x52800000 | imm16 << 5 | rd


def fmov_s_w(sd, wn):
    return 0x1E270000 | wn << 5 | sd


def fmov_w_s(wd, sn):
    return 0x1E260000 | sn << 5 | wd


def and_ffff(rd, rn):           # AND Wd, Wn, #0xffff
    return 0x12003C00 | rn << 5 | rd


def dup_h(vd, wn, q):           # DUP Vd.4H/8H, Wn
    return (0x4E020C00 if q else 0x0E020C00) | wn << 5 | vd


def dup_elem_h(vd, vn, idx):    # DUP Vd.8H, Vn.H[idx]
    return 0x4E020400 | ((idx << 2) | 2) << 16 | vn << 5 | vd


def dup_scalar_h(hd, vn, idx):  # DUP Hd, Vn.H[idx] (MOV H): the upper bits of Vd cleared
    return 0x5E020400 | ((idx << 2) | 2) << 16 | vn << 5 | hd


def half_imm(imm8):
    """VFPExpandImm for half precision: the 16-bit pattern of FMOV Hd, #imm8."""
    sign = (imm8 >> 7) & 1
    b6 = (imm8 >> 6) & 1
    exp = ((b6 ^ 1) << 4) | ((b6 * 3) << 2) | ((imm8 >> 4) & 3)
    return sign << 15 | exp << 10 | (imm8 & 0xF) << 6


# --- routine frame ---------------------------------------------------------------------------------------------
class _Frame:
    def __init__(self, avoid_v, nv, gpr_avoid=(), ngpr=0):
        self.v = [r for r in range(16, 32) if r not in avoid_v][:nv]
        assert len(self.v) == nv
        self.g = [r for r in (16, 17, 15, 14, 13, 12, 11, 10, 9) if r not in gpr_avoid][:ngpr]
        save = 16 * nv + 16 * ((ngpr + 1) // 2)
        self.size = FRAME_RED + ((save + 15) & ~15)

    def prologue(self):
        if not self.v and not self.g:                  # nothing to save: no frame at all
            return []
        w = [_sub_sp(self.size)]
        w += [_str_q(r, 16 * i) for i, r in enumerate(self.v)]
        w += [_str_x(r, 16 * len(self.v) + 8 * i) for i, r in enumerate(self.g)]
        return w

    def epilogue(self):
        if not self.v and not self.g:
            return []
        w = [_ldr_x(r, 16 * len(self.v) + 8 * i) for i, r in enumerate(self.g)]
        w += [_ldr_q(r, 16 * i) for i, r in enumerate(self.v)]
        return w + [_add_sp(self.size)]


def fmov_s_imm(sd, imm8):       # FMOV Sd, #imm8: the same 8-bit immediates (and values) as FMOV Hd, #imm8
    return 0x1E201000 | imm8 << 13 | sd


def ins_h1_wzr(vd):             # INS Vd.H[1], WZR: clears bits 31:16 (an FMOV Sd, Wn leaves them from Wn)
    return 0x4E061C00 | 31 << 5 | vd


def _sources(rd, srcs):
    """Single-precision working registers for the half sources of a scalar op whose result goes to Hd.
    A source that is Hd itself is converted in place; when Hd is not a source, the first source is converted into Sd
    (its old value is not needed); the rest get scratch registers. Returns (frame, {src: working}, conversions);
    the conversion of a source that is Hd comes first, so no other conversion overwrites it before it is read."""
    work, scratch_for = {}, []
    if rd in srcs:
        work[rd] = rd
    for s in srcs:
        if s in work:
            continue
        if rd not in srcs and rd not in work.values():
            work[s] = rd
        else:
            scratch_for.append(s)
    fr = _Frame(set(srcs) | {rd}, len(scratch_for))
    for s, r in zip(scratch_for, fr.v):
        work[s] = r
    order = ([rd] if rd in srcs else []) + [s for s in dict.fromkeys(srcs) if s != rd]
    # sources converted into scratch first, then the one converted into Sd (it may be read by nobody else)
    order.sort(key=lambda s: 0 if work[s] != rd else 1)
    conv = [fcvt_s_h(work[s], s) for s in order]
    return fr, work, conv


def _wrap(fr, body, site, base):
    words = fr.prologue() + body + fr.epilogue()
    return words + [_b(base + 4 * len(words), site + 4)]


# --- classification --------------------------------------------------------------------------------------------
def candidate_masks(np, words):
    """numpy prefilter: every word that may be a FP16 data-processing instruction (fp16_routine decides)."""
    return (((words & 0xFFE00000) == 0x1EE00000) |                 # scalar ftype=11 (sf=0 conversions included)
            ((words & 0xFFE00000) == 0x9EE00000) |                 # scalar conversions, sf=1
            ((words & 0x7FE00000) == 0x1EC00000) |                 # fixed-point conversions
            ((words & 0xFFC00000) == 0x1FC00000) |                 # FMADD/FMSUB/FNMADD/FNMSUB half
            ((words & 0x9F60C400) == 0x0E400400) |                 # vector three-same FP16
            ((words & 0x9F7E0C00) == 0x0E780800) |                 # vector two-register misc FP16
            ((words & 0x9FF8FC00) == 0x0F00FC00) |                 # vector FMOV #imm, half
            ((words & 0x9FC00400) == 0x0F000000) |                 # vector by element, half
            ((words & 0xDFC00400) == 0x5F000000) |                 # scalar by element, half
            ((words & 0xFFBE0C00) == 0x5E300800) |                 # scalar pairwise, half
            ((words & 0xDF7E0C00) == 0x5E780800) |                 # scalar two-register misc, half
            ((words & 0xDF60C400) == 0x5E400400))                  # scalar three-same, half


_SCALAR_FORMS = ((0xFFE00000, 0x1EE00000), (0xFFE00000, 0x9EE00000), (0x7FE00000, 0x1EC00000), (0xFFC00000, 0x1FC00000),
                 (0x9F60C400, 0x0E400400), (0x9F7E0C00, 0x0E780800), (0x9FF8FC00, 0x0F00FC00), (0x9FC00400, 0x0F000000),
                 (0xDFC00400, 0x5F000000), (0xFFBE0C00, 0x5E300800), (0xDF7E0C00, 0x5E780800), (0xDF60C400, 0x5E400400))


def is_candidate(w):
    """The word may be FP16 arithmetic (the same test as candidate_masks, one word)."""
    return any((w & m) == v for m, v in _SCALAR_FORMS)


def fp16_routine(w, site, base):
    """Words of the FP32 routine for FP16 word w at site, placed at base; (None, reason) when w is not handled."""
    rd, rn, rm = w & 31, (w >> 5) & 31, (w >> 16) & 31

    # --- scalar, ftype = 11 ---
    if (w & 0xFFE00C00) == 0x1EE00800 and (w >> 12) & 0xF <= 8:        # FMUL FDIV FADD FSUB FMAX FMIN FMAXNM FMINNM FNMUL
        fr, work, conv = _sources(rd, [rn, rm])
        op = 0x1E200800 | ((w >> 12) & 0xF) << 12 | work[rm] << 16 | work[rn] << 5 | rd
        return _wrap(fr, conv + [op, fcvt_h_s(rd, rd)], site, base), 'fp16 2src'
    if (w & 0xFFE07C00) == 0x1EE04000:                                  # one source
        opc = (w >> 15) & 0x3F
        if opc in (4, 5, 7):                                            # FCVT H->S/D: ARMv8.0, not ours
            return None, 'fcvt'
        if opc not in (0, 1, 2, 3) and not 8 <= opc <= 15:
            return None, 'fp16 1src opc'
        body = [fcvt_s_h(rd, rn)]                                       # Sd is free: no scratch
        if opc != 0:                                                    # FMOV Hd, Hn: the conversions alone
            body.append(0x1E204000 | opc << 15 | rd << 5 | rd)
        return _wrap(_Frame(set(), 0), body + [fcvt_h_s(rd, rd)], site, base), 'fp16 1src'
    if (w & 0xFFE0FC07) == 0x1EE02000:                                  # FCMP{E} Hn, Hm|#0
        zero = (w >> 3) & 1
        fr = _Frame({rn, rm}, 2)
        a, c = fr.v
        body = [fcvt_s_h(a, rn)]
        if not zero:
            body.append(fcvt_s_h(c, rm))
        body.append(0x1E202000 | (0 if zero else c) << 16 | a << 5 | (w & 0x18))
        return _wrap(fr, body, site, base), 'fp16 fcmp'
    if (w & 0xFFE00C00) == 0x1EE00400:                                  # FCCMP{E}
        fr = _Frame({rn, rm}, 2)
        a, c = fr.v
        op = 0x1E200400 | c << 16 | (w & 0xF000) | a << 5 | (w & 0x1F)
        return _wrap(fr, [fcvt_s_h(a, rn), fcvt_s_h(c, rm), op], site, base), 'fp16 fccmp'
    if (w & 0xFFE00C00) == 0x1EE00C00:                                  # FCSEL
        fr, work, conv = _sources(rd, [rn, rm])
        op = 0x1E200C00 | work[rm] << 16 | (w & 0xF000) | work[rn] << 5 | rd
        return _wrap(fr, conv + [op, fcvt_h_s(rd, rd)], site, base), 'fp16 fcsel'
    if (w & 0xFFE01FE0) == 0x1EE01000:                                  # FMOV Hd, #imm: same imm8 and value in single
        body = [fmov_s_imm(rd, (w >> 13) & 0xFF), fcvt_h_s(rd, rd)]
        return _wrap(_Frame(set(), 0), body, site, base), 'fp16 fmov imm'
    if (w & 0x7FE0FC00) == 0x1EE00000:                                  # conversions to/from general registers
        sf, rmode, opc = w >> 31, (w >> 19) & 3, (w >> 16) & 7
        if opc == 6 and rmode == 0:                                     # FMOV Wd/Xd, Hn
            return _wrap(_Frame(set(), 0), [fmov_w_s(rd, rn), and_ffff(rd, rd)], site, base), 'fp16 fmov to gpr'
        if opc == 7 and rmode == 0:                                     # FMOV Hd, Wn/Xn: low 16 bits, the rest 0
            body = [fmov_s_w(rd, rn), ins_h1_wzr(rd)]
            return _wrap(_Frame(set(), 0), body, site, base), 'fp16 fmov from gpr'
        if opc in (0, 1, 4, 5):                                         # FCVT{N,P,M,Z,A}{S,U} Rd, Hn
            fr = _Frame({rn}, 1)
            a, = fr.v
            op = (w & ~0x00C003E0) | a << 5
            return _wrap(fr, [fcvt_s_h(a, rn), op], site, base), 'fp16 to int'
        if opc in (2, 3) and rmode == 0:                                # SCVTF/UCVTF Hd, Rn (Sd is free)
            return _wrap(_Frame(set(), 0), [w & ~0x00C00000, fcvt_h_s(rd, rd)], site, base), 'fp16 from int'
        return None, 'fp16 conv'
    if (w & 0x7FE00000) == 0x1EC00000:                                  # fixed-point conversions
        rmode_opc = (w >> 16) & 0x1F
        if rmode_opc in (0x18, 0x19):                                   # FCVTZS/FCVTZU Rd, Hn, #fbits
            fr = _Frame({rn}, 1)
            a, = fr.v
            return _wrap(fr, [fcvt_s_h(a, rn), (w & ~0x00C003E0) | a << 5], site, base), 'fp16 to fixed'
        if rmode_opc in (0x02, 0x03):                                   # SCVTF/UCVTF Hd, Rn, #fbits (Sd is free)
            return _wrap(_Frame(set(), 0), [w & ~0x00C00000, fcvt_h_s(rd, rd)], site, base), 'fp16 from fixed'
        return None, 'fp16 fixed'
    if (w & 0xFFC00000) == 0x1FC00000:                                  # FMADD/FMSUB/FNMADD/FNMSUB Hd, Hn, Hm, Ha
        ra = (w >> 10) & 31
        fr, work, conv = _sources(rd, [rn, rm, ra])
        op = (w & ~0x00C07FFF & ~(31 << 16)) | work[rm] << 16 | work[ra] << 10 | work[rn] << 5 | rd
        return _wrap(fr, conv + [op, fcvt_h_s(rd, rd)], site, base), 'fp16 fmadd'

    # --- AdvSIMD scalar (H registers) ---
    if (w & 0xDFC00400) == 0x5F000000 and (w >> 12) & 0xF in (1, 5, 9):  # FMLA/FMLS/FMUL/FMULX Hd, Hn, Vm.H[i]
        u, opc4 = (w >> 29) & 1, (w >> 12) & 0xF
        if u and opc4 != 9:
            return None, 'fp16 scalar elem'
        idx = ((w >> 11) & 1) << 2 | ((w >> 21) & 1) << 1 | ((w >> 20) & 1)
        vm = (w >> 16) & 15
        fr = _Frame({rd, rn, vm}, 3)
        n, e, d = fr.v
        body = [dup_scalar_h(e, vm, idx), fcvt_s_h(e, e), fcvt_s_h(n, rn)]
        if opc4 == 9:                                                   # FMULX S (scalar three-same) / FMUL S
            body.append((0x5E20DC00 | e << 16 | n << 5 | n) if u else (0x1E200800 | e << 16 | n << 5 | n))
            res = n
        else:
            body.append(fcvt_s_h(d, rd))
            body.append((0x1F008000 if opc4 == 5 else 0x1F000000) | e << 16 | d << 10 | n << 5 | d)   # FMSUB/FMADD
            res = d
        return _wrap(fr, body + [fcvt_h_s(rd, res)], site, base), 'fp16 scalar elem'
    if (w & 0xFFBE0C00) == 0x5E300800:                                  # FADDP/FMAX(NM)P/FMIN(NM)P Hd, Vn.2H
        fr = _Frame({rd, rn}, 1)
        s, = fr.v
        op = ((w | 0x20000000) & ~0x3FF) | s << 5 | s                   # the single form (U=1): Sd, Vn.2S
        return _wrap(fr, [fcvtl(s, rn, 0), op, fcvt_h_s(rd, s)], site, base), 'fp16 scalar pairwise'
    if (w & 0xDF7E0C00) == 0x5E780800:                                  # scalar two-register misc, half
        u, hi_a, opc5 = (w >> 29) & 1, (w >> 23) & 1, (w >> 12) & 0x1F
        op32 = (w & ~0x007E03FF) | 0x00200000                           # the single form
        fr = _Frame({rd, rn}, 1)
        s, = fr.v
        if hi_a == 0 and opc5 == 0x1D:                                  # SCVTF/UCVTF Hd, Hn (16-bit integer)
            body = [(uxtl if u else sxtl)(s, rn, 0), op32 | s << 5 | s, fcvt_h_s(rd, s)]
        elif opc5 in (0x1A, 0x1B) or (hi_a == 0 and opc5 == 0x1C):      # FCVT{N,M,A,P,Z}{S,U} Hd, Hn
            body = [fcvt_s_h(s, rn), op32 | s << 5 | s, (0x7E614800 if u else 0x5E614800) | s << 5 | rd]  # UQXTN/SQXTN H
        elif hi_a == 1 and opc5 in (0x0C, 0x0D) or (hi_a, u, opc5) == (1, 0, 0x0E):   # FCM{GT,GE,EQ,LE,LT} #0
            body = [fcvt_s_h(s, rn), op32 | s << 5 | s, 0x5E614800 | s << 5 | rd]      # mask: SQXTN -1 -> 0xffff
        elif hi_a == 1 and opc5 == 0x1D:                                # FRECPE FRSQRTE (FRECPX depends on the format)
            body = [fcvt_s_h(s, rn), op32 | s << 5 | s, fcvt_h_s(rd, s)]
        else:
            return None, 'fp16 scalar misc opc'
        return _wrap(fr, body, site, base), 'fp16 scalar misc'
    if (w & 0xDF60C400) == 0x5E400400:                                  # scalar three-same, half
        u, hi_a, opc = (w >> 29) & 1, (w >> 23) & 1, (w >> 11) & 7
        key = (u, hi_a, opc)
        if key not in ((0, 0, 3), (0, 0, 4), (0, 0, 7), (0, 1, 7), (1, 0, 4), (1, 1, 4), (1, 0, 5), (1, 1, 5), (1, 1, 2)):
            return None, 'fp16 scalar 3same opc'                        # FMULX FCMEQ FRECPS FRSQRTS FCMGE FCMGT FACGE FACGT FABD
        compare = opc in (4, 5)
        fr = _Frame({rd, rn, rm}, 2)
        a, c = fr.v
        op = 0x5E200400 | u << 29 | hi_a << 23 | c << 16 | (0x18 | opc) << 11 | a << 5 | a
        tail = (0x5E614800 | a << 5 | rd) if compare else fcvt_h_s(rd, a)
        return _wrap(fr, [fcvt_s_h(a, rn), fcvt_s_h(c, rm), op, tail], site, base), 'fp16 scalar 3same'

    # --- vector ---
    q = (w >> 30) & 1
    if (w & 0x9FF8FC00) == 0x0F00FC00:                                  # FMOV Vd.4H/8H, #imm
        imm8 = ((w >> 16) & 7) << 5 | (w >> 5) & 31
        fr = _Frame(set(), 0, (), 1)
        g, = fr.g
        return _wrap(fr, [movz_w(g, half_imm(imm8)), dup_h(rd, g, q)], site, base), 'fp16 vec fmov imm'
    if (w & 0x9F60C400) == 0x0E400400:                                  # three-same
        u, hi_a, opc = (w >> 29) & 1, (w >> 23) & 1, (w >> 11) & 7
        key = (u, hi_a, opc)
        pairwise = key in ((1, 0, 0), (1, 0, 2), (1, 0, 6), (1, 1, 0), (1, 1, 6))   # FMAXNMP FADDP FMAXP FMINNMP FMINP
        compare = key in ((0, 0, 4), (1, 0, 4), (1, 1, 4), (1, 0, 5), (1, 1, 5))    # FCMEQ FCMGE FCMGT FACGE FACGT
        accum = key in ((0, 0, 1), (0, 1, 1))                                       # FMLA FMLS
        op32 = 0x0E200400 | 1 << 30 | u << 29 | hi_a << 23 | (0x18 | opc) << 11     # .4S form, registers added below
        return _vec_binary(w, op32, q, rd, rn, rm, pairwise, compare, accum, site, base, None)
    if (w & 0x9FC00400) == 0x0F000000 and (w >> 12) & 0xF in (1, 5, 9):  # by element: FMLA FMLS FMUL/FMULX .H[i]
        u, opc4 = (w >> 29) & 1, (w >> 12) & 0xF
        if u and opc4 != 9:
            return None, 'fp16 elem'
        idx = ((w >> 11) & 1) << 2 | ((w >> 21) & 1) << 1 | ((w >> 20) & 1)
        vm = (w >> 16) & 15
        # by element FMUL is U=0 and FMULX U=1; in the .4S three-same group FMUL is U=1 and FMULX U=0
        fp_opc, accum, uu = {1: (1, True, 0), 5: (1, True, 0), 9: (3, False, 1 - u)}[opc4]
        hi_a = 1 if opc4 == 5 else 0
        op32 = 0x0E200400 | 1 << 30 | uu << 29 | hi_a << 23 | (0x18 | fp_opc) << 11
        return _vec_binary(w, op32, q, rd, rn, vm, False, False, accum, site, base, idx)
    if (w & 0x9F7E0C00) == 0x0E780800:                                  # two-register misc
        u, hi_a, opc5 = (w >> 29) & 1, (w >> 23) & 1, (w >> 12) & 0x1F
        if (hi_a, u, opc5) in ((1, 1, 0x18), (1, 0, 0x1C), (1, 1, 0x1C), (1, 1, 0x0E)):
            return None, 'fp16 misc opc'                                # unallocated in the half group
        op32 = (w & ~0x407E03FF) | 1 << 30 | 0x00200000                 # .4S form, sz = 0, registers added below
        if hi_a == 1 and opc5 in (0x0C, 0x0D, 0x0E):                    # FCMGT/FCMGE/FCMEQ/FCMLE/FCMLT #0
            kind, narrow = 'cmp0', xtn
        elif opc5 in (0x1A, 0x1B, 0x1C):                                # FCVT{N,M,A,P,Z}{S,U}
            kind, narrow = 'toint', uqxtn if u else sqxtn
        elif hi_a == 0 and opc5 == 0x1D:                                # SCVTF/UCVTF
            kind, narrow = 'fromint', fcvtn
        elif (hi_a, opc5) in ((1, 0x0F), (1, 0x1F), (1, 0x1D)) or opc5 in (0x18, 0x19):
            kind, narrow = 'fp', fcvtn                                  # FABS FNEG FSQRT FRECPE FRSQRTE FRINT*
        else:
            return None, 'fp16 misc opc'
        if kind == 'fp' and (hi_a, opc5, u) == (1, 0x1F, 0):
            return None, 'fp16 misc opc'
        halves = (0, 1) if q else (0,)
        fr = _Frame({rd, rn}, len(halves))
        body = []
        for hpart, s in zip(halves, fr.v):
            if kind == 'fromint':
                body.append((uxtl if u else sxtl)(s, rn, hpart))
            else:
                body.append(fcvtl(s, rn, hpart))
            body.append(op32 | s << 5 | s)
        for hpart, s in zip(halves, fr.v):
            body.append(narrow(rd, s, hpart))
        return _wrap(fr, body, site, base), 'fp16 vec misc'
    return None, 'not fp16'


def _vec_binary(w, op32, q, rd, rn, rm, pairwise, compare, accum, site, base, elem):
    """Two-operand vector FP16 (three-same or by element) through .4S."""
    halves = (0, 1) if q else (0,)
    n_regs = 2 * len(halves) + (len(halves) if accum else 0) + (1 if elem is not None else 0)
    fr = _Frame({rd, rn, rm}, n_regs)
    regs = list(fr.v)
    body = []
    msrc = rm
    if elem is not None:                                               # every lane = Vm.H[idx]
        e = regs.pop()
        body.append(dup_elem_h(e, rm, elem))
        msrc = e
    nl = [regs.pop(0) for _ in halves]
    ml = [regs.pop(0) for _ in halves]
    dl = [regs.pop(0) for _ in halves] if accum else []
    for hp in halves:
        body.append(fcvtl(nl[hp], rn, hp))
        body.append(fcvtl(ml[hp], msrc, hp))
        if accum:
            body.append(fcvtl(dl[hp], rd, hp))
    res = []
    if pairwise:
        if q:                                                          # lanes: pairs of Vn, then pairs of Vm
            body.append(op32 | nl[1] << 16 | nl[0] << 5 | nl[0])
            body.append(op32 | ml[1] << 16 | ml[0] << 5 | ml[0])
            res = [nl[0], ml[0]]
        else:
            body.append(op32 | ml[0] << 16 | nl[0] << 5 | nl[0])
            res = [nl[0]]
    else:
        for hp in halves:
            if accum:
                body.append(op32 | ml[hp] << 16 | nl[hp] << 5 | dl[hp])
                res.append(dl[hp])
            else:
                body.append(op32 | ml[hp] << 16 | nl[hp] << 5 | nl[hp])
                res.append(nl[hp])
    narrow = xtn if compare else fcvtn
    for hp, r in zip(halves, res):
        body.append(narrow(rd, r, hp))
    return _wrap(fr, body, site, base), 'fp16 vec' + (' pairwise' if pairwise else ' elem' if elem is not None else '')


if __name__ == '__main__':
    import sys
    for arg in sys.argv[1:]:
        w = int(arg, 16)
        words, why = fp16_routine(w, 0x1000, 0x2000)
        print(f'{w:08x}: {why}', ' '.join(f'{x:08x}' for x in words or []))

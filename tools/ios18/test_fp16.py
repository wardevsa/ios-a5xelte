#!/usr/bin/env python3
"""Check tools/ios18/fp16.py against a CPU that has FP16: unicorn (QEMU's "max" arm64 model).

For random encodings of every FP16 form fp16_routine handles, run the original word and its routine (B there, B
back) from the same random state (general registers, V registers whose half lanes include +-0, subnormals,
infinities and quiet NaNs, NZCV) and compare every X/V register, SP and NZCV afterwards. Lanes where both results
are NaN count as equal (payloads follow single precision); fused multiply-add may differ by one unit in the last
place. Signalling NaN inputs are left out on purpose: FCVT to single quiets them, so FMAXNM/FMINNM(sNaN, x) return x
where the half instruction returns a NaN (no real code feeds signalling NaNs to these).

  python3 test_fp16.py [cases per form]       (needs unicorn >= 2 and capstone >= 5)
"""
import os
import random
import struct
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capstone                                     # noqa: E402
import unicorn as uc                                # noqa: E402
from unicorn import arm64_const as A                # noqa: E402
import fp16                                         # noqa: E402

SITE, ROUT, STACK = 0x100000, 0x200000, 0x300000
FORMS = [(0xFFE00000, 0x1EE00000), (0xFFE00000, 0x9EE00000), (0x7FE00000, 0x1EC00000), (0xFFC00000, 0x1FC00000),
         (0x9F60C400, 0x0E400400), (0x9F7E0C00, 0x0E780800), (0x9FF8FC00, 0x0F00FC00), (0x9FC00400, 0x0F000000),
         (0xDFC00400, 0x5F000000), (0xFFBE0C00, 0x5E300800), (0xDF7E0C00, 0x5E780800), (0xDF60C400, 0x5E400400)]
SPECIAL = [0x0000, 0x8000, 0x7C00, 0xFC00, 0x7E00, 0x7D00, 0x0001, 0x03FF, 0x3C00, 0xBC00, 0x7BFF, 0x0400, 0x3555]
md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)


def half():
    h = random.choice(SPECIAL) if random.random() < 0.3 else random.getrandbits(16)
    if (h & 0x7C00) == 0x7C00 and h & 0x3FF:
        h |= 0x200          # quiet NaNs only: single quiets a signalling one in FCVT, so FMAXNM/FMINNM(sNaN, x) differ
    return h


XREG = [A.UC_ARM64_REG_X0 + i for i in range(29)] + [A.UC_ARM64_REG_X29, A.UC_ARM64_REG_X30]   # X29/X30 are not X0+n


def vreg():
    return sum(half() << (16 * i) for i in range(8))


def new_uc():
    mu = uc.Uc(uc.UC_ARCH_ARM64, uc.UC_MODE_ARM)
    mu.ctl_set_cpu_model(A.UC_CPU_ARM64_MAX)
    for base in (SITE, ROUT, STACK):
        mu.mem_map(base, 0x10000)
    return mu


def run(mu, state, words_at):
    for addr, words in words_at:
        mu.mem_write(addr, struct.pack(f'<{len(words)}I', *words))
    for i in range(31):
        mu.reg_write(XREG[i], state['x'][i])
    for i in range(32):
        mu.reg_write(A.UC_ARM64_REG_Q0 + i, state['v'][i])
    mu.reg_write(A.UC_ARM64_REG_SP, STACK + 0x8000)
    mu.reg_write(A.UC_ARM64_REG_NZCV, state['nzcv'])
    mu.reg_write(A.UC_ARM64_REG_FPCR, 0)
    mu.reg_write(A.UC_ARM64_REG_CPACR_EL1, 3 << 20)
    mu.emu_start(SITE, SITE + 4, count=200)
    return ([mu.reg_read(XREG[i]) for i in range(31)], [mu.reg_read(A.UC_ARM64_REG_Q0 + i) for i in range(32)],
            mu.reg_read(A.UC_ARM64_REG_SP), mu.reg_read(A.UC_ARM64_REG_NZCV) & 0xF0000000)


def is_nan16(h):
    return (h & 0x7C00) == 0x7C00 and (h & 0x3FF)


def lanes_equal(a, b, fma):
    if a == b:
        return True
    for i in range(8):
        x, y = (a >> (16 * i)) & 0xFFFF, (b >> (16 * i)) & 0xFFFF
        if x == y or (is_nan16(x) and is_nan16(y)) or (fma and abs(x - y) <= 1 and (x ^ y) >> 15 == 0):
            continue
        return False
    return True


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    random.seed(18)
    stats, bad = Counter(), []
    import numpy as np
    for mask, value in FORMS + list(fp16._SCALAR_FORMS):           # a value bit outside its mask never matches
        assert value & ~mask == 0, f'form {mask:08x}/{value:08x}: value outside the mask'
    for mask, value in FORMS:
        tried = 0
        while stats[f'{value:08x} ok'] + stats[f'{value:08x} bad'] < n and tried < 200 * n:
            tried += 1
            w = (random.getrandbits(32) & ~mask) | value
            words, kind = fp16.fp16_routine(w, SITE, ROUT)
            if words is None or next(md.disasm_lite(struct.pack('<I', w), 0), None) is None:
                continue
            # the prefilters v80strip and v80strip_cache use must let every handled word through (2026-11-17: the
            # scalar masks did not, and no scalar FP16 word was rewritten)
            if not fp16.is_candidate(w) or not fp16.candidate_masks(np, np.array([w], dtype=np.uint32))[0]:
                stats['PREFILTER MISS'] += 1
                bad.append(f'{w:08x} {kind}: handled by fp16_routine but rejected by the prefilter')
                continue
            state = {'x': [random.getrandbits(64) for _ in range(31)], 'v': [vreg() for _ in range(32)],
                     'nzcv': random.getrandbits(4) << 28}
            try:
                ref = run(new_uc(), state, [(SITE, [w])])
            except uc.UcError:
                stats['unicorn refuses'] += 1                   # not executable on the emulated CPU either
                continue
            got = run(new_uc(), state, [(SITE, [fp16._b(SITE, ROUT)]), (ROUT, words)])
            fma = 'fmadd' in kind or ((w & 0x9F60C400) == 0x0E400400 and (w >> 11) & 7 == 1) or \
                ((w & 0x9FC00400) == 0x0F000000 and (w >> 12) & 0xF in (1, 5))
            ok = ref[0] == got[0] and ref[2] == got[2] and ref[3] == got[3] and \
                all(lanes_equal(r, g, fma) for r, g in zip(ref[1], got[1]))
            stats[f'{value:08x} ' + ('ok' if ok else 'bad')] += 1
            stats['kind ' + kind] += 1
            if not ok and len(bad) < 12:
                diff = [i for i in range(32) if not lanes_equal(ref[1][i], got[1][i], fma)]
                bad.append(f'{w:08x} {kind}: {next(md.disasm_lite(struct.pack("<I", w), 0))[2:]} v{diff} '
                           f'x{[i for i in range(31) if ref[0][i] != got[0][i]]} nzcv {ref[3]:x}/{got[3]:x}')
    for k, c in sorted(stats.items()):
        print(f'  {k}: {c}')
    for line in bad:
        print('BAD', line)
    print('FAIL' if bad else 'PASS')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

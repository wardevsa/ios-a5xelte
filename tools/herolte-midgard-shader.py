"""Hand-assemble the Midgard fragment shaders for the T880 tests.

Field layouts are Mesa's midgard.h bitfields, packed LSB first.

solid (herogpu=8): one bundle, TAG_ALU_12 + 4 (writeout variant, as Mesa's
scheduler emits it on GPUs without MIDGARD_NO_UPPER_ALU, e.g. 0x880):
    vmul: imov r0, r26 (embedded constants, all four 32-bit lanes)
    vadd: iadd r1.w, r31.x, #0          (Mesa: "r1.w = return address")
    br  : extended writeout, cond always, back to this bundle until it lands
Layout: control word, 2 register words, 2 x 48-bit vector ALU, 48-bit
extended branch, zero padding to 32 bytes, 16 bytes of constants.

textured (herogpu=9): what Mesa's preload/blit shader compiles to,
texture(s, varying0.xy) with an unnormalized sampler, in four bundles:
    ldst   : ld_vary_32 r0.xyzw, varying 0 (perspective, sample interp)
    alu4   : imov r28, r0             (texture inputs live in r28/r29)
    tex4   : r29 = texture 0 / sampler 0, 2D, gradient op at LOD 0, r28.xy
    alu8+wo: imov r0, r29; iadd r1.w, r31.x, #0; br.write to itself
"""
import struct

TAG_TEXTURE_4, TAG_LOAD_STORE_4 = 0x3, 0x5
TAG_ALU_4, TAG_ALU_8_WRITEOUT, TAG_ALU_12_WRITEOUT = 0x8, 0xD, 0xE
TAG_BREAK = 1
VMUL, VADD, BRANCH = 1 << 17, 1 << 21, 1 << 27
OP_IMOV, OP_IADD = 0x7B, 0x40
REG_MODE_32, SHRINK_NONE, OUTMOD_KEEPLO = 2, 2, 2
REGISTER_UNUSED, REGISTER_CONSTANT = 24, 26
SWZ_XYZW = 0 | 1 << 2 | 2 << 4 | 3 << 6


def reg_word(src1, src2, out, imm):
    return src1 | src2 << 5 | out << 10 | imm << 15


def vector_src(swizzle, mod=0, expand=0):
    return mod | expand << 2 | swizzle << 5


def vector_alu(op, src1, src2, mask):
    v = op | REG_MODE_32 << 8 | src1 << 10 | src2 << 23
    v |= SHRINK_NONE << 36 | OUTMOD_KEEPLO << 38 | mask << 40
    return v.to_bytes(6, 'little')


def expand_mask(m):     # 32-bit lanes: 2 mask bits per component
    return sum(3 << (2 * i) for i in range(4) if m >> i & 1)


def branch_writeout(dest_tag, offset):
    cond = 0xFFFF       # midgard_condition_always duplicated over the LUT
    v = 7 | dest_tag << 3 | 0 << 7 | (offset & 0x7FFFFF) << 9 | cond << 32
    return v.to_bytes(6, 'little')


def bits(fields):
    """Pack (value, width) pairs LSB first, like a packed C bitfield."""
    v, pos = 0, 0
    for val, width in fields:
        assert 0 <= val < 1 << width, (val, width)
        v |= val << pos
        pos += width
    return v, pos


def writeout_bundle(tag, src_reg, total_bytes):
    body = struct.pack('<I', VMUL | VADD | BRANCH | tag | TAG_BREAK << 4)
    body += struct.pack('<H', reg_word(REGISTER_UNUSED, src_reg, 0, 0))
    body += struct.pack('<H', reg_word(31, 0, 1, 1))
    body += vector_alu(OP_IMOV, 0, vector_src(SWZ_XYZW), expand_mask(0xF))
    body += vector_alu(OP_IADD, vector_src(0), 0, expand_mask(0x8))
    body += branch_writeout(tag, -(total_bytes // 16))   # loop on itself
    return body + b'\0' * (32 - len(body))


def assemble(color_words):
    body = writeout_bundle(TAG_ALU_12_WRITEOUT, REGISTER_CONSTANT, 48)
    body += struct.pack('<4I', *color_words)
    assert len(body) == 48
    return body


def ld_vary_32(reg, mask, varying):
    params = 1 << 4 | 1 << 6          # perspective_correction, interpolate_sample
    v, n = bits([
        (0x98, 8),                    # midgard_op_ld_vary_32
        (reg, 5), (mask, 4), (SWZ_XYZW, 8),
        (0, 2), (7, 3),               # arg_comp, arg_reg = REGISTER_LDST_ZERO
        (0, 1),                       # bitsize_toggle
        (2, 2),                       # index_format = midgard_index_address_u32
        (0, 2), (7, 3), (0, 4),       # index_comp, index_reg = ZERO, shift
        (varying << 9 | params, 18),  # signed_offset
    ])
    assert n == 60
    return v


def ldst_bundle(next_tag, word1, word2=3):    # 3 = LDST_NOP
    v = TAG_LOAD_STORE_4 | next_tag << 4 | word1 << 8 | word2 << 68
    return v.to_bytes(16, 'little')


def mov_bundle(next_tag, dst, src):
    body = struct.pack('<I', VMUL | TAG_ALU_4 | next_tag << 4)
    body += struct.pack('<H', reg_word(REGISTER_UNUSED, src, dst, 0))
    body += vector_alu(OP_IMOV, 0, vector_src(SWZ_XYZW), expand_mask(0xF))
    return body + b'\0' * (16 - len(body))


def texture_bundle(next_tag, in_select, out_select):
    v, n = bits([
        (TAG_TEXTURE_4, 4), (next_tag, 4),
        (2, 4),               # op: midgard_tex_op_gradient (Mesa's txl)
        (1, 4),               # mode: TEXTURE_NORMAL
        (3, 2),               # exec: MIDGARD_PARTIAL_EXECUTION_NONE
        (2, 2),               # format: 2D
        (0, 1), (0, 1),       # sampler/texture handles are immediates
        (0, 1), (0, 1),       # lod/offset immediates
        (1, 1), (in_select, 1), (0, 1),     # in_reg full, r28/r29, lower
        (SWZ_XYZW, 8),        # in_reg_swizzle
        (0, 2),               # unknown8
        (1, 1),               # out_full
        (1, 2),               # sampler_type: MALI_SAMPLER_FLOAT
        (out_select, 1), (0, 1),            # out r28/r29, lower
        (0xF, 4),             # mask
        (0, 2),               # outmod
        (SWZ_XYZW, 8),        # swizzle
        (0, 4), (0, 8),       # out_of_order, unknown4
        (0, 12),              # offset (immediate 0)
        (0, 8), (0, 8),       # bias, bias_int: LOD 0
        (0, 16), (0, 16),     # sampler_handle, texture_handle
    ])
    assert n == 128
    return v.to_bytes(16, 'little')


def assemble_textured():
    code = ldst_bundle(TAG_ALU_4, ld_vary_32(0, 0xF, 0))
    code += mov_bundle(TAG_TEXTURE_4, 28, 0)
    code += texture_bundle(TAG_ALU_8_WRITEOUT, 0, 1)
    code += writeout_bundle(TAG_ALU_8_WRITEOUT, 29, 32)
    assert len(code) == 80
    return code, TAG_LOAD_STORE_4


def c_words(code):
    words = struct.unpack(f'<{len(code) // 4}I', code)
    return ',\n'.join(', '.join(f'0x{w:08x}' for w in words[i:i + 6])
                      for i in range(0, len(words), 6))


if __name__ == '__main__':
    # 0x3c003c00: fp16 pairs (1.0, 1.0); as fp32 it is ~0.0078 (0233 showed
    # it: the shader's r0 is fp32, so the triangle came out near black).
    print('solid:')
    print(c_words(assemble([0x3C003C00] * 4)))
    code, tag = assemble_textured()
    print(f'textured (first tag {tag:#x}):')
    print(c_words(code))

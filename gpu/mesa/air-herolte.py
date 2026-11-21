#!/usr/bin/env python3
"""The S7's changes to Scion's AIR frontend (MIT, tools/mesa/air at a6f4bc38), after ios-b1lte's apply.py.

  air-herolte.py MESA/src/compiler/air

What iOS 18's shaders (the iPhone XR's 22H352, 20335 modules in 196 .metallib files) need that iOS 16.5's and 26's did
not, found on a host build against that corpus (docs/herolte-metal.md). Each change checks the exact text it replaces
and fails loudly if the file moved; run twice, it says so and changes nothing.
"""
import sys

AIR = sys.argv[1]
done = []


def change(name, path, old, new, marker=None):
    p = f'{AIR}/{path}'
    s = open(p).read()
    if new in s or (marker and marker in s):
        done.append(f'{name} (already)')
        return
    if s.count(old) != 1:
        sys.exit(f'air-herolte: {name}: {path} is not as expected ({s.count(old)} matches)')
    open(p, 'w').write(s.replace(old, new))
    done.append(name)


# 1. iOS 18's sincos: air.fast_sincos.f32(float x, ptr c) returns sin(x) and writes cos(x) through c (the out-pointer
# form of Metal's sincos(x, thread T &cosval)). MercuryPoster's fluidity and pro24Main shaders use it, and the frontend
# took the pointer for a number ("a pointer where a number belongs", 87 modules of the corpus).
change('sincos through a pointer', 'air_intrinsics.c',
       '''   nir_def *a[4] = { 0 };
   for (unsigned i = 0; i < argc && i < 4; i++)
      if (!(a[i] = air_get_ssa(c, in->operands[1 + i])))
         return false;
''',
       '''   /* HEROLTE: air.[fast_]sincos(x, ptr) -- sin(x) returned, cos(x) written through the pointer (iOS 18) */
   if ((!strcmp(op, "fast_sincos") || !strcmp(op, "sincos")) && argc == 2) {
      nir_def *x = air_get_ssa(c, in->operands[1]);
      struct air_val *cp = air_get(c, in->operands[2]);
      if (!x || !cp)
         return false;
      if (cp->kind != AIR_VAL_PTR)
         return air_error(c, "intrinsic: air.%s writes its cosine through a pointer that is not "
                             "one place", op);
      bool exact = c->b.exact;
      c->b.exact = false;
      nir_def *s = nir_fsin(&c->b, x), *co = nir_fcos(&c->b, x);
      c->b.exact = exact;
      if (!air_store_ptr(c, cp->ptr, co, x->bit_size / 8))
         return false;
      air_set(c, &in->base, air_val_ssa(c, s));
      *handled = true;
      return true;
   }

   nir_def *a[4] = { 0 };
   for (unsigned i = 0; i < argc && i < 4; i++)
      if (!(a[i] = air_get_ssa(c, in->operands[1 + i])))
         return false;
''')

# 2. Aggregates through calls of the module's own functions, flattened: every number in a struct or array (nested ones
# too) is one NIR parameter, and the struct or array is rebuilt on the other side. Scion's frontend gave a returned
# struct one out-parameter per NUMBER member and dropped the others, and passed no aggregate argument at all.
# MercuryPoster's tori::*::torusVertex returns a metal::float3x3 -- { [3 x <3 x float>] } -- from
# rotationMatrixFromEuler and passes its array to pointMapped: "an array where a number belongs" (68 modules).
# param_glsl_type also gets the 8-bit width, which a flattened member can have (a boolean stays a 32-bit word, as\n# Scion has it: vsEdge of RoomPlan returns i1 members into int outputs).
change('8-bit parameters', 'air_to_nir.c',
       '''   return glsl_vector_type(bits == 16 ? GLSL_TYPE_FLOAT16 :
                           bits == 64 ? GLSL_TYPE_UINT64 : GLSL_TYPE_UINT,''',
       '''   return glsl_vector_type(bits == 16 ? GLSL_TYPE_FLOAT16 :
                           bits == 64 ? GLSL_TYPE_UINT64 :
                           bits == 8 ? GLSL_TYPE_UINT8 : bits == 1 ? GLSL_TYPE_BOOL : GLSL_TYPE_UINT,''')

change('aggregate leaves', 'air_to_nir.c',
       '''static struct air_val *air_constant_val(struct air_ctx *c, const struct air_constant *k);
''',
       '''/* HEROLTE: a struct or array crossing a call of the module's own functions, as its NUMBERS in order ("leaves"):
 * one NIR parameter each, rebuilt as an AIR_VAL_AGG on the other side. A pointer inside one has no leaf (such an
 * argument specialises the callee instead, translate_callee). */
static bool
agg_type(const struct air_type *t)
{
   return t->kind == AIR_TYPE_STRUCT || t->kind == AIR_TYPE_ARRAY;
}

static unsigned
agg_count(const struct air_type *t)
{
   return t->kind == AIR_TYPE_STRUCT ? t->num_members : (unsigned)t->count;
}

static const struct air_type *
agg_member(const struct air_type *t, unsigned k)
{
   return t->kind == AIR_TYPE_STRUCT ? t->members[k] : t->elem;
}

static unsigned
agg_leaves(const struct air_type *t)
{
   if (agg_type(t)) {
      unsigned n = 0;
      for (unsigned k = 0; k < agg_count(t); k++)
         n += agg_leaves(agg_member(t, k));
      return n;
   }
   return ret_member_is_number(t) ? 1 : 0;
}

static void
agg_leaf_types(const struct air_type *t, const struct air_type **out, unsigned *n)
{
   if (agg_type(t)) {
      for (unsigned k = 0; k < agg_count(t); k++)
         agg_leaf_types(agg_member(t, k), out, n);
   } else if (ret_member_is_number(t)) {
      out[(*n)++] = t;
   }
}

/* a value's leaves, in agg_leaf_types order; NULL for one it does not have (an undef member) */
static bool
agg_leaf_vals(struct air_ctx *c, const struct air_type *t, struct air_val *v, struct air_val **out,
              unsigned *n)
{
   if (agg_type(t)) {
      if (v && v->kind != AIR_VAL_AGG)
         return air_error(c, "instruction: a struct or array crossing a call that is not one here");
      for (unsigned k = 0; k < agg_count(t); k++)
         if (!agg_leaf_vals(c, agg_member(t, k), v && k < v->num_elems ? v->elems[k] : NULL, out, n))
            return false;
      return true;
   }
   if (!ret_member_is_number(t))
      return true;
   if (v && v->kind != AIR_VAL_SSA)
      return air_error(c, "instruction: a member of a struct or array crossing a call that is not "
                          "a number");
   out[(*n)++] = v;
   return true;
}

static struct air_val *
agg_from_leaves(struct air_ctx *c, const struct air_type *t, struct air_val **leaves, unsigned *n)
{
   if (agg_type(t)) {
      struct air_val *a = air_val_agg(c, agg_count(t));
      for (unsigned k = 0; k < agg_count(t); k++)
         a->elems[k] = agg_from_leaves(c, agg_member(t, k), leaves, n);
      return a;
   }
   if (!ret_member_is_number(t))
      return NULL;
   return leaves[(*n)++];
}

static struct air_val *air_constant_val(struct air_ctx *c, const struct air_constant *k);
''', marker='agg_leaf_types(const struct air_type *t, const struct air_type **out')

change('flattened struct return: emit', 'air_to_nir.c',
       '''      if (v->kind != AIR_VAL_AGG || v->num_elems != c->num_ret_fields)
         return air_error(c, "instruction: a returned struct that was never built, "
                             "from a function called in the module");
      for (unsigned i = 0; i < v->num_elems; i++) {
         if (!c->ret_fields[i] || !v->elems[i])
            continue;
         if (v->elems[i]->kind != AIR_VAL_SSA)
            return air_error(c, "instruction: field %u of a returned struct is not a "
                                "number, from a function called in the module", i);
         nir_def *d = v->elems[i]->def;
         nir_store_deref(&c->b, c->ret_fields[i], d,
                         nir_component_mask(d->num_components));
      }
      return true;''',
       '''      /* HEROLTE: one out-parameter per LEAF (agg_leaves), arrays and nested structs flattened */
      const struct air_type *rt = c->fn->fn_type->elem;
      if (v->kind != AIR_VAL_AGG)
         return air_error(c, "instruction: a returned struct that was never built, "
                             "from a function called in the module");
      unsigned nl = 0;
      struct air_val **leaves = rzalloc_array(c->mem_ctx, struct air_val *, MAX2(agg_leaves(rt), 1));
      if (!agg_leaf_vals(c, rt, v, leaves, &nl))
         return false;
      for (unsigned i = 0; i < nl && i < c->num_ret_fields; i++) {
         if (!c->ret_fields[i] || !leaves[i])
            continue;
         nir_def *d = leaves[i]->def;
         nir_store_deref(&c->b, c->ret_fields[i], d,
                         nir_component_mask(d->num_components));
      }
      return true;''')

change('flattened parameters: count', 'air_to_nir.c',
       '''   unsigned nret = 0;
   if (ret_struct) {
      for (unsigned i = 0; i < rt->num_members; i++)
         nret += ret_member_is_number(rt->members[i]);
   } else if (has_ret) {
      nret = 1;
   }
   unsigned nparams = 3 * f->num_args + nret + b2l_extra;   /* B2L (B1L-0084): a chosen pointer takes three */''',
       '''   unsigned nret = 0;
   if (ret_struct) {
      nret = agg_leaves(rt);   /* HEROLTE: every number in it */
   } else if (has_ret) {
      nret = 1;
   }
   unsigned nparams = 3 * f->num_args + nret + b2l_extra;   /* B2L (B1L-0084): a chosen pointer takes three */
   const struct air_type **ret_leaf =
      rzalloc_array(c->mem_ctx, const struct air_type *, MAX2(nret, 1));
   if (ret_struct) {
      unsigned nl = 0;
      agg_leaf_types(rt, ret_leaf, &nl);
   }''')

change('flattened parameters: return params', 'air_to_nir.c',
       '''   if (ret_struct) {
      for (unsigned i = 0; i < rt->num_members; i++) {
         if (!ret_member_is_number(rt->members[i]))
            continue;
         fn->params[idx++] = (nir_parameter){
            .num_components = 1, .bit_size = 32,
            .is_return = true,
            .mode = nir_var_function_temp,
            .type = param_glsl_type(c, rt->members[i]),
         };
      }
   } else if (has_ret) {''',
       '''   if (ret_struct) {
      for (unsigned i = 0; i < nret; i++) {
         fn->params[idx++] = (nir_parameter){
            .num_components = 1, .bit_size = 32,
            .is_return = true,
            .mode = nir_var_function_temp,
            .type = param_glsl_type(c, ret_leaf[i]),
         };
      }
   } else if (has_ret) {''')

change('flattened parameters: callee return fields', 'air_to_nir.c',
       '''      c->ret_fields = rzalloc_array(c->mem_ctx, nir_deref_instr *,
                                    MAX2(rt->num_members, 1));
      c->num_ret_fields = rt->num_members;
      unsigned p = 0;
      for (unsigned i = 0; i < rt->num_members; i++) {
         if (!ret_member_is_number(rt->members[i]))
            continue;
         c->ret_fields[i] =
            nir_build_deref_cast(&c->b, nir_load_param(&c->b, p++),
                                 nir_var_function_temp,
                                 param_glsl_type(c, rt->members[i]), 0);
      }''',
       '''      /* HEROLTE: one per leaf; at least one entry, so that emit_return knows it is in a struct-returning callee */
      c->ret_fields = rzalloc_array(c->mem_ctx, nir_deref_instr *, MAX2(nret, 1));
      c->num_ret_fields = MAX2(nret, 1);
      for (unsigned p = 0; p < nret; p++)
         c->ret_fields[p] =
            nir_build_deref_cast(&c->b, nir_load_param(&c->b, p),
                                 nir_var_function_temp,
                                 param_glsl_type(c, ret_leaf[p]), 0);''')

change('flattened parameters: call site return', 'air_to_nir.c',
       '''   nir_variable **fields = ret_struct ?
      rzalloc_array(c->mem_ctx, nir_variable *, MAX2(rt->num_members, 1)) : NULL;
   nir_call_instr *call = nir_call_instr_create(c->nir, fn);
   unsigned idx = 0;
   if (ret_struct) {
      for (unsigned i = 0; i < rt->num_members; i++) {
         if (!ret_member_is_number(rt->members[i]))
            continue;
         fields[i] = nir_local_variable_create(c->b.impl,
                                               param_glsl_type(c, rt->members[i]),
                                               "callret");
         call->params[idx++] =
            nir_src_for_ssa(&nir_build_deref_var(&c->b, fields[i])->def);
      }
   } else if (has_ret) {''',
       '''   /* HEROLTE: one local per leaf of a returned struct (agg_leaves) */
   unsigned nret_leaves = ret_struct ? agg_leaves(rt) : 0;
   const struct air_type **ret_leaf =
      rzalloc_array(c->mem_ctx, const struct air_type *, MAX2(nret_leaves, 1));
   nir_variable **fields = ret_struct ?
      rzalloc_array(c->mem_ctx, nir_variable *, MAX2(nret_leaves, 1)) : NULL;
   nir_call_instr *call = nir_call_instr_create(c->nir, fn);
   unsigned idx = 0;
   if (ret_struct) {
      unsigned nl = 0;
      agg_leaf_types(rt, ret_leaf, &nl);
      for (unsigned i = 0; i < nret_leaves; i++) {
         fields[i] = nir_local_variable_create(c->b.impl, param_glsl_type(c, ret_leaf[i]),
                                               "callret");
         call->params[idx++] =
            nir_src_for_ssa(&nir_build_deref_var(&c->b, fields[i])->def);
      }
   } else if (has_ret) {''')

change('flattened parameters: call site rebuild', 'air_to_nir.c',
       '''   if (ret_struct) {
      struct air_val *agg = air_val_agg(c, rt->num_members);
      for (unsigned i = 0; i < rt->num_members; i++)
         if (fields[i])
            agg->elems[i] = air_val_ssa(c, nir_load_var(&c->b, fields[i]));
      air_set(c, &in->base, agg);''',
       '''   if (ret_struct) {
      struct air_val **leaves = rzalloc_array(c->mem_ctx, struct air_val *, MAX2(nret_leaves, 1));
      for (unsigned i = 0; i < nret_leaves; i++)
         leaves[i] = air_val_ssa(c, nir_load_var(&c->b, fields[i]));
      unsigned n = 0;
      air_set(c, &in->base, agg_from_leaves(c, rt, leaves, &n));''')

# 3. A table of functions: a function's address is its number in the module plus one, stored and loaded as a 32-bit
# integer in the shader's own memory, and a call through it calls every function of the call's type whose address the
# module takes and keeps the one whose number it is (bcsel). Only for candidates that write no memory but their own:
# all of them run. MercuryPoster's shippou::*::compute keep materialTop/Center/Bottom/World in an `alloca [4 x ptr]`
# and computeColor calls one by index ("a function value used before it is defined").
change('function numbers', 'air_to_nir.c',
       '''   air_error(c, "instruction: a %s value used before it is defined%s%s",''',
       '''   /* HEROLTE: a function's address is its number in the module plus one (herolte_indirect_call) */
   if (v->kind == AIR_VALUE_FUNCTION) {
      for (unsigned i = 0; i < c->m->num_functions; i++) {
         if (&c->m->functions[i]->base != v)
            continue;
         nir_cursor use = c->b.cursor;
         c->b.cursor = c->const_cursor;
         struct air_val *val = air_val_ssa(c, nir_imm_int(&c->b, (int)i + 1));
         c->const_cursor = c->b.cursor;
         c->b.cursor = use;
         air_set(c, v, val);
         return val;
      }
   }
   air_error(c, "instruction: a %s value used before it is defined%s%s",''')

change('function numbers loaded back', 'air_to_nir.c',
       '''      nir_def *res = air_load_ptr(c, p->ptr, in->base.type, in->align);
      if (!res)
         return false;
      air_set(c, &in->base, air_val_ssa(c, res));
      return true;
   }
   case AIR_OP_STORE: {''',
       '''      /* HEROLTE: a pointer loaded from the shader's own memory is a function number stored there */
      if (in->base.type->kind == AIR_TYPE_POINTER && p->ptr.class == AIR_PTR_SCRATCH) {
         static const struct air_type herolte_i32 = { .kind = AIR_TYPE_INT, .bits = 32 };
         nir_def *fnum = air_load_ptr(c, p->ptr, &herolte_i32, in->align);
         if (!fnum)
            return false;
         air_set(c, &in->base, air_val_ssa(c, fnum));
         return true;
      }
      nir_def *res = air_load_ptr(c, p->ptr, in->base.type, in->align);
      if (!res)
         return false;
      air_set(c, &in->base, air_val_ssa(c, res));
      return true;
   }
   case AIR_OP_STORE: {''')

change('calls through a function number', 'air_to_nir.c',
       '''      if (callee->kind != AIR_VALUE_FUNCTION || !callee->name)
         return air_error(c, "instruction: a call through a pointer");''',
       '''      if (callee->kind != AIR_VALUE_FUNCTION || !callee->name)
         return herolte_indirect_call(c, in);   /* HEROLTE */''')

change('indirect call declaration', 'air_to_nir.c',
       '''static struct air_val *air_constant_val(struct air_ctx *c, const struct air_constant *k);
''',
       '''static struct air_val *air_constant_val(struct air_ctx *c, const struct air_constant *k);
static bool herolte_indirect_call(struct air_ctx *c, const struct air_inst *in);
''', marker='static bool herolte_indirect_call(struct air_ctx *c, const struct air_inst *in);')

INDIRECT = r'''
/* -- HEROLTE: calls through a function number (air_get: a function's address is its number plus one) -- */

/* whether a function writes nothing but its own memory: no stores through a pointer outside address space 0, no
 * atomics, no texture writes or barriers, and the same for the module functions it calls */
static bool
herolte_pure(const struct air_module *m, const struct air_function *f, unsigned depth)
{
   if (depth > 8)
      return false;
   for (unsigned b = 0; b < f->num_blocks; b++) {
      for (unsigned i = 0; i < f->blocks[b].num_insts; i++) {
         const struct air_inst *in = f->blocks[b].insts[i];
         if (in->op == AIR_OP_ATOMICRMW || in->op == AIR_OP_CMPXCHG)
            return false;
         if (in->op == AIR_OP_STORE) {
            const struct air_type *pt = in->operands[1]->type;
            if (!pt || pt->kind != AIR_TYPE_POINTER || pt->addrspace != 0)
               return false;
         }
         if (in->op == AIR_OP_CALL) {
            const struct air_value *ce = in->operands[0];
            if (ce->kind != AIR_VALUE_FUNCTION || !ce->name)
               return false;
            if (strstr(ce->name, "write") || strstr(ce->name, "atomic") || strstr(ce->name, "barrier") ||
                strstr(ce->name, "memcpy") || strstr(ce->name, "memset"))
               return false;
            for (unsigned k = 0; k < m->num_functions; k++)
               if (&m->functions[k]->base == ce && !m->functions[k]->is_declaration &&
                   !herolte_pure(m, m->functions[k], depth + 1))
                  return false;
         }
      }
   }
   return true;
}

/* whether the module uses a function's address anywhere but as the callee of a call */
static bool
herolte_address_taken(const struct air_module *m, const struct air_value *fv)
{
   for (unsigned g = 0; g < m->num_functions; g++) {
      const struct air_function *f = m->functions[g];
      for (unsigned b = 0; b < f->num_blocks; b++)
         for (unsigned i = 0; i < f->blocks[b].num_insts; i++) {
            const struct air_inst *in = f->blocks[b].insts[i];
            for (unsigned o = 0; o < in->num_operands; o++)
               if (in->operands[o] == fv && !(in->op == AIR_OP_CALL && o == 0))
                  return true;
         }
   }
   return false;
}

/* cond ? a : b, member by member; NULL when their shapes differ */
static struct air_val *
herolte_select(struct air_ctx *c, nir_def *cond, struct air_val *a, struct air_val *b)
{
   if (!a)
      return b;
   if (!b)
      return a;
   if (a->kind == AIR_VAL_SSA && b->kind == AIR_VAL_SSA && a->def->bit_size == b->def->bit_size &&
       a->def->num_components == b->def->num_components)
      return air_val_ssa(c, nir_bcsel(&c->b, cond, a->def, b->def));
   if (a->kind == AIR_VAL_AGG && b->kind == AIR_VAL_AGG && a->num_elems == b->num_elems) {
      struct air_val *r = air_val_agg(c, a->num_elems);
      for (unsigned k = 0; k < a->num_elems; k++) {
         r->elems[k] = herolte_select(c, cond, a->elems[k], b->elems[k]);
         if (a->elems[k] && b->elems[k] && !r->elems[k])
            return NULL;
      }
      return r;
   }
   return NULL;
}

static bool
herolte_indirect_call(struct air_ctx *c, const struct air_inst *in)
{
   nir_def *id = air_get_ssa(c, in->operands[0]);
   if (!id)
      return air_error(c, "instruction: a call through a pointer that is not a function's number");
   bool has_ret = in->base.type && in->base.type->kind != AIR_TYPE_VOID;
   struct air_val *acc = NULL;
   unsigned n = 0;
   for (unsigned i = 0; i < c->m->num_functions; i++) {
      const struct air_function *f = c->m->functions[i];
      if (f->is_declaration || !f->num_blocks || !f->base.name || f->fn_type != in->aux_type ||
          !herolte_address_taken(c->m, &f->base))
         continue;
      if (!herolte_pure(c->m, f, 0))
         return air_error(c, "instruction: a call through a pointer to %s, which writes memory, so "
                             "calling every candidate is not an option", f->base.name);
      if (!air_call_in_module(c, in, f->base.name))
         return false;
      n++;
      if (has_ret) {
         struct air_val *r = air_get(c, &in->base);
         if (!r)
            return false;
         acc = acc ? herolte_select(c, nir_ieq_imm(&c->b, id, (int)i + 1), r, acc) : r;
         if (!acc)
            return air_error(c, "instruction: a call through a pointer whose candidates return "
                                "values of different shapes");
      }
   }
   if (!n)
      return air_error(c, "instruction: a call through a pointer, and no function of its type "
                          "has its address taken");
   if (has_ret)
      air_set(c, &in->base, acc);
   return true;
}
'''
p = f'{AIR}/air_to_nir.c'
s = open(p).read()
if 'herolte_indirect_call(struct air_ctx *c, const struct air_inst *in)\n{' not in s:
    open(p, 'w').write(s.rstrip('\n') + '\n' + INDIRECT)
    done.append('indirect calls')
else:
    done.append('indirect calls (already)')

# 4. A phi of a struct or array: one register per leaf (agg_leaves), stored on every incoming edge and rebuilt as an
# aggregate where the phi stands. A struct holding a pointer stays refused (a pointer has no register here).
# MercuryPoster's shippou computeColor carries its ray-hit struct around a loop that way (236 modules of the corpus).
change('aggregate phis: context', 'air_private.h',
       '''   /* phi -> nir register decl */
   struct hash_table *phi_regs;''',
       '''   /* phi -> nir register decl */
   struct hash_table *phi_regs;
   /* HEROLTE: phi of a struct or array -> nir_def *[agg_leaves], one register per leaf (air_to_nir.c) */
   struct hash_table *herolte_agg_phis;''')

change('aggregate phis: registers', 'air_to_nir.c',
       '''         if (in->base.type->kind == AIR_TYPE_STRUCT ||
             in->base.type->kind == AIR_TYPE_ARRAY)
            return air_error(c, "instruction: a phi of %s, which NIR has no register for",''',
       '''         if (agg_type(in->base.type) && !herolte_agg_has_ptr(in->base.type)) {
            /* HEROLTE: one register per leaf */
            unsigned nl = agg_leaves(in->base.type), nt = 0;
            const struct air_type **lt =
               rzalloc_array(c->mem_ctx, const struct air_type *, MAX2(nl, 1));
            agg_leaf_types(in->base.type, lt, &nt);
            nir_def **regs = rzalloc_array(c->mem_ctx, nir_def *, MAX2(nl, 1));
            for (unsigned k = 0; k < nl; k++)
               regs[k] = nir_decl_reg(&entry, air_nir_components(lt[k]), air_nir_bit_size(c, lt[k]), 0);
            if (!c->herolte_agg_phis)
               c->herolte_agg_phis = _mesa_pointer_hash_table_create(c->mem_ctx);
            _mesa_hash_table_insert(c->herolte_agg_phis, in, regs);
            continue;
         }
         if (in->base.type->kind == AIR_TYPE_STRUCT ||
             in->base.type->kind == AIR_TYPE_ARRAY)
            return air_error(c, "instruction: a phi of %s, which NIR has no register for",''')

change('aggregate phis: has a pointer', 'air_to_nir.c',
       '''static struct air_val *air_constant_val(struct air_ctx *c, const struct air_constant *k);
static bool herolte_indirect_call(''',
       '''static bool
herolte_agg_has_ptr(const struct air_type *t)
{
   if (agg_type(t)) {
      for (unsigned k = 0; k < agg_count(t); k++)
         if (herolte_agg_has_ptr(agg_member(t, k)))
            return true;
      return false;
   }
   return t->kind == AIR_TYPE_POINTER;
}

static struct air_val *air_constant_val(struct air_ctx *c, const struct air_constant *k);
static bool herolte_indirect_call(''', marker='herolte_agg_has_ptr(const struct air_type *t)\n{')

change('aggregate phis: loads', 'air_to_nir.c',
       '''         struct hash_entry *e = _mesa_hash_table_search(c->phi_regs, in);
         air_set(c, &in->base,
                 air_val_ssa(c, nir_load_reg(&c->b, e->data)));''',
       '''         struct hash_entry *ae = c->herolte_agg_phis && agg_type(in->base.type) ?
            _mesa_hash_table_search(c->herolte_agg_phis, in) : NULL;
         if (ae) {   /* HEROLTE: the aggregate from its leaves' registers */
            nir_def **regs = ae->data;
            unsigned nl = agg_leaves(in->base.type), n = 0;
            struct air_val **leaves = rzalloc_array(c->mem_ctx, struct air_val *, MAX2(nl, 1));
            for (unsigned k = 0; k < nl; k++)
               leaves[k] = air_val_ssa(c, nir_load_reg(&c->b, regs[k]));
            air_set(c, &in->base, agg_from_leaves(c, in->base.type, leaves, &n));
            continue;
         }
         struct hash_entry *e = _mesa_hash_table_search(c->phi_regs, in);
         air_set(c, &in->base,
                 air_val_ssa(c, nir_load_reg(&c->b, e->data)));''')

change('aggregate phis: stores', 'air_to_nir.c',
       '''         struct hash_entry *re = _mesa_hash_table_search(c->phi_regs, in);
         if (!re)
            continue; /* a phi in an unreachable block, or one of pointers */''',
       '''         struct hash_entry *ae = c->herolte_agg_phis && agg_type(in->base.type) ?
            _mesa_hash_table_search(c->herolte_agg_phis, in) : NULL;
         if (ae) {   /* HEROLTE: each leaf into its register, on every edge */
            nir_def **regs = ae->data;
            unsigned nl = agg_leaves(in->base.type);
            for (unsigned k = 0; k < in->num_operands; k++) {
               struct hash_entry *ce = _mesa_hash_table_search(c->phi_cursors, in->targets[k]);
               if (!ce)
                  continue;
               c->b.cursor = *(nir_cursor *)ce->data;
               struct air_val *v = air_get(c, in->operands[k]);
               if (!v)
                  return false;
               struct air_val **leaves = rzalloc_array(c->mem_ctx, struct air_val *, MAX2(nl, 1));
               unsigned n = 0;
               if (!agg_leaf_vals(c, in->base.type, v, leaves, &n))
                  return false;
               for (unsigned q = 0; q < n; q++)
                  if (leaves[q])
                     nir_store_reg(&c->b, leaves[q]->def, regs[q]);
               *(nir_cursor *)ce->data = c->b.cursor;
            }
            continue;
         }
         struct hash_entry *re = _mesa_hash_table_search(c->phi_regs, in);
         if (!re)
            continue; /* a phi in an unreachable block, or one of pointers */''')

# 6. Varyings packed: 32-bit float varyings of fewer than four components share slots, in the order they appear (the
# order both stages take them in, add_varying), at a component offset (location_frac) and with the driver location
# of the first variable in the slot. Everything else keeps a slot of its own. One slot per varying ran past VAR31 into
# the per-patch slots: MercuryPoster's torusVertex has 40 to 55 varyings (36 to 51 of them scalars), 48 to 63
# components, which is 12 to 16 vec4 packed -- what the Mali-T880 has -- and 40 to 55 slots not.
change('packed varyings: helper', 'air_to_nir.c',
       '''/* fragment inputs and vertex outputs take the slots in the order they appear;''',
       '''/* HEROLTE: the slot and component of the next varying, first fit: a 32-bit float varying of fewer than four
 * components goes after the components of the first slot that has room for it and holds only such varyings; anything
 * else, and a varying that fits nowhere, takes the next empty slot. Read off the variables made so far, so both
 * stages, taking the same varyings in the same order, place them alike. (*next: Scion's counter, unused.) */
static bool
herolte_packable(const struct glsl_type *gt)
{
   return glsl_get_base_type(gt) == GLSL_TYPE_FLOAT && glsl_get_vector_elements(gt) < 4;
}

static unsigned
herolte_varying_slot(struct air_ctx *c, const struct air_type *t, nir_variable_mode mode, unsigned *next,
                     unsigned *frac)
{
   (void)next;
   unsigned comps = air_nir_components(t);
   bool packable = comps < 4 && air_type_is_float(air_type_scalar(t)) && air_nir_bit_size(c, t) == 32;
   uint8_t used[64] = { 0 };
   unsigned top = 0;
   nir_foreach_variable_with_modes(v, c->nir, mode) {
      if (v->data.location < VARYING_SLOT_VAR0 || v->data.location >= VARYING_SLOT_VAR0 + 64)
         continue;
      unsigned s = v->data.location - VARYING_SLOT_VAR0;
      unsigned end = herolte_packable(v->type) ? v->data.location_frac + glsl_get_vector_elements(v->type) : 4;
      used[s] = MAX2(used[s], end);
      top = MAX2(top, s + 1);
   }
   for (unsigned s = 0; packable && s < top; s++) {
      if (used[s] + comps <= 4) {
         *frac = used[s];
         return VARYING_SLOT_VAR0 + s;
      }
   }
   *frac = 0;
   return VARYING_SLOT_VAR0 + top;
}

/* the driver location of a varying: its slot's, when another variable is there already */
static unsigned
herolte_varying_driver_location(struct air_ctx *c, nir_variable_mode mode, unsigned slot, unsigned frac,
                                unsigned *count)
{
   if (frac) {
      nir_foreach_variable_with_modes(v, c->nir, mode)
         if (v->data.location == (int)slot)
            return v->data.driver_location;
   }
   return (*count)++;
}

/* fragment inputs and vertex outputs take the slots in the order they appear;''')

change('packed varyings: fragment inputs', 'air_to_nir.c',
       '''      unsigned slot = VARYING_SLOT_VAR0 + (*next_varying)++;
      const char *name = md_key_str(node, "air.arg_name");
      nir_variable *var = make_io_var(c, nir_var_shader_in, t, slot, name);
      var->data.driver_location = c->nir->num_inputs++;''',
       '''      unsigned frac = 0;   /* HEROLTE: packed (herolte_varying_slot) */
      unsigned slot = herolte_varying_slot(c, t, nir_var_shader_in, next_varying, &frac);
      const char *name = md_key_str(node, "air.arg_name");
      nir_variable *var = make_io_var(c, nir_var_shader_in, t, slot, name);
      var->data.location_frac = frac;
      var->data.driver_location =
         herolte_varying_driver_location(c, nir_var_shader_in, slot, frac, &c->nir->num_inputs);''')

change('packed varyings: vertex outputs', 'air_to_nir.c',
       '''      location = VARYING_SLOT_VAR0 + (*next_varying)++;
      add_varying(c, md_str(node, md_key(node, "air.vertex_output") + 1), location,
                  air_nir_components(t), node);''',
       '''      location = herolte_varying_slot(c, t, nir_var_shader_out, next_varying, &herolte_frac);   /* HEROLTE: packed */
      add_varying(c, md_str(node, md_key(node, "air.vertex_output") + 1), location,
                  air_nir_components(t), node);''')

change('packed varyings: output variable', 'air_to_nir.c',
       '''   nir_variable *var = make_io_var(c, nir_var_shader_out, t, location, name);
   var->data.index = index;
   var->data.driver_location = c->nir->num_outputs++;''',
       '''   nir_variable *var = make_io_var(c, nir_var_shader_out, t, location, name);
   var->data.index = index;
   var->data.location_frac = herolte_frac;   /* HEROLTE: packed varyings */
   var->data.driver_location = location >= VARYING_SLOT_VAR0 && location < VARYING_SLOT_PATCH0 ?
      herolte_varying_driver_location(c, nir_var_shader_out, location, herolte_frac, &c->nir->num_outputs) :
      c->nir->num_outputs++;''')

change('packed varyings: output component', 'air_to_nir.c',
       '''   unsigned location = ~0u, index = 0;
   const char *name = md_key_str(node, "air.arg_name");

   int rt = md_key(node, "air.render_target");''',
       '''   unsigned location = ~0u, index = 0, herolte_frac = 0;
   const char *name = md_key_str(node, "air.arg_name");

   int rt = md_key(node, "air.render_target");''')

# 7. A boolean member of an entry point's result, stored as the 32-bit integer its output is (make_io_var makes an i1
# output an int). With booleans one bit wide through calls (8-bit parameters, above), RoomPlan's vsEdge returned
# computeVertexOut's i1 members into int outputs and NIR refused the store.
change('boolean outputs as words', 'air_to_nir.c',
       '''         nir_store_var(&c->b, c->outputs[i].var, v->elems[i]->def,
                       BITFIELD_MASK(v->elems[i]->def->num_components));''',
       '''         nir_def *hd = v->elems[i]->def;   /* HEROLTE: a boolean into its 32-bit output */
         if (hd->bit_size == 1 && glsl_get_bit_size(glsl_without_array(c->outputs[i].var->type)) == 32)
            hd = nir_b2i32(&c->b, hd);
         nir_store_var(&c->b, c->outputs[i].var, hd,
                       BITFIELD_MASK(v->elems[i]->def->num_components));''')

change('boolean inputs from words', 'air_to_nir.c',
       '''      if (c->nir->info.stage == MESA_SHADER_FRAGMENT)
         add_varying(c, name, slot, air_nir_components(t), node);
      c->params[param] = air_val_ssa(c, nir_load_var(&c->b, var));''',
       '''      if (c->nir->info.stage == MESA_SHADER_FRAGMENT)
         add_varying(c, name, slot, air_nir_components(t), node);
      nir_def *hl = nir_load_var(&c->b, var);   /* HEROLTE: an i1 varying arrives as an int (RoomPlan's fsEdge) */
      if (air_nir_bit_size(c, t) == 1 && hl->bit_size != 1)
         hl = nir_ine_imm(&c->b, hl, 0);
      c->params[param] = air_val_ssa(c, hl);''')

# 5. air_metal_test only (not the library): --draw-attrib also configures attribute 2 with the texture coordinate.
# MercuryPoster's torusVertex reads position, normal and uv as attributes 0, 1 and 2; the harness configured 0, 1 and 3.
change('air_metal_test: attribute 2', 'air_metal_test.c',
       '''   shape->vertex_attribute[3] = (struct rwa_vertex_attribute){
      .format = l->uv.format, .offset = l->uv.offset, .buffer_index = l->uv.buffer };

   shape->vertex_layout[l->pos.buffer]''',
       '''   shape->vertex_attribute[3] = (struct rwa_vertex_attribute){
      .format = l->uv.format, .offset = l->uv.offset, .buffer_index = l->uv.buffer };
   shape->vertex_attribute[2] = shape->vertex_attribute[3];   /* HEROLTE: torusVertex's uv */

   shape->vertex_layout[l->pos.buffer]''')

# 8. A program-scope global's own initial value. plan_globals puts every global that is not a sampler, a function
# constant or threadgroup memory in scratch, "written by the static initializers" -- but a global with an initializer
# and no static initializer (`constant float2 quadVertices[6] = {...}`, addrspace 2) was never written, so the shader
# read whatever scratch held. MercuryPoster's postVertex takes its six corners from such an array: on the T880 every
# vertex landed on one point and no pixel was drawn (boot-18k41..43). The value is written at the top of the entry
# point, before the static initializers run, with the frontend's own layout (air_layout.c).
change('global initializers: bytes', 'air_to_nir.c',
       '''static void
run_static_initializers(struct air_ctx *c)
{''',
       '''/* HEROLTE: the bytes of a constant of type t at buf + off, in the module's layout. False when it cannot say
 * (a constant expression, which needs addresses this frontend does not have). */
static bool
herolte_const_bytes(const struct air_module *m, const struct air_value *v, const struct air_type *t, uint8_t *buf,
                    uint64_t size, uint64_t off)
{
   if (!v || v->kind != AIR_VALUE_CONSTANT)
      return false;
   const struct air_constant *k = (const struct air_constant *)v;
   switch (k->ckind) {
   case AIR_CONST_NULL:
   case AIR_CONST_UNDEF:
   case AIR_CONST_POISON:
      return true;   /* the buffer is zeroed */
   case AIR_CONST_INT:
   case AIR_CONST_FLOAT: {
      unsigned bytes = MAX2(1, DIV_ROUND_UP(air_type_bit_size(t), 8));
      if (bytes > 8 || off + bytes > size)
         return false;
      memcpy(buf + off, &k->u, bytes);   /* little endian, as the GPU */
      return true;
   }
   case AIR_CONST_AGGREGATE:
   case AIR_CONST_DATA:
      for (unsigned i = 0; i < k->num_elems; i++) {
         const struct air_type *et;
         uint64_t eo;
         if (t->kind == AIR_TYPE_STRUCT) {
            if (i >= t->num_members)
               return false;
            et = t->members[i];
            eo = off + air_struct_member_offset(m, t, i);
         } else if (t->kind == AIR_TYPE_ARRAY || t->kind == AIR_TYPE_VECTOR) {
            et = t->elem;
            eo = off + i * (t->kind == AIR_TYPE_ARRAY ? air_type_alloc_size(m, et)
                                                       : MAX2(1, air_type_bit_size(et) / 8));
         } else {
            return false;
         }
         if (k->ckind == AIR_CONST_DATA) {
            unsigned bytes = MAX2(1, DIV_ROUND_UP(air_type_bit_size(et), 8));
            if (bytes > 8 || eo + bytes > size)
               return false;
            memcpy(buf + eo, &k->data[i], bytes);
         } else if (!herolte_const_bytes(m, k->elems[i], et, buf, size, eo)) {
            return false;
         }
      }
      return true;
   default:
      return false;
   }
}

/* HEROLTE: every scratch global with an initializer gets it, in 32-bit words (bytes for a tail). */
static void
herolte_global_initializers(struct air_ctx *c)
{
   for (unsigned i = 0; i < c->m->num_globals; i++) {
      const struct air_global_plan *pl = &c->global_plan[i];
      const struct air_global *g = c->m->globals[i];
      if (pl->skip || pl->class != AIR_PTR_SCRATCH || !pl->has_offset || !g->init)
         continue;
      uint64_t size = air_type_alloc_size(c->m, g->value_type);
      if (!size || size > 65536)
         continue;
      uint8_t *buf = rzalloc_size(c->mem_ctx, size);
      if (!buf || !herolte_const_bytes(c->m, g->init, g->value_type, buf, size, 0))
         continue;   /* left to the static initializers, as before */
      uint64_t o = 0;
      for (; pl->offset % 4 == 0 && o + 4 <= size; o += 4) {
         uint32_t w;
         memcpy(&w, buf + o, 4);
         nir_store_scratch(&c->b, nir_imm_int(&c->b, w), nir_imm_int(&c->b, pl->offset + o), .align_mul = 4,
                           .write_mask = 1);
      }
      for (; o < size; o++)
         nir_store_scratch(&c->b, nir_imm_intN_t(&c->b, buf[o], 8), nir_imm_int(&c->b, pl->offset + o),
                           .align_mul = 1, .write_mask = 1);
   }
}

static void
run_static_initializers(struct air_ctx *c)
{
   herolte_global_initializers(c);''')

# 6. On the T880 (boot-18k41). pro24MainFragment's own sampler asks for filter::bicubic, which Scion refuses because
# Gallium has no such filter; a wallpaper is better sampled as linear than not drawn, which is what air_run does too.
change('bicubic sampled as linear: no refusal', 'air_metal.c',
       '''   if (a->mag_filter == AIR_SAMPLER_BICUBIC || a->min_filter == AIR_SAMPLER_BICUBIC) {
      say(why, why_size, "the shader's own sampler at index %u asks for filter::bicubic, "
                         "which neither MTLSamplerDescriptor nor this GPU has", index);
      return false;
   }
''',
       '''   /* HEROLTE: filter::bicubic is sampled as linear (the table below), as air_run does: MercuryPoster's
    * pro24MainFragment asks for it, and Gallium has no bicubic filter. */
''')
change('bicubic sampled as linear: table', 'air_metal.c',
       '''      [AIR_SAMPLER_LINEAR] = RWA_FILTER_LINEAR,
   };''',
       '''      [AIR_SAMPLER_LINEAR] = RWA_FILTER_LINEAR,
      [AIR_SAMPLER_BICUBIC] = RWA_FILTER_LINEAR,   /* HEROLTE */
   };''')

# 7. Midgard has no b2i8 ("MESA: error: Unhandled ALU op b2i8", shippou::one::compute, boot-18k41): the frontend's 8-bit
# integers made from booleans (uchar flags) are made at 32 bits and narrowed after, which Midgard and softpipe both have.
change('b2i8 at 32 bits: callback', 'air_metal.c',
       '''static void
finalize_for_gallium(nir_shader *nir, struct pipe_screen *screen, unsigned ubo_base)
{''',
       '''/* HEROLTE: which ALU instructions nir_lower_bit_size widens: b2i8, which Midgard cannot emit. */
static unsigned
herolte_widen_bit_size(const nir_instr *instr, void *data)
{
   (void)data;
   if (instr->type != nir_instr_type_alu)
      return 0;
   return nir_instr_as_alu(instr)->op == nir_op_b2i8 ? 32 : 0;
}

static void
finalize_for_gallium(nir_shader *nir, struct pipe_screen *screen, unsigned ubo_base)
{''')
change('b2i8 at 32 bits: pass', 'air_metal.c',
       '''   NIR_PASS(_, nir, nir_lower_system_values);
''',
       '''   NIR_PASS(_, nir, nir_lower_bit_size, herolte_widen_bit_size, NULL);   /* HEROLTE: b2i8 */
   NIR_PASS(_, nir, nir_lower_system_values);
''')

# 9. The b2i8 of 7 came back: Panfrost's own nir_opt_algebraic folds u2u8(b2i32(x)) into b2i8(x) again
# (boot-18k43, shippou::one::compute: "Unhandled ALU op b2i8" three times, then minutes in mir_ra). Midgard itself,
# after nir_lower_bool_to_int32 (no nir_opt_algebraic runs after it), makes b2i8(x) as (x & 1) narrowed one size at a
# time, which is how Midgard narrows (a move with a destination override per step).
change('Midgard b2i8: pass', '../../panfrost/midgard/midgard_compile.c',
       '''   /* We implement booleans as 32-bit 0/~0 */
   NIR_PASS(progress, nir, nir_lower_bool_to_int32);
''',
       '''   /* We implement booleans as 32-bit 0/~0 */
   NIR_PASS(progress, nir, nir_lower_bool_to_int32);
   NIR_PASS(progress, nir, nir_shader_instructions_pass, herolte_lower_b2i8, nir_metadata_control_flow, NULL);
''')
change('Midgard b2i8: callback', '../../panfrost/midgard/midgard_compile.c',
       '''static void
optimise_nir(nir_shader *nir, unsigned quirks, bool is_blend)
{''',
       '''/* HEROLTE: b2i8, which Midgard has no instruction for: (x & 1) at 32 bits, then 16, then 8. */
static bool
herolte_lower_b2i8(nir_builder *b, nir_instr *instr, void *data)
{
   if (instr->type != nir_instr_type_alu)
      return false;
   nir_alu_instr *alu = nir_instr_as_alu(instr);
   if (alu->op != nir_op_b2i8)
      return false;
   b->cursor = nir_before_instr(instr);
   nir_def *x = nir_ssa_for_alu_src(b, alu, 0);
   if (x->bit_size != 32)
      x = nir_b2i32(b, x);
   else
      x = nir_iand_imm(b, x, 1);
   nir_def_replace(&alu->def, nir_u2u8(b, nir_u2u16(b, x)));
   return true;
}

static void
optimise_nir(nir_shader *nir, unsigned quirks, bool is_blend)
{''')

# 10. A fragment shader's 16-bit colour outputs (Metal's half4, f16vec4 FRAG_RESULT_DATA0) are written at 32 bits.
# Midgard's writeout hands the tile buffer 32-bit registers: on the T880 postFragment's half4 came back as
# (0.0007, 0.0078, nan, nan) in RGBA32Float -- the halves (x,y),(z,w=1.0 = 0x3c00) read as two floats (boot-18k44).
change('fragment outputs at 32 bits: callback', 'air_metal.c',
       '''/* HEROLTE: which ALU instructions nir_lower_bit_size widens''',
       '''/* HEROLTE: a fragment shader's 16-bit store_output made a 32-bit one, of the same base type. */
static bool
herolte_widen_fs_output(nir_builder *b, nir_intrinsic_instr *intr, void *data)
{
   (void)data;
   if (intr->intrinsic != nir_intrinsic_store_output)
      return false;
   nir_alu_type t = nir_intrinsic_src_type(intr);
   if (nir_alu_type_get_type_size(t) != 16)
      return false;
   nir_alu_type base = nir_alu_type_get_base_type(t);
   b->cursor = nir_before_instr(&intr->instr);
   nir_def *v = intr->src[0].ssa;
   v = base == nir_type_float ? nir_f2f32(b, v) : base == nir_type_int ? nir_i2i32(b, v) : nir_u2u32(b, v);
   nir_src_rewrite(&intr->src[0], v);
   nir_intrinsic_set_src_type(intr, base | 32);
   return true;
}

/* HEROLTE: which ALU instructions nir_lower_bit_size widens''')
change('fragment outputs at 32 bits: pass', 'air_metal.c',
       '''            type_size_vec4, nir_lower_io_use_interpolated_input_intrinsics);
   /*
    * B2L (B1L-0058)''',
       '''            type_size_vec4, nir_lower_io_use_interpolated_input_intrinsics);
   if (nir->info.stage == MESA_SHADER_FRAGMENT) {   /* HEROLTE: 32-bit colour outputs */
      NIR_PASS(_, nir, nir_shader_intrinsics_pass, herolte_widen_fs_output, nir_metadata_control_flow, NULL);
      nir_foreach_shader_out_variable(var, nir) {
         const struct glsl_type *t = var->type;
         if (!glsl_type_is_vector_or_scalar(t))
            continue;
         enum glsl_base_type bt = glsl_get_base_type(t);
         if (bt == GLSL_TYPE_FLOAT16 || bt == GLSL_TYPE_INT16 || bt == GLSL_TYPE_UINT16)
            var->type = glsl_vector_type(bt == GLSL_TYPE_FLOAT16 ? GLSL_TYPE_FLOAT :
                                         bt == GLSL_TYPE_INT16 ? GLSL_TYPE_INT : GLSL_TYPE_UINT,
                                         glsl_get_vector_elements(t));
      }
   }
   /*
    * B2L (B1L-0058)''')

# 11. A texture the fragment shader declares and the application left unbound reads zeros, as it does on Apple's GPUs,
# instead of refusing the draw. iOS 18's default wallpaper (MercuryPoster's fluidity style) binds texture 0 alone to
# fluidity::fragmentShader, which declares two: every frame of its second pass was refused ("reads texture 1 and 1
# texture was bound", boot-18k49) and only the first pass reached the screen. A 1x1 texture of zeros of the declared
# kind and element type goes in each such slot (ios-b1lte did the same for SpringBoard, B1L-0228/0229).
change('unbound textures read zeros: helpers', 'air_metal.c',
       '''int
rwa_render_draw(struct rwa_render *render, const struct rwa_draw *draw,
                char *why, size_t why_size)
{''',
       '''/* HEROLTE: a 1x1 texture of zeros of one kind and element type, made once per device. */
static struct rwa_texture *
herolte_zero_texture(struct rwa_device *device, unsigned type, nir_alu_type element, bool shadow)
{
   static struct { struct rwa_device *device; unsigned type, format; struct rwa_texture *t; } made[24];
   static unsigned nmade;
   /* RGBA8Unorm, RGBA8Uint, RGBA8Sint; Depth32Float for a depth2d a comparison reads */
   unsigned format = shadow ? 252 : element == nir_type_uint ? 73 : element == nir_type_int ? 74 : 70;
   for (unsigned i = 0; i < nmade; i++)
      if (made[i].device == device && made[i].type == type && made[i].format == format)
         return made[i].t;
   if (nmade == ARRAY_SIZE(made))
      return NULL;
   bool cube = type == RWA_TYPE_CUBE || type == RWA_TYPE_CUBE_ARRAY;
   bool ms = type == RWA_TYPE_2D_MULTISAMPLE || type == RWA_TYPE_2D_MULTISAMPLE_ARRAY;
   struct rwa_texture_shape shape = {
      .pixel_format = format, .type = type, .width = 1, .height = 1, .depth = 1, .array_length = 1,
      .mip_levels = 1, .sample_count = ms ? 4 : 1, .usage = 1,   /* MTLTextureUsageShaderRead */
   };
   char why[256];
   struct rwa_texture *t = rwa_texture_create(device, &shape, why, sizeof(why));
   if (!t) {
      fprintf(stderr, "herolte: no zero texture of type %u, format %u: %s\\n", type, format, why);
      return NULL;
   }
   if (!shadow && !ms) {
      static const uint32_t zero[4];
      const unsigned origin[3] = { 0, 0, 0 }, size[3] = { 1, 1, 1 };
      for (unsigned layer = 0; layer < (cube ? 6u : 1u); layer++)
         rwa_texture_write(t, 0, layer, origin, size, zero, 0, why, sizeof(why));
   }
   made[nmade].device = device;
   made[nmade].type = type;
   made[nmade].format = format;
   made[nmade].t = t;
   nmade++;
   return t;
}

/* HEROLTE: *out is *in, with a zero texture in every declared, unbound texture slot. */
static void
herolte_fill_unbound(struct rwa_device *device, const struct air_shader_info *info,
                     const struct rwa_slot *slots, const struct rwa_bindings *in,
                     struct rwa_bindings *out, struct rwa_texture **storage)
{
   bool changed = false;
   unsigned count = in->texture_count;
   *out = *in;
   for (unsigned i = 0; i < info->num_resources; i++) {
      const struct air_resource *r = &info->resources[i];
      if (r->kind != AIR_RESOURCE_TEXTURE || r->argbuf_set != ~0u || r->index >= RWA_MAX_TEXTURES)
         continue;
      if (r->index < in->texture_count && in->textures[r->index])
         continue;
      if (!changed) {
         memset(storage, 0, RWA_MAX_TEXTURES * sizeof(*storage));
         for (unsigned k = 0; k < in->texture_count && k < RWA_MAX_TEXTURES; k++)
            storage[k] = in->textures[k];
         changed = true;
      }
      const struct rwa_slot *s = &slots[r->index];
      unsigned type = RWA_TYPE_2D;
      if (s->shape_known && !metal_texture_type(s->dim, s->is_array, &type))
         type = RWA_TYPE_2D;
      nir_alu_type element = nir_type_float;
      const char *word;
      if (!slot_element(s, &element, &word, NULL))
         element = nir_type_float;
      storage[r->index] = herolte_zero_texture(device, type, element, s->shadow);
      count = MAX2(count, r->index + 1);
   }
   if (changed) {
      out->textures = storage;
      out->texture_count = count;
   }
}

int
rwa_render_draw(struct rwa_render *render, const struct rwa_draw *draw,
                char *why, size_t why_size)
{
   /* HEROLTE: the fragment stage's unbound textures read zeros (herolte_fill_unbound) */
   struct rwa_draw herolte_draw;
   struct rwa_texture *herolte_ftex[RWA_MAX_TEXTURES];
   if (draw) {
      herolte_draw = *draw;
      herolte_fill_unbound(render->device, &render->finfo, render->frag_slots, &draw->fragment,
                           &herolte_draw.fragment, herolte_ftex);
      draw = &herolte_draw;
   }''')

# 12. 8- and 16-bit loads from constant buffers, made as a 32-bit load of the aligned word, shifted and narrowed.
# fluidity::sdfFragmentShader picks the channel of its SDF from a `bool` of its uniforms (an 8-bit load_ubo at offset
# 8): on the T880 every draw went to R and G stayed 0 (boot-18k53, the RG32Float attachment read back), so the second
# pass, which reads G, drew no shape. Midgard reads the whole word for such a load, and the bytes beside the bool made
# the comparison with 0 fail. Every `bool`, `uchar`, `short` of a constant buffer goes through here.
change('narrow constant-buffer loads: callback', 'air_metal.c',
       '''/* HEROLTE: a fragment shader's 16-bit store_output made a 32-bit one, of the same base type. */''',
       '''/* HEROLTE: an 8- or 16-bit load_ubo as 32-bit loads of the words that hold it, each byte or half shifted out. */
static bool
herolte_widen_ubo_load(nir_builder *b, nir_intrinsic_instr *intr, void *data)
{
   (void)data;
   if (intr->intrinsic != nir_intrinsic_load_ubo || intr->def.bit_size >= 32)
      return false;
   unsigned bits = intr->def.bit_size, bytes = bits / 8;
   b->cursor = nir_before_instr(&intr->instr);
   nir_def *block = intr->src[0].ssa, *offset = intr->src[1].ssa;
   nir_def *comps[NIR_MAX_VEC_COMPONENTS];
   for (unsigned i = 0; i < intr->def.num_components; i++) {
      nir_def *at = nir_iadd_imm(b, offset, i * bytes);
      nir_def *word = nir_load_ubo(b, 1, 32, block, nir_iand_imm(b, at, ~3u), .access = nir_intrinsic_access(intr),
                                   .align_mul = 4, .align_offset = 0, .range_base = 0, .range = ~0u);
      nir_def *shift = nir_ishl_imm(b, nir_iand_imm(b, at, 3), 3);
      comps[i] = nir_u2uN(b, nir_ushr(b, word, shift), bits);
   }
   nir_def_replace(&intr->def, nir_vec(b, comps, intr->def.num_components));
   return true;
}

/* HEROLTE: a fragment shader's 16-bit store_output made a 32-bit one, of the same base type. */''')
change('narrow constant-buffer loads: pass', 'air_metal.c',
       '''   NIR_PASS(_, nir, nir_lower_bit_size, herolte_widen_bit_size, NULL);   /* HEROLTE: b2i8 */
''',
       '''   NIR_PASS(_, nir, nir_lower_bit_size, herolte_widen_bit_size, NULL);   /* HEROLTE: b2i8 */
   NIR_PASS(_, nir, nir_shader_intrinsics_pass, herolte_widen_ubo_load, nir_metadata_control_flow,
            NULL);   /* HEROLTE: 8/16-bit constant-buffer loads */
''')

print('air-herolte: ' + ', '.join(done))

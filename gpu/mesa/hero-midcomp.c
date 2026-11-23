/*
 * hero-midcomp: one function of a .metallib through what the phone's libhakiosair does with it, on the PC, for the
 * Galaxy S7's Mali-T880 (Midgard, gpu_id 0x0880): the AIR front end (air_to_nir, the same patches as the phone's), the
 * I/O lowering libhakiosair does before Gallium sees the shader, midgard_preprocess_nir and midgard_compile_shader_nir.
 * After ios-b1lte's b2l-bicomp (userspace/mesa/b2l-bicomp.c, MIT), which does the same for Bifrost.
 *
 * Boot 26k7k: backboardd on Metal spent 150 s and more in Midgard's compiler on QuartzCore's first fragment function
 * (A2Xghfc) and never drew. This tool times each step for one function, so the slow one can be found and fixed here.
 *
 *   hero-midcomp LIB.metallib --fn NAME [--gpu 0xNNNN] [--nir]
 *   hero-midcomp LIB.metallib --list
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "compiler/nir/nir.h"
#include "compiler/nir/nir_builder.h"
#include "compiler/air/nir_air.h"
#include "panfrost/midgard/midgard_compile.h"
#include "util/ralloc.h"
#include "util/u_dynarray.h"

static double
now(void)
{
   struct timespec t;
   clock_gettime(CLOCK_MONOTONIC, &t);
   return t.tv_sec + t.tv_nsec / 1e9;
}

static int
type_size_vec4(const struct glsl_type *type, bool bindless)
{
   (void)bindless;
   return glsl_count_attribute_slots(type, false);
}

/* what panfrost's Gallium lowering turns into sysval UBO reads on the phone; a UBO read here too */
static bool
zero_gallium_sysvals(nir_builder *b, nir_intrinsic_instr *intr, void *data)
{
   (void)data;
   switch (intr->intrinsic) {
   case nir_intrinsic_load_rt_conversion_pan:
   case nir_intrinsic_load_viewport_scale:
   case nir_intrinsic_load_viewport_offset:
   case nir_intrinsic_load_base_instance:
   case nir_intrinsic_load_base_vertex:
   case nir_intrinsic_load_first_vertex:
   case nir_intrinsic_load_ssbo_address:
      break;
   default:
      return false;
   }
   b->cursor = nir_before_instr(&intr->instr);
   nir_def_replace(&intr->def, nir_load_ubo(b, intr->def.num_components, intr->def.bit_size, nir_imm_int(b, 0),
                                            nir_imm_int(b, 0), .align_mul = 4, .align_offset = 0,
                                            .range_base = 0, .range = ~0));
   return true;
}

static unsigned
count_instrs(nir_shader *nir)
{
   unsigned n = 0;
   nir_foreach_function_impl(impl, nir) {
      nir_foreach_block(block, impl) {
         nir_foreach_instr(instr, block)
            n++;
      }
   }
   return n;
}

static unsigned
count_blocks(nir_shader *nir)
{
   unsigned n = 0;
   nir_foreach_function_impl(impl, nir) {
      nir_foreach_block(block, impl)
         n++;
   }
   return n;
}

int
main(int argc, char **argv)
{
   const char *path = NULL, *fn = NULL;
   bool list = false, print = false;
   unsigned gpu_id = 0x0880;

   for (int i = 1; i < argc; i++) {
      if (!strcmp(argv[i], "--fn") && i + 1 < argc)
         fn = argv[++i];
      else if (!strcmp(argv[i], "--gpu") && i + 1 < argc)
         gpu_id = strtoul(argv[++i], NULL, 0);
      else if (!strcmp(argv[i], "--list"))
         list = true;
      else if (!strcmp(argv[i], "--nir"))
         print = true;
      else
         path = argv[i];
   }
   if (!path || (!fn && !list)) {
      fprintf(stderr, "usage: hero-midcomp LIB.metallib --fn NAME [--gpu 0xNNNN] [--nir] | --list\n");
      return 2;
   }
   FILE *f = fopen(path, "rb");
   if (!f) {
      perror(path);
      return 2;
   }
   fseek(f, 0, SEEK_END);
   long size = ftell(f);
   fseek(f, 0, SEEK_SET);
   void *data = malloc(size);
   if (fread(data, 1, size, f) != (size_t)size)
      return 2;
   fclose(f);

   glsl_type_singleton_init_or_ref();
   void *ctx = ralloc_context(NULL);
   struct air_metallib lib;
   const char *lerr = NULL;
   if (!air_metallib_parse(ctx, data, size, &lib, &lerr)) {
      printf("%s: %s\n", path, lerr ? lerr : "not a metallib");
      return 2;
   }
   const void *code = NULL;
   size_t code_size = 0;
   for (unsigned i = 0; i < lib.num_functions; i++) {
      if (list)
         printf("%s %zu\n", lib.functions[i].name, (size_t)lib.functions[i].bitcode_size);
      else if (!strcmp(lib.functions[i].name, fn)) {
         code = lib.functions[i].bitcode;
         code_size = lib.functions[i].bitcode_size;
      }
   }
   if (list)
      return 0;
   if (!code) {
      printf("%s: no function %s\n", path, fn);
      return 2;
   }

   double t0 = now();
   struct air_constant_value *fc;
   unsigned nfc = air_module_function_constants(ctx, code, code_size, &fc);
   struct air_to_nir_options opts = { .constants = fc, .num_constants = nfc };
   struct air_shader_info info;
   const char *err = NULL;
   nir_shader *nir = air_to_nir(ctx, code, code_size, NULL, &opts, &midgard_nir_options, &info, &err);
   if (!nir) {
      printf("%s: translate FAILED: %s\n", fn, err ? err : "?");
      return 1;
   }
   double t1 = now();
   printf("%s: %zu bytes of AIR, %u function constants; air_to_nir %.2f s: %u NIR instructions, %u blocks\n", fn,
          code_size, nfc, t1 - t0, count_instrs(nir), count_blocks(nir));
   fflush(stdout);
   if (getenv("HERO_NIR_AIR"))   /* what the AIR front end hands over, before any lowering */
      nir_print_shader(nir, stdout);

   NIR_PASS(_, nir, nir_lower_io, nir_var_shader_in | nir_var_shader_out, type_size_vec4,
            nir_lower_io_use_interpolated_input_intrinsics);
   NIR_PASS(_, nir, nir_lower_system_values);
   nir_shader_gather_info(nir, nir_shader_get_entrypoint(nir));
   midgard_preprocess_nir(nir, gpu_id);
   NIR_PASS(_, nir, nir_shader_intrinsics_pass, zero_gallium_sysvals, nir_metadata_control_flow, NULL);
   double t2 = now();
   printf("%s: preprocess %.2f s: %u NIR instructions, %u blocks\n", fn, t2 - t1, count_instrs(nir), count_blocks(nir));
   fflush(stdout);
   if (print)
      nir_print_shader(nir, stdout);

   struct panfrost_compile_inputs inputs = { .gpu_id = gpu_id };
   struct util_dynarray binary;
   util_dynarray_init(&binary, NULL);
   struct pan_shader_info pinfo;
   memset(&pinfo, 0, sizeof(pinfo));
   midgard_compile_shader_nir(nir, &inputs, &binary, &pinfo);
   double t3 = now();
   printf("%s: %s, midgard_compile_shader_nir %.2f s: %u bytes of Midgard code, %u work registers, %u TLS bytes\n", fn,
          gl_shader_stage_name(nir->info.stage), t3 - t2, binary.size, pinfo.work_reg_count, pinfo.tls_size);
   util_dynarray_fini(&binary);
   ralloc_free(ctx);
   return 0;
}

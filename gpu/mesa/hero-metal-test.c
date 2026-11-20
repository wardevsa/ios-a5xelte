/*
 * hero_metal_test: one Metal pipeline of a .metallib through libhakiosair (Scion's air_metal.h, rwa_*) on the
 * S7's Mali-T880, given what the SHADER declares rather than a fixed test shape (docs/herolte-metal.md, M2).
 *
 *   hero_metal_test [options] LIB --list
 *   hero_metal_test [options] LIB VERTEX FRAGMENT     a render pipeline; VERTEX "-" lets the library supply a quad
 *   hero_metal_test [options] LIB KERNEL              a compute pipeline
 *
 * options: -s WxH (32x32) attachment / grid size, -f FMT (125, RGBA32Float) colour format, -c N colour attachments,
 *          -z fill buffers with small floats instead of zeros, -t SEC (60) give up after SEC seconds with a backtrace,
 *          -l X,Y,Z threads per group (8,8,1).
 *
 * Every texture slot gets a texture of the declared kind (2D, 3D, cube, array; float, int or uint elements) filled
 * with a gradient, every buffer index 64 KB, every sampler a linear clamped one. Vertex attributes are configured
 * as Float4 from one stream at buffer index 30 and switched to Int4/UInt4 when the library says the shader wants
 * integers. What comes back: the compile and draw times, a few pixels, how many pixels differ from the clear colour
 * and how many are NaN.
 *
 * The .metallib reader is Scion's (air_metal_test.c, MIT, Scion-Project/hackios-xnu-kernel).
 */
#include <errno.h>
#include <execinfo.h>
#include <math.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include "air_metal.h"

#define BUF_BYTES (64 * 1024)
#define STREAM_INDEX 30
#define MAX_TEX 16
#define MAX_BUF 31

static char why[1024];
static const char *volatile stage = "starting";

static double
now(void)
{
   struct timespec t;
   clock_gettime(CLOCK_MONOTONIC, &t);
   return t.tv_sec + t.tv_nsec / 1e9;
}

static void
on_alarm(int sig)
{
   (void)sig;
   char msg[160];
   int n = snprintf(msg, sizeof(msg), "hero_metal_test: TIMEOUT while %s; where the main thread is:\n", stage);
   write(1, msg, n);
   void *frames[48];
   int count = backtrace(frames, 48);
   backtrace_symbols_fd(frames, count, 1);
   _exit(3);
}

/* ---- the .metallib, as Scion's air_metal_test reads it ---- */
struct lib {
   uint8_t *bytes;
   size_t size;
};

static uint64_t u64_at(const struct lib *l, size_t o) { uint64_t v = 0; if (o + 8 <= l->size) memcpy(&v, l->bytes + o, 8); return v; }
static uint32_t u32_at(const struct lib *l, size_t o) { uint32_t v = 0; if (o + 4 <= l->size) memcpy(&v, l->bytes + o, 4); return v; }
static uint16_t u16_at(const struct lib *l, size_t o) { uint16_t v = 0; if (o + 2 <= l->size) memcpy(&v, l->bytes + o, 2); return v; }

/* Calls `each` for every function; stops when it returns true. */
static bool
functions(const struct lib *l, bool (*each)(const char *, const uint8_t *, size_t, void *), void *ctx)
{
   if (l->size < 0x58 || memcmp(l->bytes, "MTLB", 4) != 0) {
      printf("hero_metal_test: not a .metallib\n");
      return false;
   }
   size_t list = u64_at(l, 0x18), list_end = u64_at(l, 0x20);
   uint64_t bc_off = u64_at(l, 0x48), bc_len = u64_at(l, 0x50);
   unsigned count = u32_at(l, list);
   if (list_end > l->size || list_end < list || count > (list_end - list) / 8) {
      printf("hero_metal_test: a damaged function list\n");
      return false;
   }
   size_t p = list + 4;
   for (unsigned i = 0; i < count; i++) {
      uint64_t off = 0, len = 0;
      char name[256] = "";
      uint32_t size = u32_at(l, p);
      size_t q = p + 4, end = p + size;
      while (q + 6 <= end && q + 6 <= l->size) {
         if (!memcmp(l->bytes + q, "ENDT", 4))
            break;
         uint16_t tlen = u16_at(l, q + 4);
         if (!memcmp(l->bytes + q, "NAME", 4))
            snprintf(name, sizeof(name), "%.*s", (int)tlen, (const char *)l->bytes + q + 6);
         else if (!memcmp(l->bytes + q, "OFFT", 4) && tlen >= 24)
            off = u64_at(l, q + 6 + 16);
         else if (!memcmp(l->bytes + q, "MDSZ", 4) && tlen >= 8)
            len = u64_at(l, q + 6);
         q += 6 + tlen;
      }
      uint64_t start = bc_off + off, stop = start + len;
      bool ok = start < l->size && stop <= l->size && stop > start && stop <= bc_off + bc_len;
      if (each(name, ok ? l->bytes + start : NULL, ok ? stop - start : 0, ctx))
         return true;
      p = end;
   }
   return false;
}

static bool
print_one(const char *name, const uint8_t *bc, size_t size, void *ctx)
{
   (void)bc;
   (void)ctx;
   printf("  %s (%zu bytes)\n", name, size);
   return false;
}

struct find {
   const char *want;
   const uint8_t *bc;
   size_t size;
};

static bool
find_one(const char *name, const uint8_t *bc, size_t size, void *ctx)
{
   struct find *f = ctx;
   if (strcmp(name, f->want))
      return false;
   f->bc = bc;
   f->size = size;
   return true;
}

static bool
find(const struct lib *l, const char *want, const uint8_t **bc, size_t *size)
{
   struct find f = { want, NULL, 0 };
   if (!functions(l, find_one, &f) || !f.bc) {
      printf("hero_metal_test: no function %s in the library\n", want);
      return false;
   }
   *bc = f.bc;
   *size = f.size;
   return true;
}

/* ---- resources ---- */
static unsigned W = 32, H = 32;
static bool float_fill;

static struct rwa_buffer *
make_buffer(struct rwa_device *dev)
{
   struct rwa_buffer *b = rwa_buffer_create(dev, BUF_BYTES, why, sizeof(why));
   if (!b) {
      printf("hero_metal_test: buffer: %s\n", why);
      return NULL;
   }
   uint32_t *w = rwa_buffer_map(b);
   for (unsigned i = 0; i < BUF_BYTES / 4; i++) {
      float f = ((i * 37) % 200) / 200.0f + 0.0025f;   /* (0, 1): positions, colours and factors stay finite */
      w[i] = 0;
      if (float_fill)
         memcpy(&w[i], &f, 4);
   }
   return b;
}

static const char *
type_name(unsigned t)
{
   static const char *n[] = { "1d", "1d array", "2d", "2d array", "2d ms", "cube", "cube array", "3d",
                              "2d ms array", "buffer" };
   return t < 10 ? n[t] : "?";
}

/* One texture of the kind the shader declares, with a gradient in it. */
static struct rwa_texture *
make_texture(struct rwa_device *dev, const struct rwa_texture_decl *d)
{
   unsigned type = d->type_known ? d->type : 2;
   bool depth = !strncmp(d->metal_type, "depth", 5);
   struct rwa_texture_shape s = {
      .pixel_format = depth ? 252 : d->element == RWA_ELEMENT_INT ? 124 : d->element == RWA_ELEMENT_UINT ? 123 : 125,
      .type = type,
      .width = 16, .height = (type == 0 || type == 1) ? 1 : 16, .depth = type == 7 ? 16 : 1,
      .array_length = (type == 1 || type == 3 || type == 6 || type == 8) ? 2 : 1,
      .mip_levels = 1,
      .sample_count = (type == 4 || type == 8) ? 4 : 1,
      .usage = d->usage | 1,
   };
   if (type == 5 || type == 6)
      s.height = s.width;
   struct rwa_texture *t = rwa_texture_create(dev, &s, why, sizeof(why));
   printf("hero_metal_test:   texture %u: %s \"%s\", format %u%s%s\n", d->index, type_name(type), d->metal_type,
          s.pixel_format, d->type_known ? "" : " (kind not declared: 2d)", t ? "" : " -- REFUSED");
   if (!t) {
      printf("hero_metal_test:   %s\n", why);
      return NULL;
   }
   if (depth || s.sample_count > 1)
      return t;
   unsigned layers = s.array_length * ((type == 5 || type == 6) ? 6 : 1);
   unsigned n = s.width * s.height * s.depth;
   uint32_t *texels = malloc(n * 16);
   for (unsigned z = 0; z < s.depth; z++)
      for (unsigned y = 0; y < s.height; y++)
         for (unsigned x = 0; x < s.width; x++) {
            uint32_t *p = texels + 4 * ((z * s.height + y) * s.width + x);
            if (s.pixel_format == 125) {
               float f[4] = { (x + 0.5f) / s.width, (y + 0.5f) / s.height, (z + 0.5f) / s.depth, 1 };
               memcpy(p, f, 16);
            } else {
               p[0] = x, p[1] = y, p[2] = z, p[3] = 1;
            }
         }
   for (unsigned layer = 0; layer < layers; layer++) {
      unsigned origin[3] = { 0, 0, 0 }, size[3] = { s.width, s.height, s.depth };
      if (rwa_texture_write(t, 0, layer, origin, size, texels, 0, why, sizeof(why))) {
         printf("hero_metal_test:   texture %u layer %u not written: %s\n", d->index, layer, why);
         break;
      }
   }
   free(texels);
   return t;
}

/* Fills `tex` (indexed by Metal slot) for every texture the function declares; returns the slot count. */
static int
make_textures(struct rwa_device *dev, const uint8_t *bc, size_t size, const char *entry, struct rwa_texture **tex)
{
   struct rwa_texture_decl d[MAX_TEX];
   unsigned count = 0, slots = 0;
   if (rwa_module_textures(dev, bc, size, entry, d, MAX_TEX, &count, why, sizeof(why))) {
      printf("hero_metal_test: %s: textures: %s\n", entry, why);
      return -1;
   }
   for (unsigned i = 0; i < count; i++) {
      tex[d[i].index] = make_texture(dev, &d[i]);
      if (d[i].index + 1 > slots)
         slots = d[i].index + 1;
   }
   return slots;
}

static struct rwa_sampler *
make_sampler(struct rwa_device *dev)
{
   struct rwa_sampler_state s = {
      .min_filter = 1, .mag_filter = 1, .max_anisotropy = 1, .normalized_coordinates = 1,
      .lod_min = 0, .lod_max = 1000, .compare_function = 7,
   };
   struct rwa_sampler *r = rwa_sampler_create(dev, &s, why, sizeof(why));
   if (!r)
      printf("hero_metal_test: sampler: %s\n", why);
   return r;
}

static unsigned
pixel_bytes(unsigned fmt)
{
   switch (fmt) {
   case 123: case 124: case 125: return 16;
   case 105: case 110: case 115: return 8;   /* RG32Float, RGBA16Unorm.. RGBA16Float */
   default: return 4;
   }
}

static void
report_pixels(unsigned att, unsigned fmt, const uint8_t *px, const float clear[4])
{
   unsigned bpp = pixel_bytes(fmt), differ = 0, nans = 0;
   for (unsigned i = 0; i < W * H; i++) {
      const uint8_t *p = px + i * bpp;
      if (fmt == 125) {
         float f[4];
         memcpy(f, p, 16);
         for (int c = 0; c < 4; c++)
            if (isnan(f[c]))
               nans++;
         if (memcmp(f, clear, 16))
            differ++;
      } else {
         bool zero = true;
         for (unsigned b = 0; b < bpp; b++)
            zero &= p[b] == 0;
         differ += !zero;
      }
   }
   printf("hero_metal_test: attachment %u: %u of %u pixels differ from the clear colour, %u NaN components\n", att,
          differ, W * H, nans);
   unsigned at[4][2] = { { 0, 0 }, { W / 2, H / 2 }, { W / 4, 3 * H / 4 }, { W - 1, H - 1 } };
   for (int k = 0; k < 4; k++) {
      const uint8_t *p = px + (at[k][1] * W + at[k][0]) * bpp;
      if (fmt == 125) {
         float f[4];
         memcpy(f, p, 16);
         printf("hero_metal_test:   (%u,%u) = %g %g %g %g\n", at[k][0], at[k][1], f[0], f[1], f[2], f[3]);
      } else {
         uint32_t w[4] = { 0 };
         memcpy(w, p, bpp);
         printf("hero_metal_test:   (%u,%u) = %08x %08x %08x %08x\n", at[k][0], at[k][1], w[0], w[1], w[2], w[3]);
      }
   }
}

/* ---- render ---- */
static int
render(struct rwa_device *dev, const struct lib *l, const char *vname, const char *fname, unsigned fmt,
       unsigned colors)
{
   const uint8_t *vbc = NULL, *fbc;
   size_t vsize = 0, fsize;
   if (strcmp(vname, "-") && !find(l, vname, &vbc, &vsize))
      return 1;
   if (!find(l, fname, &fbc, &fsize))
      return 1;

   struct rwa_render_shape shape = { .color_count = colors, .sample_count = 1 };
   for (unsigned i = 0; i < colors; i++)
      shape.color_format[i] = fmt;
   for (unsigned a = 0; a < 16; a++)
      shape.vertex_attribute[a] = (struct rwa_vertex_attribute){ 31, a * 16, STREAM_INDEX };
   shape.vertex_layout[STREAM_INDEX] = (struct rwa_vertex_layout){ 256, 1, 1 };

   struct rwa_render_info info;
   struct rwa_render *r = NULL;
   double t0 = now(), t1 = t0;
   stage = "compiling the render pipeline";
   for (int attempt = 0; attempt < 17 && !r; attempt++) {
      memset(&info, 0, sizeof(info));
      t0 = now();
      r = rwa_render_create(dev, vbc, vsize, vbc ? vname : NULL, fbc, fsize, fname, &shape, &info, why, sizeof(why));
      t1 = now();
      unsigned a;
      const char *p = strstr(why, "vertex attribute ");
      if (r || !p || sscanf(p, "vertex attribute %u", &a) != 1 || a >= 16 || !strstr(why, "wants "))
         break;
      unsigned f = strstr(why, "wants signed integer") ? 35 : strstr(why, "wants unsigned integer") ? 39 : 0;
      if (!f || shape.vertex_attribute[a].format == f)
         break;
      printf("hero_metal_test: attribute %u as %s\n", a, f == 35 ? "Int4" : "UInt4");
      shape.vertex_attribute[a].format = f;
   }
   if (!r) {
      printf("hero_metal_test: pipeline REFUSED after %.2f s: %s\n", t1 - t0, why);
      return 1;
   }
   printf("hero_metal_test: pipeline compiled in %.2f s: %u vertex buffers, %u fragment buffers, %u fragment "
          "textures, %u samplers, %u attributes fetched (streams mask 0x%x)%s\n", t1 - t0, info.vertex_buffers,
          info.fragment_buffers, info.fragment_textures, info.fragment_samplers, info.vertex_attribute_count,
          info.vertex_stream_mask, info.generated_vertex_stage ? ", vertex stage supplied" : "");

   stage = "making the resources";
   struct rwa_texture *ftex[MAX_TEX] = { 0 }, *vtex[MAX_TEX] = { 0 };
   int fslots = make_textures(dev, fbc, fsize, fname, ftex);
   int vslots = vbc ? make_textures(dev, vbc, vsize, vname, vtex) : 0;
   if (fslots < 0 || vslots < 0)
      return 1;
   struct rwa_buffer *vbuf[MAX_BUF] = { 0 }, *fbuf[MAX_BUF] = { 0 };
   for (unsigned i = 0; i < info.vertex_buffers && i < MAX_BUF; i++)
      vbuf[i] = make_buffer(dev);
   for (unsigned i = 0; i < info.fragment_buffers && i < MAX_BUF; i++)
      fbuf[i] = make_buffer(dev);
   struct rwa_sampler *smp[MAX_TEX] = { 0 };
   for (unsigned i = 0; i < info.fragment_samplers && i < MAX_TEX; i++)
      smp[i] = make_sampler(dev);

   /* The stream: four corners of the screen, every float attribute the same corner, integers 0. */
   struct rwa_buffer *stream = rwa_buffer_create(dev, 4 * 256, why, sizeof(why));
   if (!stream) {
      printf("hero_metal_test: stream: %s\n", why);
      return 1;
   }
   float *sv = rwa_buffer_map(stream);
   static const float corner[4][2] = { { -1, -1 }, { 1, -1 }, { -1, 1 }, { 1, 1 } };
   for (unsigned v = 0; v < 4; v++)
      for (unsigned a = 0; a < 16; a++) {
         float *e = sv + v * 64 + a * 4;
         e[0] = corner[v][0], e[1] = corner[v][1], e[2] = 0.5f, e[3] = 1;
         if (shape.vertex_attribute[a].format != 31)
            memset(e, 0, 16);
      }
   struct rwa_vertex_stream streams[STREAM_INDEX + 1] = { 0 };
   streams[STREAM_INDEX].buffer = stream;

   struct rwa_texture *color[8] = { 0 };
   for (unsigned i = 0; i < colors; i++) {
      struct rwa_texture_shape s = { fmt, 2, W, H, 1, 1, 1, 1, 1 | 4 };
      color[i] = rwa_texture_create(dev, &s, why, sizeof(why));
      if (!color[i]) {
         printf("hero_metal_test: colour attachment: %s\n", why);
         return 1;
      }
   }
   static const float clear[4] = { 0.125f, 0.25f, 0.375f, 0.5f };
   struct rwa_draw d = {
      .color = color, .color_count = colors, .clear_color = clear,
      .vertex = { vbuf, info.vertex_buffers, vtex, (unsigned)vslots, NULL, 0 },
      .fragment = { fbuf, info.fragment_buffers, ftex, (unsigned)fslots, smp, info.fragment_samplers },
      .primitive = 4, .vertex_start = 0, .vertex_count = 4,
      .vertex_streams = info.vertex_stream_mask ? streams : NULL,
      .vertex_stream_count = info.vertex_stream_mask ? STREAM_INDEX + 1 : 0,
   };
   stage = "drawing";
   t0 = now();
   int err = rwa_render_draw(r, &d, why, sizeof(why));
   if (!err)
      err = rwa_finish(dev, why, sizeof(why));
   t1 = now();
   if (err) {
      printf("hero_metal_test: draw FAILED after %.2f s: %s\n", t1 - t0, why);
      return 1;
   }
   printf("hero_metal_test: drew %ux%u in %.3f s (first draw: includes the GPU's own setup)\n", W, H, t1 - t0);

   /* A second draw, now that everything is resident: the number a frame would cost. */
   t0 = now();
   err = rwa_render_draw(r, &d, why, sizeof(why));
   if (!err)
      err = rwa_finish(dev, why, sizeof(why));
   t1 = now();
   printf("hero_metal_test: second draw %s in %.3f s\n", err ? "FAILED" : "done", t1 - t0);

   stage = "reading back";
   uint8_t *px = malloc(W * H * 16);
   for (unsigned i = 0; i < colors; i++) {
      unsigned origin[3] = { 0, 0, 0 }, size[3] = { W, H, 1 };
      if (rwa_texture_read(color[i], 0, 0, origin, size, px, 0, why, sizeof(why)))
         printf("hero_metal_test: attachment %u not read: %s\n", i, why);
      else
         report_pixels(i, fmt, px, clear);
   }
   free(px);
   return 0;
}

/* ---- compute ---- */
static int
compute(struct rwa_device *dev, const struct lib *l, const char *kname, const unsigned group[3])
{
   const uint8_t *bc;
   size_t size;
   if (!find(l, kname, &bc, &size))
      return 1;
   struct rwa_compute_info info;
   memset(&info, 0, sizeof(info));
   stage = "compiling the kernel";
   double t0 = now();
   struct rwa_compute *c = rwa_compute_create(dev, bc, size, kname, &info, why, sizeof(why));
   double t1 = now();
   if (!c) {
      printf("hero_metal_test: kernel REFUSED after %.2f s: %s\n", t1 - t0, why);
      return 1;
   }
   printf("hero_metal_test: kernel compiled in %.2f s: %u buffers, %u textures, %u samplers, at most %u threads a "
          "group, %u shared bytes\n", t1 - t0, info.buffers, info.textures, info.samplers,
          info.max_threads_per_group, info.static_shared_bytes);

   stage = "making the resources";
   struct rwa_texture *tex[MAX_TEX] = { 0 };
   struct rwa_texture_decl decl[MAX_TEX];
   unsigned ndecl = 0;
   if (rwa_module_textures(dev, bc, size, kname, decl, MAX_TEX, &ndecl, why, sizeof(why))) {
      printf("hero_metal_test: textures: %s\n", why);
      return 1;
   }
   unsigned slots = 0;
   for (unsigned i = 0; i < ndecl; i++) {
      struct rwa_texture_decl d = decl[i];
      tex[d.index] = make_texture(dev, &d);
      slots = d.index + 1 > slots ? d.index + 1 : slots;
   }
   struct rwa_buffer *buf[MAX_BUF] = { 0 };
   for (unsigned i = 0; i < info.buffers && i < MAX_BUF; i++)
      buf[i] = make_buffer(dev);
   struct rwa_sampler *smp[MAX_TEX] = { 0 };
   for (unsigned i = 0; i < info.samplers && i < MAX_TEX; i++)
      smp[i] = make_sampler(dev);

   unsigned gs[3] = { group[0], group[1], group[2] };
   while (info.max_threads_per_group && gs[0] * gs[1] * gs[2] > info.max_threads_per_group)
      gs[gs[0] >= gs[1] ? 0 : 1] /= 2;
   unsigned groups[3] = { (W + gs[0] - 1) / gs[0], (H + gs[1] - 1) / gs[1], 1 };
   struct rwa_bindings b = { buf, info.buffers, tex, slots, smp, info.samplers };
   stage = "dispatching";
   t0 = now();
   int err = rwa_dispatch(c, &b, groups, gs, why, sizeof(why));
   if (!err)
      err = rwa_finish(dev, why, sizeof(why));
   t1 = now();
   if (err) {
      printf("hero_metal_test: dispatch FAILED after %.2f s: %s\n", t1 - t0, why);
      return 1;
   }
   printf("hero_metal_test: dispatched %ux%ux1 groups of %ux%ux%u in %.3f s\n", groups[0], groups[1], gs[0], gs[1],
          gs[2], t1 - t0);

   stage = "reading back";
   for (unsigned i = 0; i < ndecl; i++) {
      if (!(decl[i].usage & 2) || !tex[decl[i].index])
         continue;
      uint8_t *px = calloc(16 * 16, 16);
      unsigned origin[3] = { 0, 0, 0 }, sz[3] = { 16, 16, 1 };
      if (rwa_texture_read(tex[decl[i].index], 0, 0, origin, sz, px, 0, why, sizeof(why))) {
         printf("hero_metal_test: texture %u not read: %s\n", decl[i].index, why);
      } else {
         unsigned saveW = W, saveH = H;
         static const float none[4] = { -1, -1, -1, -1 };
         W = H = 16;
         printf("hero_metal_test: written texture %u:\n", decl[i].index);
         report_pixels(decl[i].index, decl[i].element == RWA_ELEMENT_FLOAT ? 125 : 123, px, none);
         W = saveW, H = saveH;
      }
      free(px);
   }
   for (unsigned i = 0; i < info.buffers && i < MAX_BUF; i++) {
      if (!buf[i])
         continue;
      const uint32_t *w = rwa_buffer_map(buf[i]);
      unsigned nonzero = 0;
      for (unsigned k = 0; k < BUF_BYTES / 4; k++)
         nonzero += w[k] != 0;
      printf("hero_metal_test: buffer %u: %u non-zero words; first %08x %08x %08x %08x\n", i, nonzero, w[0], w[1],
             w[2], w[3]);
   }
   return 0;
}

int
main(int argc, char **argv)
{
   setvbuf(stdout, NULL, _IOLBF, 0);
   unsigned fmt = 125, colors = 1, timeout = 60, group[3] = { 8, 8, 1 };
   int i = 1;
   for (; i < argc && argv[i][0] == '-' && argv[i][1]; i++) {
      if (!strcmp(argv[i], "-s") && i + 1 < argc)
         sscanf(argv[++i], "%ux%u", &W, &H);
      else if (!strcmp(argv[i], "-f") && i + 1 < argc)
         fmt = atoi(argv[++i]);
      else if (!strcmp(argv[i], "-c") && i + 1 < argc)
         colors = atoi(argv[++i]);
      else if (!strcmp(argv[i], "-t") && i + 1 < argc)
         timeout = atoi(argv[++i]);
      else if (!strcmp(argv[i], "-l") && i + 1 < argc)
         sscanf(argv[++i], "%u,%u,%u", &group[0], &group[1], &group[2]);
      else if (!strcmp(argv[i], "-z"))
         float_fill = true;
      else
         break;
   }
   int rest = argc - i;
   if (rest < 2 || rest > 3 || W == 0 || H == 0 || W > 1024 || H > 1024 || colors < 1 || colors > 8) {
      fprintf(stderr, "usage: hero_metal_test [-s WxH] [-f FMT] [-c N] [-z] [-t SEC] [-l X,Y,Z] LIB "
                      "(--list | VERTEX FRAGMENT | KERNEL)\n");
      return 2;
   }

   struct lib l = { 0 };
   FILE *f = fopen(argv[i], "rb");
   if (!f) {
      printf("hero_metal_test: %s: %s\n", argv[i], strerror(errno));
      return 1;
   }
   fseek(f, 0, SEEK_END);
   l.size = ftell(f);
   fseek(f, 0, SEEK_SET);
   l.bytes = malloc(l.size);
   if (fread(l.bytes, 1, l.size, f) != l.size) {
      printf("hero_metal_test: %s: short read\n", argv[i]);
      return 1;
   }
   fclose(f);
   if (rest == 2 && !strcmp(argv[i + 1], "--list"))
      return functions(&l, print_one, NULL) ? 0 : 0;

   signal(SIGALRM, on_alarm);
   alarm(timeout);
   stage = "opening the GPU";
   struct rwa_device *dev = rwa_device_open(why, sizeof(why));
   if (!dev) {
      printf("hero_metal_test: no device: %s\n", why);
      return 1;
   }
   printf("hero_metal_test: device \"%s\"\n", rwa_device_name(dev));
   int rc = rest == 3 ? render(dev, &l, argv[i + 1], argv[i + 2], fmt, colors)
                      : compute(dev, &l, argv[i + 1], group);
   stage = "closing";
   rwa_device_close(dev);
   return rc;
}

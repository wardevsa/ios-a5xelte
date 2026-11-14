/*
 * Galaxy S7 port: the OSMesaSweet* entry points of Bergamota's OSMesa patch
 * (ry-diffusion/Bergamota, gpu-eagl, gpu/eagl/mesa, MIT) over Panfrost and
 * HeroGPU (targets/osmesa/hero_hw.c), appended to osmesa.c by
 * gpu/mesa/patch-mesa.py. The EAGL shim (gpu/eagl/src/osm.c) calls them:
 * the GPU copies CoreAnimation's render targets into the display
 * IOSurfaces instead of glReadPixels + a CPU copy, and samples RGBA8/BGRA8
 * surfaces in place (OSMesaSweetWrapTexture). The writable CPU alias is not
 * implemented (it answers 0).
 */
#include "main/context.h"
#include "main/fbobject.h"
#include "main/teximage.h"
#include "main/texobj.h"
#include "state_tracker/st_cb_eglimage.h"
#include "state_tracker/st_cb_flush.h"
#include "state_tracker/st_cb_texture.h"
#include "util/os_time.h"       /* u_box_2d: util/box.h, already included by osmesa.c */

extern int hero_hw_active(void);
extern struct pipe_resource *hero_hw_surface_resource(uint32_t surface_id, int opaque, unsigned *w, unsigned *h);
extern void hero_hw_surface_sync(uint32_t surface_id);
extern void hero_hw_surface_forget(uint32_t surface_id);

GLAPI int GLAPIENTRY OSMesaSweetActive(void);
GLAPI void GLAPIENTRY OSMesaSweetForgetSurface(uint32_t surface_id);
GLAPI int GLAPIENTRY OSMesaSweetBlit(GLuint name, int is_texture, uint32_t surface_id, int flip, int opaque);
GLAPI void GLAPIENTRY OSMesaSweetStats(double *out, int n);
GLAPI int GLAPIENTRY OSMesaSweetAttachDirect(GLuint name, uint32_t surface_id);
GLAPI void GLAPIENTRY OSMesaSweetDirectSync(uint32_t surface_id);
GLAPI void GLAPIENTRY OSMesaSweetZeroTexture(void);
GLAPI int GLAPIENTRY OSMesaSweetWrapTexture(GLuint name, uint32_t surface_id, int kind, unsigned w, unsigned h);
GLAPI void GLAPIENTRY OSMesaSweetWrapSync(uint32_t surface_id);
GLAPI int GLAPIENTRY OSMesaSweetSurfaceAlias(uint32_t surface_id, void **base, unsigned *bpr, unsigned *w, unsigned *h);
GLAPI void GLAPIENTRY OSMesaSweetAliasSync(uint32_t surface_id);

/* 0 blits, 1 render wait, 2 blit enqueue, 3 blit wait, 4 cache sync, 5 surface lookup, 6 refused (ms) */
static double hero_stats[8];

GLAPI void GLAPIENTRY
OSMesaSweetStats(double *out, int n)
{
   for (int i = 0; i < n && i < 8; i++)
      out[i] = hero_stats[i];
}

GLAPI int GLAPIENTRY
OSMesaSweetActive(void)
{
   const char *e = getenv("HERO_GPU_BLIT");
   return hero_hw_active() && !(e && e[0] == '0');
}

GLAPI void GLAPIENTRY
OSMesaSweetForgetSurface(uint32_t surface_id)
{
   hero_hw_surface_forget(surface_id);
}

/*
 * Copy a renderbuffer (is_texture 0) or level 0 of a texture of the current
 * context into IOSurface `surface_id` with the GPU. `flip` mirrors
 * vertically (GL rows are bottom-up), `opaque` writes alpha 1. 1 on success,
 * 0 when the caller must take the CPU path.
 */
GLAPI int GLAPIENTRY
OSMesaSweetBlit(GLuint name, int is_texture, uint32_t surface_id, int flip, int opaque)
{
   OSMesaContext osmesa = OSMesaGetCurrentContext();
   struct pipe_resource *src = NULL, *dst;
   unsigned dw = 0, dh = 0;

   if (!osmesa || !OSMesaSweetActive())
      return 0;
   struct st_context *st = osmesa->st;
   struct gl_context *ctx = st->ctx;
   struct pipe_context *pipe = st->pipe;
   double t0 = os_time_get_nano() / 1e6;

   FLUSH_VERTICES(ctx, 0, 0);
   if (is_texture) {
      struct gl_texture_object *t = _mesa_lookup_texture(ctx, name);
      if (t)
         src = t->pt;
   } else {
      struct gl_renderbuffer *rb = _mesa_lookup_renderbuffer(ctx, name);
      if (rb)
         src = rb->texture;
   }
   if (!src)
      return 0;
   dst = hero_hw_surface_resource(surface_id, opaque, &dw, &dh);
   double t1 = os_time_get_nano() / 1e6;
   hero_stats[5] += t1 - t0;
   if (!dst) {
      hero_stats[6] += 1;
      return 0;
   }

   unsigned w = MIN2(src->width0, dw), h = MIN2(src->height0, dh);
   struct pipe_blit_info b;
   memset(&b, 0, sizeof(b));
   b.src.resource = src;
   b.src.level = 0;
   b.src.format = src->format;
   /* Flip through the source box: u_blitter takes a negative source height. */
   u_box_2d(0, flip ? (int)h : 0, w, flip ? -(int)h : (int)h, &b.src.box);
   b.dst.resource = dst;
   b.dst.level = 0;
   b.dst.format = dst->format;
   u_box_2d(0, 0, w, h, &b.dst.box);
   b.mask = PIPE_MASK_RGBA;
   b.filter = PIPE_TEX_FILTER_NEAREST;
   pipe->blit(pipe, &b);
   double t2 = os_time_get_nano() / 1e6;
   st_finish(st);
   double t3 = os_time_get_nano() / 1e6;
   hero_hw_surface_sync(surface_id);
   double t4 = os_time_get_nano() / 1e6;
   hero_stats[0] += 1;
   hero_stats[2] += t2 - t1;
   hero_stats[3] += t3 - t2;
   hero_stats[4] += t4 - t3;
   return 1;
}

/*
 * Zero-copy display buffer: level 0 of texture `name` becomes the memory of
 * IOSurface `surface_id` (like glEGLImageTargetTexture2DOES). The shim uses
 * it only when asked (BGL_DIRECT=1).
 */
GLAPI int GLAPIENTRY
OSMesaSweetAttachDirect(GLuint name, uint32_t surface_id)
{
   OSMesaContext osmesa = OSMesaGetCurrentContext();
   unsigned dw = 0, dh = 0;

   if (!osmesa || !OSMesaSweetActive())
      return 0;
   struct st_context *st = osmesa->st;
   struct gl_context *ctx = st->ctx;
   struct gl_texture_object *t = _mesa_lookup_texture(ctx, name);
   if (!t || t->Target != GL_TEXTURE_2D)
      return 0;
   struct pipe_resource *res = hero_hw_surface_resource(surface_id, 0, &dw, &dh);
   if (!res)
      return 0;
   struct gl_texture_image *img = _mesa_get_tex_image(ctx, t, GL_TEXTURE_2D, 0);
   if (!img)
      return 0;
   struct st_egl_image stimg;
   memset(&stimg, 0, sizeof(stimg));
   stimg.texture = res;
   stimg.format = res->format;
   stimg.internalformat = GL_RGBA;
   st_bind_egl_image(ctx, t, img, &stimg, false, true);
   return t->surface_based && t->pt == res;
}

GLAPI void GLAPIENTRY
OSMesaSweetDirectSync(uint32_t surface_id)
{
   OSMesaContext osmesa = OSMesaGetCurrentContext();

   if (!osmesa || !OSMesaSweetActive())
      return;
   FLUSH_VERTICES(osmesa->st->ctx, 0, 0);
   st_finish(osmesa->st);
   hero_hw_surface_sync(surface_id);
}

/*
 * glTexImage2D(NULL) leaves a texture undefined; on iOS its memory is
 * cleared, here a recycled BO still holds old pixels. Zero level 0 of the
 * texture bound to the current unit's GL_TEXTURE_2D.
 */
GLAPI void GLAPIENTRY
OSMesaSweetZeroTexture(void)
{
   OSMesaContext osmesa = OSMesaGetCurrentContext();

   if (!osmesa || !OSMesaSweetActive())
      return;
   struct st_context *st = osmesa->st;
   struct gl_context *ctx = st->ctx;
   struct gl_texture_object *t = ctx->Texture.Unit[ctx->Texture.CurrentUnit].CurrentTex[TEXTURE_2D_INDEX];
   if (!t || t->Target != GL_TEXTURE_2D || t->surface_based)
      return;
   if (!st_finalize_texture(ctx, st->pipe, t, 0) || !t->pt)
      return;
   struct pipe_box box;
   u_box_2d(0, 0, t->pt->width0, t->pt->height0, &box);
   if (st->pipe->clear_texture)
      st->pipe->clear_texture(st->pipe, t->pt, 0, &box, NULL);
}

/*
 * Sample an IOSurface in place: level 0 of texture `name` becomes the
 * surface's memory, as AttachDirect does for render targets. The shim
 * (texImageIOSurface with BGL_WRAPSAMPLE=1) asks for it instead of copying
 * the pixels: the copies of SpringBoard's icons were taken while still
 * empty and never refreshed (the CPU renderer reads the memory each frame
 * and drew them). kind (eagl.m): 4 RGBA8, 5 BGRA8; the others are copied.
 */
GLAPI int GLAPIENTRY
OSMesaSweetWrapTexture(GLuint name, uint32_t surface_id, int kind, unsigned w, unsigned h)
{
   OSMesaContext osmesa = OSMesaGetCurrentContext();
   unsigned dw = 0, dh = 0;

   if (!osmesa || !OSMesaSweetActive() || (kind != 4 && kind != 5))
      return 0;
   struct st_context *st = osmesa->st;
   struct gl_context *ctx = st->ctx;
   struct gl_texture_object *t = _mesa_lookup_texture(ctx, name);
   if (!t || t->Target != GL_TEXTURE_2D)
      return 0;
   struct pipe_resource *res = hero_hw_surface_resource(surface_id, kind == 4 ? 2 : 0, &dw, &dh);
   if (!res || dw != w || dh != h)
      return 0;
   struct gl_texture_image *img = _mesa_get_tex_image(ctx, t, GL_TEXTURE_2D, 0);
   if (!img)
      return 0;
   hero_hw_surface_sync(surface_id);    /* the producer's CPU cache lines reach memory first */
   struct st_egl_image stimg;
   memset(&stimg, 0, sizeof(stimg));
   stimg.texture = res;
   stimg.format = res->format;
   stimg.internalformat = GL_RGBA;
   st_bind_egl_image(ctx, t, img, &stimg, false, true);
   return t->surface_based && t->pt == res;
}

/* The producer wrote the surface again: clean its CPU cache lines to memory before the GPU samples it. */
GLAPI void GLAPIENTRY
OSMesaSweetWrapSync(uint32_t surface_id)
{
   if (OSMesaSweetActive())
      hero_hw_surface_sync(surface_id);
}

GLAPI int GLAPIENTRY
OSMesaSweetSurfaceAlias(uint32_t surface_id, void **base, unsigned *bpr, unsigned *w, unsigned *h)
{
   (void)surface_id; (void)base; (void)bpr; (void)w; (void)h;
   return 0;
}

GLAPI void GLAPIENTRY
OSMesaSweetAliasSync(uint32_t surface_id)
{
   (void)surface_id;
}

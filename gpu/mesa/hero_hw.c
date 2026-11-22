/*
 * OSMesa on the Galaxy S7's Mali-T880: osmesa_create_screen() (patched to
 * try this first) gets a Panfrost screen over the HeroGPU libdrm stand-in
 * (gpu/mesa/herodrm.c) instead of softpipe. HERO_GPU=0 keeps softpipe;
 * so does a kernel without HeroGPU.
 */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include <pthread.h>
#include <string.h>

#include "pipe/p_screen.h"
#include "pipe/p_state.h"
#include "frontend/winsys_handle.h"
#include "util/driconf.h"
#include "util/macros.h"
#include "util/u_inlines.h"
#include "util/xmlconfig.h"
#include "panfrost/drm/panfrost_drm_public.h"
#include "xf86drm.h"

struct pipe_screen *hero_hw_create_screen(void);
int hero_hw_active(void);
struct pipe_resource *hero_hw_surface_resource(uint32_t surface_id, int opaque, unsigned *w, unsigned *h);
void hero_hw_surface_sync(uint32_t surface_id);
void hero_hw_surface_forget(uint32_t surface_id);

/* gpu/mesa/herodrm.c */
struct herodrm_surface {
   uint32_t handle, bytes_per_row, width, height, pixel_format, offset, planes;
   uint64_t size;
};
int herodrm_surface_import(uint32_t surface_id, struct herodrm_surface *info);
int herodrm_bo_sync(uint32_t handle);

static struct pipe_screen *hero_screen;

static const driOptionDescription hero_driconf[] = {
#include "panfrost/driinfo_panfrost.h"
};

/* Panfrost reads its options from these for the screen's lifetime. */
static driOptionCache options, options_info;

struct pipe_screen *
hero_hw_create_screen(void)
{
   const char *env = getenv("HERO_GPU");
   if (env && env[0] == '0')
      return NULL;

   int fd = drmOpenWithType("panfrost", NULL, 0);
   if (fd < 0) {
      fprintf(stderr, "hero_hw: no HeroGPU, using softpipe\n");
      return NULL;
   }

   driParseOptionInfo(&options_info, hero_driconf, ARRAY_SIZE(hero_driconf));
   driParseConfigFiles(&options, &options_info, 0, "panfrost", NULL, NULL, NULL, 0,
                       NULL, 0);
   struct pipe_screen_config config = {
      .options = &options,
      .options_info = &options_info,
   };
   struct pipe_screen *screen = panfrost_drm_screen_create(fd, &config);
   /* The screen holds its own dup of the descriptor. */
   close(fd);
   if (!screen)
      fprintf(stderr, "hero_hw: Panfrost screen creation failed, using softpipe\n");
   hero_screen = screen;
   return screen;
}

int
hero_hw_active(void)
{
   return hero_screen != NULL;
}

/*
 * IOSurfaces as render targets (the EAGL shim's GPU blit into CoreAnimation's
 * display surfaces), after Bergamota's sweet_hw.c (ry-diffusion/Bergamota,
 * gpu-eagl, MIT): the kernel maps the surface's pixels into the GPU (HeroGPU
 * SurfaceBO), Panfrost imports them as a linear BGRA resource, and the CPU
 * caches are cleaned after each blit. Surfaces the path cannot use (other
 * formats, several planes) are remembered and left to the CPU copy.
 */
#define MAX_SURF 512            /* display targets plus the sampled icons and layer images (OSMesaSweetWrapTexture) */
static struct {
   uint32_t id, handle;
   int opaque;
   unsigned w, h;
   struct pipe_resource *res;
} surfs[MAX_SURF];
#define MAX_REFUSED 256
static uint32_t refused[MAX_REFUSED];
static int nrefused;
static pthread_mutex_t surf_lock = PTHREAD_MUTEX_INITIALIZER;

static int
refused_has(uint32_t id)
{
   for (int i = 0; i < nrefused; i++)
      if (refused[i] == id)
         return 1;
   return 0;
}

struct pipe_resource *
hero_hw_surface_resource(uint32_t surface_id, int opaque, unsigned *w, unsigned *h)
{
   struct pipe_resource *res = NULL;
   int free_slot = -1;
   const int dbg = getenv("EAGL_SHIM_DEBUG") != NULL;

   if (!hero_screen)
      return NULL;
   pthread_mutex_lock(&surf_lock);
   for (int i = 0; i < MAX_SURF; i++) {
      if (surfs[i].res && surfs[i].id == surface_id && surfs[i].opaque == opaque) {
         res = surfs[i].res;
         *w = surfs[i].w;
         *h = surfs[i].h;
         goto out;
      }
      if (!surfs[i].res && free_slot < 0)
         free_slot = i;
   }
   if (free_slot < 0 || refused_has(surface_id))
      goto out;

   struct herodrm_surface sb;
   memset(&sb, 0, sizeof(sb));
   int fd = herodrm_surface_import(surface_id, &sb);
   if (fd < 0 || sb.planes > 1 || (sb.bytes_per_row & 63) ||
       !(sb.pixel_format == 0x42475241 /* BGRA */ ||
         (sb.pixel_format == 0 && sb.bytes_per_row >= sb.width * 4 && sb.bytes_per_row < sb.width * 8))) {
      if (dbg)
         fprintf(stderr, "hero_hw: surface %u not usable by the GPU (import %d, planes %u fmt %08x, %ux%u bpr %u)\n",
                 surface_id, fd, sb.planes, sb.pixel_format, sb.width, sb.height, sb.bytes_per_row);
      if (fd >= 0)
         drmCloseBufferHandle(-1, sb.handle);
      if (nrefused < MAX_REFUSED)
         refused[nrefused++] = surface_id;
      goto out;
   }
   struct pipe_resource templ;
   memset(&templ, 0, sizeof(templ));
   templ.target = PIPE_TEXTURE_2D;
   /* opaque: 0 BGRA, 1 BGRX (alpha written as 1), 2 RGBA (images CoreAnimation uploads as GL_RGBA) */
   templ.format = opaque == 2 ? PIPE_FORMAT_R8G8B8A8_UNORM :
                  opaque ? PIPE_FORMAT_B8G8R8X8_UNORM : PIPE_FORMAT_B8G8R8A8_UNORM;
   templ.width0 = sb.width;
   templ.height0 = sb.height;
   templ.depth0 = 1;
   templ.array_size = 1;
   templ.usage = PIPE_USAGE_DEFAULT;
   templ.bind = PIPE_BIND_RENDER_TARGET | PIPE_BIND_SAMPLER_VIEW;
   struct winsys_handle wh;
   memset(&wh, 0, sizeof(wh));
   wh.type = WINSYS_HANDLE_TYPE_FD;      /* Panfrost imports dma-bufs only: the stand-in's descriptor */
   wh.handle = fd;
   wh.stride = sb.bytes_per_row;
   wh.offset = sb.offset;
   wh.size = sb.size;
   wh.modifier = 0;                      /* DRM_FORMAT_MOD_LINEAR */
   res = hero_screen->resource_from_handle(hero_screen, &templ, &wh, PIPE_HANDLE_USAGE_FRAMEBUFFER_WRITE);
   if (!res) {
      if (dbg)
         fprintf(stderr, "hero_hw: resource_from_handle failed for surface %u (%ux%u bpr %u)\n", surface_id, sb.width,
                 sb.height, sb.bytes_per_row);
      drmCloseBufferHandle(-1, sb.handle);
      if (nrefused < MAX_REFUSED)
         refused[nrefused++] = surface_id;
      goto out;
   }
   surfs[free_slot].id = surface_id;
   surfs[free_slot].handle = sb.handle;
   surfs[free_slot].opaque = opaque;
   surfs[free_slot].w = sb.width;
   surfs[free_slot].h = sb.height;
   surfs[free_slot].res = res;
   *w = sb.width;
   *h = sb.height;
   if (dbg)
      fprintf(stderr, "hero_hw: surface %u (%ux%u bpr %u) is a GPU render target\n", surface_id, sb.width, sb.height,
              sb.bytes_per_row);
out:
   pthread_mutex_unlock(&surf_lock);
   return res;
}

void
hero_hw_surface_sync(uint32_t surface_id)
{
   pthread_mutex_lock(&surf_lock);
   for (int i = 0; i < MAX_SURF; i++)
      if (surfs[i].res && surfs[i].id == surface_id) {
         herodrm_bo_sync(surfs[i].handle);
         break;
      }
   pthread_mutex_unlock(&surf_lock);
}

void
hero_hw_surface_forget(uint32_t surface_id)
{
   pthread_mutex_lock(&surf_lock);
   for (int i = 0; i < nrefused; i++)
      if (refused[i] == surface_id) {
         refused[i] = refused[--nrefused];
         i--;
      }
   for (int i = 0; i < MAX_SURF; i++)
      if (surfs[i].res && surfs[i].id == surface_id) {
         pipe_resource_reference(&surfs[i].res, NULL);   /* the BO goes when Mesa drops its last reference */
         memset(&surfs[i], 0, sizeof(surfs[i]));
      }
   pthread_mutex_unlock(&surf_lock);
}

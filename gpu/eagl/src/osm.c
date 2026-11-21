// SPDX-License-Identifier: MIT
// Based on Bergamota's gpu/eagl/src/osm.c (ry-diffusion/Bergamota, MIT).
//
// The Galaxy S7's libOSMesa (gpu/mesa: Panfrost over HeroGPU) provides the OSMesaSweet* entry points
// (gpu/mesa/osmesa_hero.inc): presents are GPU blits into the display IOSurfaces. Sampling client-memory
// surfaces in place and the writable alias still answer 0 there, and eagl.m copies those on the CPU.
// HERO_GPU_BLIT=0 (gl.env) turns the GPU blit off. Mesa's on-disk shader cache is not built (it keys on an
// ELF build-id): shaders compile once per process.
#include <stddef.h>
#include <GL/osmesa.h>
#include "osm.h"

#define OSMESA_ES_PROFILE 0x36      // gpu/mesa/patch-mesa.py

osm_ctx osm_create(int es_api, osm_ctx share) {
    const int attr[] = {
        OSMESA_FORMAT, OSMESA_RGBA, OSMESA_DEPTH_BITS, 0, OSMESA_STENCIL_BITS, 0,
        OSMESA_PROFILE, OSMESA_ES_PROFILE,
        OSMESA_CONTEXT_MAJOR_VERSION, es_api, OSMESA_CONTEXT_MINOR_VERSION, 0, 0 };
    return (osm_ctx)OSMesaCreateContextAttribs(attr, (OSMesaContext)share);
}
void osm_destroy(osm_ctx c) { OSMesaDestroyContext((OSMesaContext)c); }
int osm_make_current(osm_ctx c, void *buf, int w, int h) {
    if (!c) { OSMesaMakeCurrent(NULL, NULL, GL_UNSIGNED_BYTE, 0, 0); return 1; }
    return OSMesaMakeCurrent((OSMesaContext)c, buf, GL_UNSIGNED_BYTE, w, h) ? 1 : 0;
}
void *osm_getproc(const char *name) { return (void *)OSMesaGetProcAddress(name); }

extern int OSMesaSweetActive(void);
extern int OSMesaSweetBlit(unsigned name, int is_texture, unsigned surface_id, int flip, int opaque);
extern void OSMesaSweetForgetSurface(unsigned surface_id);
extern void OSMesaSweetStats(double *out, int n);
extern int OSMesaSweetAttachDirect(unsigned name, unsigned surface_id);
extern void OSMesaSweetDirectSync(unsigned surface_id);
extern int OSMesaSweetSurfaceAlias(unsigned surface_id, void **base, unsigned *bpr, unsigned *w, unsigned *h);
extern void OSMesaSweetAliasSync(unsigned surface_id);
extern void OSMesaSweetZeroTexture(void);
extern int OSMesaSweetWrapTexture(unsigned name, unsigned surface_id, int kind, unsigned w, unsigned h);
extern void OSMesaSweetWrapSync(unsigned surface_id);

int osm_sweet_active(void) { return OSMesaSweetActive(); }
int osm_sweet_blit(unsigned name, int is_texture, unsigned surface_id, int flip, int opaque) {
    return OSMesaSweetBlit(name, is_texture, surface_id, flip, opaque);
}
void osm_sweet_forget(unsigned surface_id) { OSMesaSweetForgetSurface(surface_id); }
void osm_sweet_stats(double *out, int n) { OSMesaSweetStats(out, n); }
int osm_sweet_attach_direct(unsigned name, unsigned surface_id) { return OSMesaSweetAttachDirect(name, surface_id); }
void osm_sweet_direct_sync(unsigned surface_id) { OSMesaSweetDirectSync(surface_id); }
int osm_sweet_surface_alias(unsigned surface_id, void **base, unsigned *bpr, unsigned *w, unsigned *h) {
    return OSMesaSweetSurfaceAlias(surface_id, base, bpr, w, h);
}
void osm_sweet_alias_sync(unsigned surface_id) { OSMesaSweetAliasSync(surface_id); }
void osm_sweet_zero_texture(void) { OSMesaSweetZeroTexture(); }
int osm_sweet_wrap_texture(unsigned name, unsigned surface_id, int kind, unsigned w, unsigned h) {
    return OSMesaSweetWrapTexture(name, surface_id, kind, w, h);
}
void osm_sweet_wrap_sync(unsigned surface_id) { OSMesaSweetWrapSync(surface_id); }

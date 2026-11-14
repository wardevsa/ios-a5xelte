// SPDX-License-Identifier: MIT
// Galaxy S7 port: the OpenGL ES library behind HakiOS's src/eagl.c (hakios.gl.h), in place of its
// gl_osmesa.c: our libOSMesa (gpu/mesa: Panfrost on the Mali-T880 over HeroGPU). The differences from
// HakiOS's file: our OSMesa takes the OpenGL ES profile as 0x36 (gpu/mesa/patch-mesa.py, not their 0x38),
// and an IOSurface becomes a texture's memory through OSMesaSweetAttachDirect (gpu/mesa/osmesa_hero.inc:
// HeroGPU maps the surface into the GPU and Panfrost imports it) instead of their freedreno patch to
// glEGLImageTargetTexture2DOES.
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "hakios.gl.h"

#define OSMESA_RGBA                     0x1908
#define OSMESA_FORMAT                   0x22
#define OSMESA_DEPTH_BITS               0x30
#define OSMESA_STENCIL_BITS             0x31
#define OSMESA_PROFILE                  0x33
#define OSMESA_CONTEXT_MAJOR_VERSION    0x36
#define OSMESA_CONTEXT_MINOR_VERSION    0x37
#define OSMESA_ES_PROFILE_HERO          0x36    /* gpu/mesa/patch-mesa.py */
#define GL_UNSIGNED_BYTE                0x1401
#define GL_TEXTURE_BINDING_2D           0x8069

typedef struct osmesa_context *OSMesaContext;
extern OSMesaContext OSMesaCreateContextAttribs(const int *attributes, OSMesaContext share);
extern unsigned char OSMesaMakeCurrent(OSMesaContext context, void *buffer, unsigned type, int width, int height);
extern void OSMesaDestroyContext(OSMesaContext context);
extern void glGetIntegerv(unsigned name, int *value);
extern int OSMesaSweetActive(void);
extern int OSMesaSweetAttachDirect(unsigned name, uint32_t surface_id);
extern void OSMesaSweetDirectSync(uint32_t surface_id);

#define WINDOW  16

struct hakios_gl {
	OSMesaContext context;
	unsigned char window[WINDOW * WINDOW * 4];
};

struct hakios_gl *
hakios_gl_create(int version)
{
	const int attributes[] = {
		OSMESA_FORMAT, OSMESA_RGBA, OSMESA_DEPTH_BITS, 24, OSMESA_STENCIL_BITS, 8,
		OSMESA_PROFILE, OSMESA_ES_PROFILE_HERO, OSMESA_CONTEXT_MAJOR_VERSION, version, OSMESA_CONTEXT_MINOR_VERSION, 0,
		0
	};
	struct hakios_gl *gl = calloc(1, sizeof(*gl));

	if (gl != NULL && (gl->context = OSMesaCreateContextAttribs(attributes, NULL)) == NULL) {
		free(gl);
		gl = NULL;
	}
	return gl;
}

int
hakios_gl_make_current(struct hakios_gl *gl)
{
	if (gl == NULL) {
		return OSMesaMakeCurrent(NULL, NULL, 0, 0, 0);
	}
	return OSMesaMakeCurrent(gl->context, gl->window, GL_UNSIGNED_BYTE, WINDOW, WINDOW);
}

void
hakios_gl_destroy(struct hakios_gl *gl)
{
	OSMesaDestroyContext(gl->context);
	free(gl);
}

const char *
hakios_gl_library(void)
{
	return "Mesa Panfrost on the Mali-T880 (OSMesa, HeroGPU)";
}

/* The texture bound to GL_TEXTURE_2D gets the IOSurface's memory (BGRA surfaces: eagl.c's surface_shared() asks only for those). */
int
hakios_gl_surface_texture(struct hakios_gl *gl, uint32_t surface)
{
	int bound = 0;

	(void)gl;
	if (!OSMesaSweetActive()) {
		return 0;
	}
	glGetIntegerv(GL_TEXTURE_BINDING_2D, &bound);
	return bound != 0 && OSMesaSweetAttachDirect((unsigned)bound, surface);
}

/*
 * The GPU has written the surface (eagl.c, frame_end()): wait for it and make what it wrote visible to the
 * CPU and the display. The surfaces' memory is cached by the CPU here (unlike HakiOS's Adreno phones), and
 * the display driver copies it with the CPU: without this it read lines left from earlier frames, which
 * showed as blocks of old pictures wherever something moved.
 */
void
hakios_gl_surface_written(struct hakios_gl *gl, uint32_t surface)
{
	(void)gl;
	if (OSMesaSweetActive()) {
		OSMesaSweetDirectSync(surface);
	}
}

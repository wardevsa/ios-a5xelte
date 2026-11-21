#!/usr/bin/env python3
"""The S7's changes to Scion's Metal device (ios-b1lte's userspace/metal/scion at B2L_REF), on the copy build-metal.sh
compiles.

  metal-herolte.py DIR

Drawables (docs/herolte-metal.md, M4): CoreAnimation hands the device an IOSurface through
-newTextureWithDescriptor:iosurface:plane:, and Scion's hakiosdrawable.m asks HakiOS's own kernel service
(HakiosGPU/HakiosMali, request 0x7e) to describe it, then has the compiler library import it by ID. This port's kernel
imports a surface through HeroGPU's SurfaceBO instead, which gpu/mesa/herodrm.c wraps as herodrm_surface_import(): one
call, the surface's geometry and a stand-in descriptor for its GPU buffer -- exactly what hero_hw.c (the OpenGL side)
hands Panfrost. So the description comes from there, and the descriptor goes where Scion's code puts the surface ID
(rwa_texture_from_surface makes it the dma-buf descriptor of a winsys_handle). And the GPU's writes into imported
surfaces are made visible to the display (herodrm_bo_sync) when a command buffer completes, as hero_hw.c does after a
frame. Each change checks the exact text it replaces.
"""
import sys

D = sys.argv[1]
done = []


def change(name, path, old, new, count=1):
    p = f'{D}/{path}'
    s = open(p).read()
    if s.count(old) != count:
        sys.exit(f'metal-herolte: {name}: {path} is not as expected ({s.count(old)} matches, want {count})')
    open(p, 'w').write(s.replace(old, new))
    done.append(name)


change('drawable: HeroGPU import', 'hakiosdrawable.m',
       '#include "hakios.drawable.h"\n',
       '''#include "hakios.drawable.h"
#include <pthread.h>

static void rwd_say(char *why, size_t why_size, const char *format, ...);

/* HEROLTE: gpu/mesa/herodrm.c's surface import and sync, looked up in the libdrm stand-in this process already has */
struct herolte_surface {
	uint32_t handle, bytes_per_row, width, height, pixel_format, offset, planes;
	uint64_t size;
};
static int (*herolte_import_fn)(uint32_t, struct herolte_surface *);
static int (*herolte_sync_fn)(uint32_t);
static pthread_mutex_t herolte_lock = PTHREAD_MUTEX_INITIALIZER;
static uint32_t herolte_bos[64];
static unsigned herolte_nbos;

static void
herolte_look(void)
{
	static int looked;
	if (looked)
		return;
	looked = 1;
	void *drm = dlopen("/private/var/herolte/lib/libdrm.2.dylib", RTLD_NOW);
	if (drm != NULL) {
		*(void **)&herolte_import_fn = dlsym(drm, "herodrm_surface_import");
		*(void **)&herolte_sync_fn = dlsym(drm, "herodrm_bo_sync");
	}
	printf("hakiosdrawable: HeroGPU surface import %s, sync %s\\n", herolte_import_fn ? "found" : "MISSING",
	       herolte_sync_fn ? "found" : "MISSING");
}

/* The surface as a GPU buffer: its geometry into *surface, the stand-in descriptor returned (or -1 and a sentence). */
static int
herolte_surface_import(uint32_t id, struct rwd_surface *surface, char *why, size_t why_size)
{
	struct herolte_surface s = { 0 };
	herolte_look();
	if (herolte_import_fn == NULL) {
		rwd_say(why, why_size, "libdrm.2 has no herodrm_surface_import: no surface can reach the GPU");
		return -1;
	}
	int fd = herolte_import_fn(id, &s);
	if (fd < 0) {
		rwd_say(why, why_size, "HeroGPU would not take surface %u as a GPU buffer", id);
		return -1;
	}
	memset(surface, 0, sizeof(*surface));
	surface->surface = id;
	surface->handle = s.handle;
	surface->size = s.size;
	surface->offset = s.offset;
	surface->rowBytes = s.bytes_per_row;
	surface->width = s.width;
	surface->height = s.height;
	surface->pixelFormat = s.pixel_format;
	surface->planes = s.planes;
	return fd;
}

static void
herolte_track(uint32_t handle)
{
	pthread_mutex_lock(&herolte_lock);
	unsigned i;
	for (i = 0; i < herolte_nbos && herolte_bos[i] != handle; i++)
		;
	if (i == herolte_nbos) {
		if (herolte_nbos == 64)
			memmove(herolte_bos, herolte_bos + 1, sizeof(herolte_bos) - sizeof(herolte_bos[0]));
		else
			herolte_nbos++;
		herolte_bos[herolte_nbos - 1] = handle;
	}
	pthread_mutex_unlock(&herolte_lock);
}

/* Called when a command buffer completes (hakiosmetal_air.m): what the GPU wrote into surfaces, to the display. */
void
hero_sync_surfaces(void)
{
	if (herolte_sync_fn == NULL)
		return;
	pthread_mutex_lock(&herolte_lock);
	for (unsigned i = 0; i < herolte_nbos; i++)
		herolte_sync_fn(herolte_bos[i]);
	pthread_mutex_unlock(&herolte_lock);
}
''')

change('drawable: no HakiOS connection', 'hakiosdrawable.m',
       '''	connection = rwd_shared_connection();
	if (connection == 0) {
		rwd_say(why, why_size, "no connection to HakiosGPU: this kernel was booted "
		    "without gpu=1, so a surface's memory cannot be given to the GPU");
		return NULL;
	}
''',
       '''	(void)connection;
	/* HEROLTE: HeroGPU's own import, which describes and takes in one call */
	int prime = herolte_surface_import(id, &surface, why, why_size);
	if (prime < 0) {
		return NULL;
	}
''')

change('drawable: no describe call', 'hakiosdrawable.m',
       '''	if (rwd_surface_describe(connection, id, &surface, why, why_size) != 0) {
		return NULL;
	}
''',
       '')

change('drawable: Panfrost decides the pitch', 'hakiosdrawable.m',
       '''	if (rwd_surface_fits_adreno(&surface, bytes_per_pixel, why, why_size) != 0) {
		return NULL;
	}
''',
       '''	if (surface.planes > 1) {   /* HEROLTE: the Adreno's 64-byte rows are not the Mali's rule; Panfrost checks */
		rwd_say(why, why_size, "surface %u has %u planes; a drawable's texture is one", id, surface.planes);
		return NULL;
	}
''')

change('drawable: the descriptor imported', 'hakiosdrawable.m',
       '''	texture = import(mesa_device, want, (int)id, surface.offset, surface.rowBytes, why,
	    why_size);
	if (texture == NULL) {
		return NULL;    /* the library wrote the sentence; it names the GPU's own reason */
	}
''',
       '''	texture = import(mesa_device, want, prime, surface.offset, surface.rowBytes, why,
	    why_size);
	if (texture == NULL) {
		return NULL;    /* the library wrote the sentence; it names the GPU's own reason */
	}
	herolte_track(surface.handle);
''')

change('command buffer: surfaces synced when complete', 'hakiosmetal_air.m',
       '\t\t\t_status = RW_CB_COMPLETED;\n\t\t\treturn;\n',
       '\t\t\thero_sync_surfaces();   /* HEROLTE */\n\t\t\t_status = RW_CB_COMPLETED;\n\t\t\treturn;\n')
change('command buffer: surfaces synced when finished', 'hakiosmetal_air.m',
       '\t_status = RW_CB_COMPLETED;   /* the fence has been paid, and only now */\n',
       '\thero_sync_surfaces();   /* HEROLTE */\n\t_status = RW_CB_COMPLETED;   /* the fence has been paid, and only now */\n')

# Small buffers, reused (boot-18k50/51). -setVertexBytes: and -setFragmentBytes: made a whole Mesa buffer -- a 4 KB
# kernel BO, ~4 ms each -- per call and autoreleased it; MercuryPoster's render thread drains no pool, so ~430 BOs every
# 5 s were made and none given back, until HeroGPU refused the drawables' surfaces (no picture, white widgets, stutters).
# Now: (1) the encoder keeps those buffers until -endEncoding (the recorded work retains its own, B1L-0112), with no
# autorelease; (2) a buffer of 64 KB or less goes back to a pool when it dies -- its command buffer has run by then:
# submits are synchronous on this port -- and the next buffer of that size class takes it, zeroed, with no kernel call.
change('small buffers: the pool', 'hakiosmetal_air.m',
       '@implementation HakiosMetalBuffer\n',
       '''/* HEROLTE: Mesa buffers of the size classes 256 B .. 64 KB, kept when their HakiosMetalBuffer dies */
#define HEROLTE_CLASSES 9
static struct {
	pthread_mutex_t lock;
	struct rwa_device *device;
	struct rwa_buffer *free[HEROLTE_CLASSES][64];
	unsigned count[HEROLTE_CLASSES];
	unsigned long made, reused;
} herolte_pool = { .lock = PTHREAD_MUTEX_INITIALIZER };

/* 1 + the class of a length (256 << class bytes), or 0 for a length that is not pooled */
static unsigned
herolte_class_of(NSUInteger length)
{
	for (unsigned c = 0; c < HEROLTE_CLASSES; c++)
		if (length <= (256u << c))
			return c + 1;
	return 0;
}

static struct rwa_buffer *
herolte_pool_take(struct rwa_device *device, unsigned cls)
{
	struct rwa_buffer *b = NULL;
	pthread_mutex_lock(&herolte_pool.lock);
	if (cls && herolte_pool.device == device && herolte_pool.count[cls - 1] > 0)
		b = herolte_pool.free[cls - 1][--herolte_pool.count[cls - 1]];
	if (b != NULL)
		herolte_pool.reused++;
	else if (cls)
		herolte_pool.made++;
	unsigned long made = herolte_pool.made, reused = herolte_pool.reused;
	pthread_mutex_unlock(&herolte_pool.lock);
	if (cls && ((made + reused) & (made + reused - 1)) == 0)
		rw_print("HEROLTE POOL: %lu small buffers made, %lu reused\\n", made, reused);
	return b;
}

/* true when the pool took the buffer (it is then not to be destroyed) */
static BOOL
herolte_pool_give(struct rwa_device *device, struct rwa_buffer *b, unsigned cls)
{
	BOOL kept = NO;
	if (!cls || device == NULL)
		return NO;
	pthread_mutex_lock(&herolte_pool.lock);
	if (herolte_pool.device == NULL)
		herolte_pool.device = device;
	if (herolte_pool.device == device && herolte_pool.count[cls - 1] < 64) {
		herolte_pool.free[cls - 1][herolte_pool.count[cls - 1]++] = b;
		kept = YES;
	}
	pthread_mutex_unlock(&herolte_pool.lock);
	return kept;
}

/* the encoders' -setBytes: buffers, kept until -endEncoding (HEROLTE) */
static char herolte_bytes_key;
static void
herolte_keep(id encoder, id buffer)
{
	NSMutableArray *kept = objc_getAssociatedObject(encoder, &herolte_bytes_key);
	if (kept == nil) {
		kept = [[NSMutableArray alloc] init];
		objc_setAssociatedObject(encoder, &herolte_bytes_key, kept, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
		[kept release];
	}
	[kept addObject:buffer];
	[buffer release];
}

@implementation HakiosMetalBuffer
''')
change('small buffers: a class per buffer', 'hakiosmetal_air.m',
       '''	struct rwa_buffer *_mesa; /* set instead when the memory came from Mesa */
	int _responsibleProcess;  /* what <MTLResourceSPI> calls the owner, for accounting */
}''',
       '''	struct rwa_buffer *_mesa; /* set instead when the memory came from Mesa */
	int _responsibleProcess;  /* what <MTLResourceSPI> calls the owner, for accounting */
	unsigned _herolteClass;   /* HEROLTE: 1 + its pool size class, 0 when not pooled */
	struct rwa_device *_herolteDevice;
}''')
change('small buffers: taken from the pool', 'hakiosmetal_air.m',
       '''		char why[256] = { 0 };

		_mesa = mesa.buffer_create([device mesaDevice], length, why, sizeof(why));
		if (_mesa == NULL) {''',
       '''		char why[256] = { 0 };

		_herolteClass = herolte_class_of(length);
		_herolteDevice = [device mesaDevice];
		_mesa = herolte_pool_take(_herolteDevice, _herolteClass);
		if (_mesa != NULL) {
			_owner = device;
			_length = length;
			_contents = mesa.buffer_map(_mesa);
			if (_contents != NULL)
				memset(_contents, 0, 256u << (_herolteClass - 1));   /* new memory reads zero */
			return self;
		}
		_mesa = mesa.buffer_create(_herolteDevice,
		    _herolteClass ? (NSUInteger)(256u << (_herolteClass - 1)) : length, why, sizeof(why));
		if (_mesa == NULL) {''')
change('small buffers: given back', 'hakiosmetal_air.m',
       '''	if (_mesa != NULL) {
		mesa.buffer_destroy(_mesa);
		[super dealloc];
		return;
	}''',
       '''	if (_mesa != NULL) {
		if (!herolte_pool_give(_herolteDevice, _mesa, _herolteClass))   /* HEROLTE */
			mesa.buffer_destroy(_mesa);
		[super dealloc];
		return;
	}''')
change('setBytes: kept by the encoder (render)', 'hakiosmetal_air.m',
       '''	if (buffer != nil) {
		[self setVertexBuffer:[buffer autorelease] offset:0 atIndex:index];
	}''',
       '''	if (buffer != nil) {
		[self setVertexBuffer:buffer offset:0 atIndex:index];
		herolte_keep(self, buffer);   /* HEROLTE: no autorelease */
	}''')
change('setBytes: kept by the encoder (fragment)', 'hakiosmetal_air.m',
       '''	if (buffer != nil) {
		[self setFragmentBuffer:[buffer autorelease] offset:0 atIndex:index];
	}''',
       '''	if (buffer != nil) {
		[self setFragmentBuffer:buffer offset:0 atIndex:index];
		herolte_keep(self, buffer);   /* HEROLTE: no autorelease */
	}''')
change('setBytes: kept by the encoder (compute)', 'hakiosmetal_air.m',
       '''	if (buffer != nil) {
		[self setBuffer:[buffer autorelease] offset:0 atIndex:index];
	}''',
       '''	if (buffer != nil) {
		[self setBuffer:buffer offset:0 atIndex:index];
		herolte_keep(self, buffer);   /* HEROLTE: no autorelease */
	}''')
change('setBytes: released at the end of a render pass', 'hakiosmetal_air.m',
       '''- (void)endEncoding
{
	/* B2L (B1L-0070): a pass that clears and draws nothing still clears (Metal's load action is the pass's) */''',
       '''- (void)endEncoding
{
	objc_setAssociatedObject(self, &herolte_bytes_key, nil, OBJC_ASSOCIATION_RETAIN_NONATOMIC);   /* HEROLTE */
	/* B2L (B1L-0070): a pass that clears and draws nothing still clears (Metal's load action is the pass's) */''')
change('setBytes: released at the end of a compute pass', 'hakiosmetal_air.m',
       '''- (void)endEncoding
{
	[super endEncoding];
}

@end''',
       '''- (void)endEncoding
{
	objc_setAssociatedObject(self, &herolte_bytes_key, nil, OBJC_ASSOCIATION_RETAIN_NONATOMIC);   /* HEROLTE */
	[super endEncoding];
}

@end''')

print('metal-herolte: ' + ', '.join(done))

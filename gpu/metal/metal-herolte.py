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

# Lifetimes that do not hang on an autorelease pool (boot-18k52: with the pool, 242 small buffers made and 14 reused --
# the buffers were still not dying, because the command buffers that held them were not). (1) The objects a caller gets
# from -commandBuffer and the encoder factories go back through objc_autoreleaseReturnValue, as ARC-compiled code returns
# them: a Swift or ARC caller (MercuryPoster) then takes its reference without the object ever entering a pool its
# render thread does not drain. (2) Submits are synchronous on this port unless HERO_ASYNC=1 (gpu/mesa/herodrm.c), so
# when -commit has flushed, the GPU has finished the work: the command buffer lets go of what it recorded there and then
# (Metal needs it no longer), not when the command buffer itself is freed.
change('returns: the declaration', 'hakiosmetal_air.m',
       '#include <pthread.h>   /* B2L (B1L-0109) */\n',
       '#include <pthread.h>   /* B2L (B1L-0109) */\nextern id objc_autoreleaseReturnValue(id);   /* HEROLTE: libobjc, as ARC returns */\n')
change('returns: commandBuffer', 'hakiosmetal_air.m',
       '\treturn [[[HakiosMetalCommandBuffer alloc] initWithHakiosQueue:self] autorelease];\n',
       '\treturn objc_autoreleaseReturnValue([[HakiosMetalCommandBuffer alloc] initWithHakiosQueue:self]);\n')
change('returns: computeCommandEncoder', 'hakiosmetal_air.m',
       '''	return [[[HakiosMetalComputeEncoder alloc] initWithHakiosCommandBuffer:self]
		   autorelease];''',
       '''	return objc_autoreleaseReturnValue([[HakiosMetalComputeEncoder alloc] initWithHakiosCommandBuffer:self]);''')
change('returns: renderCommandEncoder', 'hakiosmetal_air.m',
       '''	return [[[HakiosMetalRenderEncoder alloc] initWithHakiosCommandBuffer:self
								    descriptor:descriptor]
		   autorelease];''',
       '''	return objc_autoreleaseReturnValue([[HakiosMetalRenderEncoder alloc] initWithHakiosCommandBuffer:self
								    descriptor:descriptor]);''')
change('returns: blitCommandEncoder', 'hakiosmetal_air.m',
       '\treturn [[[HakiosMetalBlitEncoder alloc] initWithCommandBuffer:self] autorelease];\n',
       '\treturn objc_autoreleaseReturnValue([[HakiosMetalBlitEncoder alloc] initWithCommandBuffer:self]);\n')
change('work: let go when the synchronous submit returns', 'hakiosmetal_air.m',
       '''	_status = RW_CB_SCHEDULED;   /* submitted; the fence below is what makes it completed */
done:''',
       '''	_status = RW_CB_SCHEDULED;   /* submitted; the fence below is what makes it completed */
	{   /* HEROLTE: the GPU has finished (synchronous submits): what the work named is needed no longer */
		static int sync = -1;
		if (sync < 0) {
			const char *a = getenv("HERO_ASYNC");
			sync = !(a && *a == '1');
		}
		if (sync) {
			herolte_look_at_attachments(_work);
			@synchronized (self) {
				[_work removeAllObjects];
			}
		}
	}
done:''')
# Diagnostic (MercuryPoster's missing shape): what the first command buffers with two or more colour attachments left in
# each attachment, read back once the synchronous submit has returned -- pixels with anything in them, and each
# channel's least and greatest value. Says whether fluidity's SDF reaches its RG32Float attachment, and what the second
# pass makes of it.
change('diagnostic: attachments read back', 'hakiosmetal_air.m',
       '@implementation HakiosMetalCommandBuffer {\n',
       '''/* HEROLTE: the first six command buffers drawing into two or more attachments, each attachment summed up */
static void
herolte_look_at_attachments(NSArray *works)
{
	static unsigned looked;
	if (looked >= 6 || mesa.texture_read == NULL)
		return;
	HakiosMetalWork *last = nil;
	for (HakiosMetalWork *w in works)
		if (w->render != nil && w->colorCount >= 2)
			last = w;
	if (last == nil)
		return;
	looked++;
	for (unsigned i = 0; i < last->colorCount; i++) {
		id t = last->color[i];
		if (t == nil)
			continue;
		unsigned width = (unsigned)[t width], height = (unsigned)[t height], format = (unsigned)[t pixelFormat];
		unsigned bpp = format == 80 || format == 70 ? 4 : format == 105 || format == 115 ? 8 : format == 125 ? 16 :
		               format == 55 ? 4 : 0;
		if (bpp == 0 || width == 0 || height == 0)
			continue;
		uint8_t *px = malloc((size_t)width * height * bpp);
		char why[256] = { 0 };
		unsigned origin[3] = { 0, 0, 0 }, size[3] = { width, height, 1 };
		if (px == NULL || mesa.texture_read([t mesaTexture], 0, 0, origin, size, px, 0, why, sizeof(why)) != 0) {
			rw_print("HEROLTE LOOK %u: attachment %u (%ux%u format %u) not read: %s\\n", looked, i, width, height,
			         format, why);
			free(px);
			continue;
		}
		unsigned long nonzero = 0;
		float lo[4] = { 1e30f, 1e30f, 1e30f, 1e30f }, hi[4] = { -1e30f, -1e30f, -1e30f, -1e30f };
		unsigned comps = format == 105 ? 2 : 4;
		for (size_t p = 0; p < (size_t)width * height; p++) {
			const uint8_t *q = px + p * bpp;
			int any = 0;
			for (unsigned b = 0; b < bpp; b++)
				any |= q[b];
			nonzero += any != 0;
			for (unsigned c = 0; c < comps; c++) {
				float v = bpp == 4 ? q[c] / 255.0f : bpp == 8 && format == 105 ? ((const float *)q)[c] :
				          bpp == 16 ? ((const float *)q)[c] : 0;
				if (v < lo[c]) lo[c] = v;
				if (v > hi[c]) hi[c] = v;
			}
		}
		if (looked == 1) {   /* the first frame as it was drawn, every attachment, for the PC to look at */
			char path[160];
			snprintf(path, sizeof(path), "/private/var/herolte/look-%d-a%u-%ux%u-f%u.raw", getpid(), i, width, height,
			         format);
			FILE *out = fopen(path, "wb");
			if (out == NULL) {
				NSString *tmp = [NSTemporaryDirectory() stringByAppendingPathComponent:
				    [NSString stringWithFormat:@"look-a%u.raw", i]];
				snprintf(path, sizeof(path), "%s", [tmp UTF8String]);
				out = fopen(path, "wb");
			}
			size_t wrote = out ? fwrite(px, 1, (size_t)width * height * bpp, out) : 0;
			if (out)
				fclose(out);
			rw_print("HEROLTE LOOK: frame saved to %s (%zu bytes)\\n", path, wrote);
		}
		rw_print("HEROLTE LOOK %u: attachment %u %ux%u format %u: %lu of %lu pixels non-zero; channels "
		         "[%g %g] [%g %g] [%g %g] [%g %g]\\n", looked, i, width, height, format, nonzero,
		         (unsigned long)width * height, lo[0], hi[0], lo[1], hi[1], comps > 2 ? lo[2] : 0, comps > 2 ? hi[2] : 0,
		         comps > 2 ? lo[3] : 0, comps > 2 ? hi[3] : 0);
		free(px);
	}
}

@implementation HakiosMetalCommandBuffer {
''')

# Diagnostic: where Metal keeps a function's constant values (ios-b1lte's B1L-0085 survey, muted since B1L-0110).
# MercuryPoster's fluidity::fragmentShader declares isPhone, isBlending and isSimulator; the pipeline is built from the
# unspecialised module, so all three are 0 here and the poster draws as on an iPad. The survey names the class and
# the instance variables that hold the values, for the first six render pipelines of a process.
change('diagnostic: function constants surveyed', 'hakiosmetal_air.m',
       '''	if (!B2L_QUIET) rw_print("B2L fc: %s function %s, class %s\\n", stage, [[fn name] UTF8String] ?: "?",''',
       '''	rw_print("B2L fc: %s function %s, class %s\\n", stage, [[fn name] UTF8String] ?: "?",''')
change('diagnostic: function constants surveyed (ivars)', 'hakiosmetal_air.m',
       '''			if (!B2L_QUIET) rw_print("B2L fc:   %s.%s %s = %.300s\\n",''',
       '''			rw_print("B2L fc:   %s.%s %s = %.300s\\n",''')

print('metal-herolte: ' + ', '.join(done))

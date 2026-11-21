/*
 * hero_mtl_test: Metal itself on the S7 (docs/herolte-metal.md, M3). MTLCreateSystemDefaultDevice() through the
 * kernel's IOAcceleratorES and the HeroMetal plug-in, then the draw hero_metal_test made through libhakiosair directly
 * (boot-18k45): MercuryPoster's postVertex + postFragment, six vertices, into 32x32 RGBA8Unorm, over the same textures
 * (texel (x,y,z) = ((x+.5)/16, (y+.5)/16, (z+.5)/16, 1)). The same pixels prove the whole device: library, functions,
 * pipeline, textures, command queue, render encoder, commit, wait, getBytes. RGBA8 there: (0,0) ff7f0909,
 * (16,16) ff808778, (8,24) ff80c74a, (31,31) ff80f60a.
 *
 *   hero_mtl_test [METALLIB]
 *
 * The process name must be in /private/var/herolte/metal.allow for the plug-in to give it a device.
 */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <IOKit/IOKitLib.h>
#include <objc/runtime.h>
#include <stdio.h>
#include <time.h>

static double
now(void)
{
	struct timespec t;
	clock_gettime(CLOCK_MONOTONIC, &t);
	return t.tv_sec + t.tv_nsec / 1e9;
}

static id<MTLTexture>
gradient(id<MTLDevice> dev, MTLTextureType type)
{
	MTLTextureDescriptor *d = [MTLTextureDescriptor new];
	d.textureType = type;
	d.pixelFormat = MTLPixelFormatRGBA32Float;
	d.width = 16;
	d.height = 16;
	d.depth = type == MTLTextureType3D ? 16 : 1;
	d.usage = MTLTextureUsageShaderRead;
	id<MTLTexture> t = [dev newTextureWithDescriptor:d];
	if (t == nil)
		return nil;
	unsigned depth = (unsigned)d.depth;
	float *texels = malloc(16 * 16 * depth * 16);
	for (unsigned z = 0; z < depth; z++)
		for (unsigned y = 0; y < 16; y++)
			for (unsigned x = 0; x < 16; x++) {
				float *p = texels + 4 * ((z * 16 + y) * 16 + x);
				p[0] = (x + 0.5f) / 16, p[1] = (y + 0.5f) / 16, p[2] = (z + 0.5f) / depth, p[3] = 1;
			}
	[t replaceRegion:MTLRegionMake3D(0, 0, 0, 16, 16, depth) mipmapLevel:0 slice:0 withBytes:texels
	     bytesPerRow:16 * 16 bytesPerImage:16 * 16 * 16];
	free(texels);
	return t;
}

int
main(int argc, char **argv)
{
	setvbuf(stdout, NULL, _IOLBF, 0);
	@autoreleasepool {
		const char *path = argc > 1 ? argv[1] :
		    "/System/Library/ExtensionKit/Extensions/MercuryPosterExtension.appex/default.metallib";
		double t0 = now();
		id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
		printf("hero_mtl_test: MTLCreateSystemDefaultDevice: %s (%s) in %.2f s\n",
		       dev ? [[dev name] UTF8String] : "nil", dev ? object_getClassName(dev) : "-", now() - t0);
		if (dev == nil) {
			/* how far discovery got: the service, its two properties, the bundle's class, Metal's list */
			io_iterator_t it = IO_OBJECT_NULL;
			unsigned found = 0;
			if (IOServiceGetMatchingServices(kIOMainPortDefault, IOServiceMatching("IOAcceleratorES"), &it) ==
			    KERN_SUCCESS) {
				io_service_t s;
				while ((s = IOIteratorNext(it)) != IO_OBJECT_NULL) {
					found++;
					CFTypeRef n = IORegistryEntryCreateCFProperty(s, CFSTR("MetalPluginName"), NULL, 0);
					CFTypeRef c = IORegistryEntryCreateCFProperty(s, CFSTR("MetalPluginClassName"), NULL, 0);
					printf("hero_mtl_test: IOAcceleratorES %u: MetalPluginName %s, MetalPluginClassName %s\n",
					       found, n ? [[(id)n description] UTF8String] : "(none)",
					       c ? [[(id)c description] UTF8String] : "(none)");
					if (n)
						CFRelease(n);
					if (c)
						CFRelease(c);
					IOObjectRelease(s);
				}
				IOObjectRelease(it);
			}
			printf("hero_mtl_test: %u IOAcceleratorES; class HeroMetalDevice %s\n", found,
			       objc_getClass("HeroMetalDevice") ? "loaded (the bundle is in)" : "not loaded");
			NSBundle *b = [NSBundle bundleWithPath:@"/System/Library/Extensions/HeroMetal.bundle"];
			NSError *le = nil;
			BOOL ok = [b loadAndReturnError:&le];
			printf("hero_mtl_test: loading the bundle by hand: %s%s; class %s\n", ok ? "loaded" : "FAILED ",
			       ok ? "" : [[le description] UTF8String],
			       objc_getClass("HeroMetalDevice") ? "there" : "missing");
			return 1;
		}

		/* a buffer the processor writes and reads back */
		id<MTLBuffer> buf = [dev newBufferWithLength:4096 options:MTLResourceStorageModeShared];
		if (buf != nil) {
			uint32_t *w = buf.contents;
			for (unsigned i = 0; i < 1024; i++)
				w[i] = i * 2654435761u;
			unsigned bad = 0;
			for (unsigned i = 0; i < 1024; i++)
				bad += w[i] != i * 2654435761u;
			printf("hero_mtl_test: buffer of %lu bytes, %u words wrong\n", (unsigned long)buf.length, bad);
		} else {
			printf("hero_mtl_test: newBufferWithLength: nil\n");
		}

		NSError *err = nil;
		t0 = now();
		id<MTLLibrary> lib = [dev newLibraryWithURL:[NSURL fileURLWithPath:@(path)] error:&err];
		printf("hero_mtl_test: library %s: %s in %.2f s\n", path, lib ? "loaded" : [[err description] UTF8String],
		       now() - t0);
		if (lib == nil)
			return 1;
		printf("hero_mtl_test: %lu functions\n", (unsigned long)lib.functionNames.count);
		id<MTLFunction> vf = [lib newFunctionWithName:@"postVertex"];
		id<MTLFunction> ff = [lib newFunctionWithName:@"postFragment"];
		printf("hero_mtl_test: postVertex %s, postFragment %s\n", vf ? "found" : "MISSING", ff ? "found" : "MISSING");
		if (vf == nil || ff == nil)
			return 1;

		MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
		pd.vertexFunction = vf;
		pd.fragmentFunction = ff;
		pd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
		t0 = now();
		id<MTLRenderPipelineState> ps = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
		printf("hero_mtl_test: render pipeline %s in %.2f s\n", ps ? "made" : [[err description] UTF8String],
		       now() - t0);
		if (ps == nil)
			return 1;

		id<MTLTexture> t2d = gradient(dev, MTLTextureType2D), t3d = gradient(dev, MTLTextureType3D);
		MTLTextureDescriptor *cd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm
		                                                                               width:32 height:32 mipmapped:NO];
		cd.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
		id<MTLTexture> target = [dev newTextureWithDescriptor:cd];
		printf("hero_mtl_test: textures %s %s, target %s\n", t2d ? "2d" : "NO-2d", t3d ? "3d" : "NO-3d",
		       target ? "made" : "NOT made");
		if (t2d == nil || t3d == nil || target == nil)
			return 1;

		id<MTLCommandQueue> q = [dev newCommandQueue];
		for (int round = 0; round < 2; round++) {
			MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
			rp.colorAttachments[0].texture = target;
			rp.colorAttachments[0].loadAction = MTLLoadActionClear;
			rp.colorAttachments[0].clearColor = MTLClearColorMake(0.125, 0.25, 0.375, 0.5);
			rp.colorAttachments[0].storeAction = MTLStoreActionStore;
			t0 = now();
			id<MTLCommandBuffer> cb = [q commandBuffer];
			id<MTLRenderCommandEncoder> e = [cb renderCommandEncoderWithDescriptor:rp];
			[e setRenderPipelineState:ps];
			[e setFragmentTexture:t2d atIndex:0];
			[e setFragmentTexture:t3d atIndex:1];
			[e drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:6];
			[e endEncoding];
			[cb commit];
			[cb waitUntilCompleted];
			printf("hero_mtl_test: draw %d: status %ld%s%s in %.3f s\n", round + 1, (long)cb.status,
			       cb.error ? ", error " : "", cb.error ? [[cb.error description] UTF8String] : "", now() - t0);
		}

		uint32_t px[32 * 32];
		[target getBytes:px bytesPerRow:32 * 4 fromRegion:MTLRegionMake2D(0, 0, 32, 32) mipmapLevel:0];
		unsigned clear = 0;
		for (unsigned i = 0; i < 32 * 32; i++)
			clear += px[i] == 0x80604020u;
		printf("hero_mtl_test: %u of 1024 pixels still the clear colour\n", clear);
		static const unsigned at[4][2] = { { 0, 0 }, { 16, 16 }, { 8, 24 }, { 31, 31 } };
		static const uint32_t want[4] = { 0xff7f0909u, 0xff808778u, 0xff80c74au, 0xff80f60au };
		for (int k = 0; k < 4; k++) {
			uint32_t v = px[at[k][1] * 32 + at[k][0]];
			printf("hero_mtl_test:   (%u,%u) = %08x (hero_metal_test drew %08x)%s\n", at[k][0], at[k][1], v, want[k],
			       v == want[k] ? "" : " DIFFERENT");
		}
	}
	printf("hero_mtl_test: done\n");
	return 0;
}

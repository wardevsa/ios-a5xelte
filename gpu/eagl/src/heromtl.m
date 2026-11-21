// SPDX-License-Identifier: MIT
// libheromtl: a Metal provider for the Galaxy S7 port (S7GE, docs/S7GE_METAL_DESIGN.md), milestone M1.
//
// There is no AGX and no Metal driver on this phone, so MTLCreateSystemDefaultDevice() answers nil. libheroapp (inserted into every application) interposes
// MTLCreateSystemDefaultDevice and MTLCopyAllDevices and, for the applications listed in the drop file mtl.on, asks this library for a device.
// M1 implements what a clear-and-present needs, on the CPU, with no shaders: a device, a command queue, command buffers, buffers, textures backed by IOSurfaces,
// a render pass whose load action clears, and CAMetalLayer's nextDrawable/present. Whatever else an application calls is answered with zero and written down in
// /private/var/tmp/heromtl.log (never with an invented value). M2 will replay draw calls through the GLES context of the EAGL bridge.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <QuartzCore/QuartzCore.h>
#import <IOSurface/IOSurfaceRef.h>
#import <objc/runtime.h>
#import <fcntl.h>
#import <stdarg.h>
#import <sys/stat.h>
#import <unistd.h>

static void mtl_note(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
static void mtl_note(const char *fmt, ...) {
    static int count;
    if (count++ > 600) return;
    char line[500];
    va_list ap; va_start(ap, fmt);
    int n = vsnprintf(line, sizeof line - 1, fmt, ap);
    va_end(ap);
    if (n <= 0) return;
    if (n > (int)sizeof line - 2) n = (int)sizeof line - 2;
    line[n++] = '\n';
    int fd = open("/private/var/tmp/heromtl.log", O_WRONLY | O_CREAT | O_APPEND, 0666);
    if (fd >= 0) { (void)!write(fd, line, (size_t)n); fchmod(fd, 0666); close(fd); }
}

// Every object of the provider: a selector of one of the Metal protocols that a class does not implement is answered with zero and noted once.
static uintptr_t unsupported(id self, SEL cmd) {
    static NSMutableSet *seen;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ seen = [NSMutableSet set]; });
    NSString *key = [NSString stringWithFormat:@"%s %s", class_getName(object_getClass(self)), sel_getName(cmd)];
    @synchronized (seen) { if (![seen containsObject:key]) { [seen addObject:key]; mtl_note("heromtl: unsupported %s", key.UTF8String); } }
    return 0;
}

@interface HeroMTLBase : NSObject
@end
@implementation HeroMTLBase
+ (BOOL)resolveInstanceMethod:(SEL)sel {
    unsigned n = 0;
    Protocol *__unsafe_unretained *list = class_copyProtocolList(self, &n);
    BOOL ours = NO;
    for (unsigned i = 0; i < n && !ours; i++)
        for (int required = 0; required < 2 && !ours; required++)
            ours = protocol_getMethodDescription(list[i], sel, required, YES).name != NULL;
    free(list);
    if (!ours) return [super resolveInstanceMethod:sel];
    return class_addMethod(self, sel, (IMP)unsupported, "Q@:");
}
@end

static size_t bytes_per_element(MTLPixelFormat f) {
    switch (f) {
    case MTLPixelFormatA8Unorm: case MTLPixelFormatR8Unorm: case MTLPixelFormatR8Unorm_sRGB: case MTLPixelFormatR8Snorm: case MTLPixelFormatR8Uint: case MTLPixelFormatR8Sint: return 1;
    case MTLPixelFormatRG8Unorm: case MTLPixelFormatR16Float: case MTLPixelFormatR16Unorm: case MTLPixelFormatB5G6R5Unorm: return 2;
    case MTLPixelFormatRGBA16Float: case MTLPixelFormatRG32Float: case MTLPixelFormatRGBA16Unorm: return 8;
    case MTLPixelFormatRGBA32Float: return 16;
    default: return 4;
    }
}
static BOOL is_bgra(MTLPixelFormat f) { return f == MTLPixelFormatBGRA8Unorm || f == MTLPixelFormatBGRA8Unorm_sRGB; }

@class HeroDevice;
static HeroDevice *g_device;

@interface HeroBuffer : HeroMTLBase <MTLBuffer>
@property (nonatomic, assign) void *bytes;
@property (nonatomic, assign) NSUInteger size;
@property (nonatomic, assign) MTLResourceOptions opts;
@property (nonatomic, copy) NSString *label;
@end
@implementation HeroBuffer
- (void)dealloc { free(_bytes); }
- (void *)contents { return _bytes; }
- (NSUInteger)length { return _size; }
- (id<MTLDevice>)device { return (id)g_device; }
- (MTLResourceOptions)resourceOptions { return _opts; }
- (MTLStorageMode)storageMode { return MTLStorageModeShared; }
- (MTLCPUCacheMode)cpuCacheMode { return MTLCPUCacheModeDefaultCache; }
- (MTLHazardTrackingMode)hazardTrackingMode { return MTLHazardTrackingModeTracked; }
- (void)didModifyRange:(NSRange)range {}
- (MTLPurgeableState)setPurgeableState:(MTLPurgeableState)state { return MTLPurgeableStateNonVolatile; }
@end

@interface HeroTexture : HeroMTLBase <MTLTexture>
@property (nonatomic, assign) IOSurfaceRef surface;
@property (nonatomic, assign) NSUInteger w, h;
@property (nonatomic, assign) MTLPixelFormat fmt;
@property (nonatomic, assign) MTLTextureUsage use;
@property (nonatomic, copy) NSString *label;
- (instancetype)initWithWidth:(NSUInteger)w height:(NSUInteger)h format:(MTLPixelFormat)f usage:(MTLTextureUsage)u;
- (void)fillRed:(double)r green:(double)g blue:(double)b alpha:(double)a;
@end
@implementation HeroTexture
- (instancetype)initWithWidth:(NSUInteger)w height:(NSUInteger)h format:(MTLPixelFormat)f usage:(MTLTextureUsage)u {
    if (!(self = [super init])) return nil;
    size_t bpe = bytes_per_element(f);
    uint32_t fourcc = bpe == 1 ? 'L008' : bpe == 2 ? 'L016' : bpe == 8 ? 'RGhA' : 'BGRA';
    NSDictionary *d = @{ (id)kIOSurfaceWidth: @(w ?: 1), (id)kIOSurfaceHeight: @(h ?: 1), (id)kIOSurfaceBytesPerElement: @(bpe), (id)kIOSurfacePixelFormat: @(fourcc) };
    _surface = IOSurfaceCreate((__bridge CFDictionaryRef)d);
    if (!_surface) { mtl_note("heromtl: IOSurfaceCreate failed for %lux%lu format %lu", (unsigned long)w, (unsigned long)h, (unsigned long)f); return nil; }
    _w = w; _h = h; _fmt = f; _use = u;
    return self;
}
- (void)dealloc { if (_surface) CFRelease(_surface); }
- (void)fillRed:(double)r green:(double)g blue:(double)b alpha:(double)a {
    size_t bpe = bytes_per_element(_fmt);
    IOSurfaceLock(_surface, 0, NULL);
    uint8_t *base = IOSurfaceGetBaseAddress(_surface);
    size_t bpr = IOSurfaceGetBytesPerRow(_surface);
    uint8_t px[16] = {0};
    if (bpe == 4) {
        uint8_t R = (uint8_t)(fmin(fmax(r, 0), 1) * 255 + .5), G = (uint8_t)(fmin(fmax(g, 0), 1) * 255 + .5), B = (uint8_t)(fmin(fmax(b, 0), 1) * 255 + .5), A = (uint8_t)(fmin(fmax(a, 0), 1) * 255 + .5);
        if (is_bgra(_fmt)) { px[0] = B; px[1] = G; px[2] = R; px[3] = A; } else { px[0] = R; px[1] = G; px[2] = B; px[3] = A; }
    } else if (bpe == 1) px[0] = (uint8_t)(fmin(fmax(r, 0), 1) * 255 + .5);
    for (size_t y = 0; y < _h; y++)
        for (size_t x = 0; x < _w; x++) memcpy(base + y * bpr + x * bpe, px, bpe);
    IOSurfaceUnlock(_surface, 0, NULL);
}
- (id<MTLDevice>)device { return (id)g_device; }
- (NSUInteger)width { return _w; }
- (NSUInteger)height { return _h; }
- (NSUInteger)depth { return 1; }
- (NSUInteger)mipmapLevelCount { return 1; }
- (NSUInteger)sampleCount { return 1; }
- (NSUInteger)arrayLength { return 1; }
- (MTLTextureType)textureType { return MTLTextureType2D; }
- (MTLPixelFormat)pixelFormat { return _fmt; }
- (MTLTextureUsage)usage { return _use; }
- (BOOL)isFramebufferOnly { return NO; }
- (MTLStorageMode)storageMode { return MTLStorageModeShared; }
- (MTLResourceOptions)resourceOptions { return MTLResourceStorageModeShared; }
- (IOSurfaceRef)iosurface { return _surface; }
- (NSUInteger)iosurfacePlane { return 0; }
- (void)getBytes:(void *)pointer bytesPerRow:(NSUInteger)bpr fromRegion:(MTLRegion)region mipmapLevel:(NSUInteger)level {
    size_t bpe = bytes_per_element(_fmt);
    IOSurfaceLock(_surface, kIOSurfaceLockReadOnly, NULL);
    uint8_t *base = IOSurfaceGetBaseAddress(_surface); size_t sbpr = IOSurfaceGetBytesPerRow(_surface);
    for (NSUInteger y = 0; y < region.size.height; y++)
        memcpy((uint8_t *)pointer + y * bpr, base + (region.origin.y + y) * sbpr + region.origin.x * bpe, region.size.width * bpe);
    IOSurfaceUnlock(_surface, kIOSurfaceLockReadOnly, NULL);
}
- (void)replaceRegion:(MTLRegion)region mipmapLevel:(NSUInteger)level withBytes:(const void *)pointer bytesPerRow:(NSUInteger)bpr {
    size_t bpe = bytes_per_element(_fmt);
    IOSurfaceLock(_surface, 0, NULL);
    uint8_t *base = IOSurfaceGetBaseAddress(_surface); size_t sbpr = IOSurfaceGetBytesPerRow(_surface);
    for (NSUInteger y = 0; y < region.size.height; y++)
        memcpy(base + (region.origin.y + y) * sbpr + region.origin.x * bpe, (const uint8_t *)pointer + y * bpr, region.size.width * bpe);
    IOSurfaceUnlock(_surface, 0, NULL);
}
@end

@interface HeroDrawable : HeroMTLBase <CAMetalDrawable>
@property (nonatomic, strong) HeroTexture *tex;
@property (nonatomic, weak) CAMetalLayer *owner;
@property (nonatomic, assign) NSUInteger ident;
@end
@implementation HeroDrawable
- (id<MTLTexture>)texture { return (id)_tex; }
- (CAMetalLayer *)layer { return _owner; }
- (NSUInteger)drawableID { return _ident; }
- (CFTimeInterval)presentedTime { return 0; }
- (void)present { [self presentAtTime:0]; }
- (void)presentAtTime:(CFTimeInterval)t {
    CAMetalLayer *l = _owner;
    if (l && _tex.surface) { [CATransaction begin]; [CATransaction setDisableActions:YES]; l.contents = (__bridge id)_tex.surface; [CATransaction commit]; }
}
- (void)presentAfterMinimumDuration:(CFTimeInterval)d { [self present]; }
- (void)addPresentedHandler:(MTLDrawablePresentedHandler)h { if (h) dispatch_async(dispatch_get_main_queue(), ^{ h(self); }); }
@end

@interface HeroRenderEncoder : HeroMTLBase <MTLRenderCommandEncoder>
@property (nonatomic, strong) MTLRenderPassDescriptor *pass;
@property (nonatomic, copy) NSString *label;
@end
@implementation HeroRenderEncoder
- (id<MTLDevice>)device { return (id)g_device; }
- (void)endEncoding {
    MTLRenderPassColorAttachmentDescriptor *c = [_pass.colorAttachments objectAtIndexedSubscript:0];
    HeroTexture *t = (HeroTexture *)c.texture;
    if (t && [t isKindOfClass:[HeroTexture class]] && c.loadAction == MTLLoadActionClear) {
        MTLClearColor k = c.clearColor;
        [t fillRed:k.red green:k.green blue:k.blue alpha:k.alpha];
    } else if (t && c.loadAction != MTLLoadActionClear) {
        mtl_note("heromtl: render pass of load action %ld not clearing: nothing drawn (M1)", (long)c.loadAction);
    }
}
@end

@interface HeroCommandBuffer : HeroMTLBase <MTLCommandBuffer>
@property (nonatomic, weak) id<MTLCommandQueue> queue;
@property (nonatomic, strong) NSMutableArray *drawables, *completed, *scheduled;
@property (nonatomic, assign) MTLCommandBufferStatus st;
@property (nonatomic, copy) NSString *label;
@end
@implementation HeroCommandBuffer
- (instancetype)init { if ((self = [super init])) { _drawables = [NSMutableArray array]; _completed = [NSMutableArray array]; _scheduled = [NSMutableArray array]; } return self; }
- (id<MTLDevice>)device { return (id)g_device; }
- (id<MTLCommandQueue>)commandQueue { return _queue; }
- (BOOL)retainedReferences { return YES; }
- (MTLCommandBufferStatus)status { return _st; }
- (NSError *)error { return nil; }
- (id<MTLRenderCommandEncoder>)renderCommandEncoderWithDescriptor:(MTLRenderPassDescriptor *)d {
    HeroRenderEncoder *e = [HeroRenderEncoder new]; e.pass = [d copy]; return e;
}
- (void)presentDrawable:(id<MTLDrawable>)d { [_drawables addObject:d]; }
- (void)presentDrawable:(id<MTLDrawable>)d atTime:(CFTimeInterval)t { [_drawables addObject:d]; }
- (void)presentDrawable:(id<MTLDrawable>)d afterMinimumDuration:(CFTimeInterval)t { [_drawables addObject:d]; }
- (void)addCompletedHandler:(MTLCommandBufferHandler)h { if (h) [_completed addObject:[h copy]]; }
- (void)addScheduledHandler:(MTLCommandBufferHandler)h { if (h) [_scheduled addObject:[h copy]]; }
- (void)enqueue { if (_st < MTLCommandBufferStatusEnqueued) _st = MTLCommandBufferStatusEnqueued; }
- (void)commit {
    _st = MTLCommandBufferStatusScheduled;
    for (MTLCommandBufferHandler h in _scheduled) h(self);
    for (id<MTLDrawable> d in _drawables) [d present];
    _st = MTLCommandBufferStatusCompleted;
    for (MTLCommandBufferHandler h in _completed) h(self);
}
- (void)waitUntilScheduled {}
- (void)waitUntilCompleted {}
@end

@interface HeroQueue : HeroMTLBase <MTLCommandQueue>
@property (nonatomic, copy) NSString *label;
@end
@implementation HeroQueue
- (id<MTLDevice>)device { return (id)g_device; }
- (id<MTLCommandBuffer>)commandBuffer { HeroCommandBuffer *b = [HeroCommandBuffer new]; b.queue = self; return b; }
- (id<MTLCommandBuffer>)commandBufferWithUnretainedReferences { return [self commandBuffer]; }
- (id<MTLCommandBuffer>)commandBufferWithDescriptor:(MTLCommandBufferDescriptor *)d { return [self commandBuffer]; }
- (void)insertDebugCaptureBoundary {}
@end

@interface HeroDevice : HeroMTLBase <MTLDevice>
@end
@implementation HeroDevice
- (NSString *)name { return @"S7GE Mali-T880 (Metal on OpenGL ES)"; }
- (uint64_t)registryID { return 0x5337474500000001ull; }
- (BOOL)hasUnifiedMemory { return YES; }
- (BOOL)isLowPower { return YES; }
- (MTLSize)maxThreadsPerThreadgroup { return MTLSizeMake(256, 256, 64); }
- (NSUInteger)maxBufferLength { return 256u << 20; }
- (uint64_t)recommendedMaxWorkingSetSize { return 1024u << 20; }
- (NSUInteger)currentAllocatedSize { return 0; }
- (BOOL)supportsFamily:(MTLGPUFamily)family { return NO; }
- (BOOL)supportsFeatureSet:(MTLFeatureSet)featureSet { return NO; }
- (BOOL)supportsTextureSampleCount:(NSUInteger)n { return n == 1; }
- (id<MTLCommandQueue>)newCommandQueue { return [HeroQueue new]; }
- (id<MTLCommandQueue>)newCommandQueueWithMaxCommandBufferCount:(NSUInteger)n { return [HeroQueue new]; }
- (id<MTLBuffer>)newBufferWithLength:(NSUInteger)length options:(MTLResourceOptions)o {
    HeroBuffer *b = [HeroBuffer new]; b.bytes = calloc(1, length ?: 1); b.size = length; b.opts = o; return b;
}
- (id<MTLBuffer>)newBufferWithBytes:(const void *)p length:(NSUInteger)length options:(MTLResourceOptions)o {
    HeroBuffer *b = (HeroBuffer *)[self newBufferWithLength:length options:o]; if (p) memcpy(b.bytes, p, length); return b;
}
- (id<MTLTexture>)newTextureWithDescriptor:(MTLTextureDescriptor *)d {
    if (d.textureType != MTLTextureType2D) { mtl_note("heromtl: newTexture: type %ld not supported (M1)", (long)d.textureType); return nil; }
    return [[HeroTexture alloc] initWithWidth:d.width height:d.height format:d.pixelFormat usage:d.usage];
}
@end

// CAMetalLayer: the system class keeps its device and its drawables inside QuartzCore/Metal; ours are answered from here.
static const void *kDevKey = &kDevKey, *kPoolKey = &kPoolKey, *kIdKey = &kIdKey;
static CGSize layer_pixels(CAMetalLayer *l) {
    CGSize s = l.drawableSize;
    if (s.width < 1 || s.height < 1) { CGFloat sc = l.contentsScale > 0 ? l.contentsScale : 1; s = CGSizeMake(ceil(l.bounds.size.width * sc), ceil(l.bounds.size.height * sc)); }
    return s;
}
static id swz_nextDrawable(CAMetalLayer *self, SEL _cmd) {
    CGSize s = layer_pixels(self);
    if (s.width < 1 || s.height < 1) return nil;
    NSMutableArray *pool = objc_getAssociatedObject(self, kPoolKey);
    if (!pool) { pool = [NSMutableArray array]; objc_setAssociatedObject(self, kPoolKey, pool, OBJC_ASSOCIATION_RETAIN); }
    MTLPixelFormat f = self.pixelFormat ?: MTLPixelFormatBGRA8Unorm;
    for (HeroDrawable *d in [pool copy]) if (d.tex.w != (NSUInteger)s.width || d.tex.h != (NSUInteger)s.height || d.tex.fmt != f) [pool removeObject:d];
    HeroDrawable *d = nil;
    for (HeroDrawable *c in pool) if (!IOSurfaceIsInUse(c.tex.surface)) { d = c; break; }
    if (!d && pool.count < 3) {
        d = [HeroDrawable new];
        d.tex = [[HeroTexture alloc] initWithWidth:(NSUInteger)s.width height:(NSUInteger)s.height format:f usage:MTLTextureUsageRenderTarget];
        if (!d.tex) return nil;
        d.ident = pool.count + 1; [pool addObject:d];
    }
    if (!d) d = pool[0];
    d.owner = self;
    return d;
}
static id swz_device(CAMetalLayer *self, SEL _cmd) { return objc_getAssociatedObject(self, kDevKey); }
static void swz_setDevice(CAMetalLayer *self, SEL _cmd, id dev) { objc_setAssociatedObject(self, kDevKey, dev, OBJC_ASSOCIATION_RETAIN); }

id hero_mtl_device(void) {
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        g_device = [HeroDevice new];
        Class c = objc_getClass("CAMetalLayer");
        if (c) {
            class_replaceMethod(c, sel_registerName("nextDrawable"), (IMP)swz_nextDrawable, "@@:");
            class_replaceMethod(c, sel_registerName("device"), (IMP)swz_device, "@@:");
            class_replaceMethod(c, sel_registerName("setDevice:"), (IMP)swz_setDevice, "v@:@");
        }
        mtl_note("heromtl: %s: device made, CAMetalLayer %s", getprogname(), c ? "patched" : "MISSING");
    });
    return g_device;
}

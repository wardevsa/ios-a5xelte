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
#import <OpenGLES/EAGL.h>
#import <OpenGLES/ES2/gl.h>
#import <OpenGLES/ES2/glext.h>
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


// ---- M2: libraries, functions, pipelines and draws -------------------------------------------------------------------------------------------------
// An application hands Metal either MSL text (newLibraryWithSource:) or a .metallib of AIR bitcode. There is no compiler here: a function is recognised by its
// NAME and the GLSL ES source of that name is taken from this table (docs/S7GE_METAL_DESIGN.md, way (b)). Each entry also says how its vertex buffer 0 is laid out.
typedef struct { const char *name; const char *vs, *fs; int stride; int pos_off; int pos_n; int col_off; int col_n; } ShaderEntry;
static const ShaderEntry kShaders[] = {
    // tri_vertex / tri_fragment: S7GE Lab's triangle: vertices of packed_float2 position + packed_float4 colour (24 bytes), colour passed through
    { "tri_vertex",
      "attribute vec2 pos; attribute vec4 col; varying vec4 c; void main() { gl_Position = vec4(pos, 0.0, 1.0); c = col; }",
      "precision mediump float; varying vec4 c; void main() { gl_FragColor = c; }",
      24, 0, 2, 8, 4 },
};
static const ShaderEntry *shader_for(NSString *vertexName) {
    for (size_t i = 0; i < sizeof kShaders / sizeof kShaders[0]; i++) if ([vertexName isEqualToString:@(kShaders[i].name)]) return &kShaders[i];
    return NULL;
}

@interface HeroFunction : HeroMTLBase <MTLFunction>
@property (nonatomic, copy) NSString *fname;
@property (nonatomic, assign) MTLFunctionType ftype;
@property (nonatomic, copy) NSString *label;
@end
@implementation HeroFunction
- (NSString *)name { return _fname; }
- (MTLFunctionType)functionType { return _ftype; }
- (id<MTLDevice>)device { return (id)g_device; }
@end

@interface HeroLibrary : HeroMTLBase <MTLLibrary>
@property (nonatomic, strong) NSArray<NSString *> *names;
@property (nonatomic, strong) NSDictionary<NSString *, NSNumber *> *types;
@property (nonatomic, copy) NSString *label;
@end
@implementation HeroLibrary
- (id<MTLDevice>)device { return (id)g_device; }
- (NSArray<NSString *> *)functionNames { return _names; }
- (id<MTLFunction>)newFunctionWithName:(NSString *)name {
    NSNumber *ty = _types[name];
    if (!ty) { mtl_note("heromtl: newFunctionWithName: %s is not in the library", name.UTF8String); return nil; }
    HeroFunction *f = [HeroFunction new]; f.fname = name; f.ftype = (MTLFunctionType)ty.integerValue; return f;
}
@end

static HeroLibrary *library_from_source(NSString *src) {
    NSRegularExpression *re = [NSRegularExpression regularExpressionWithPattern:@"\\b(vertex|fragment|kernel)\\s+[\\w:<>]+\\s+(\\w+)\\s*\\(" options:0 error:nil];
    NSMutableArray *names = [NSMutableArray array]; NSMutableDictionary *types = [NSMutableDictionary dictionary];
    for (NSTextCheckingResult *m in [re matchesInString:src options:0 range:NSMakeRange(0, src.length)]) {
        NSString *kind = [src substringWithRange:[m rangeAtIndex:1]], *name = [src substringWithRange:[m rangeAtIndex:2]];
        [names addObject:name]; types[name] = @([kind isEqualToString:@"vertex"] ? MTLFunctionTypeVertex : [kind isEqualToString:@"fragment"] ? MTLFunctionTypeFragment : MTLFunctionTypeKernel);
    }
    HeroLibrary *l = [HeroLibrary new]; l.names = names; l.types = types;
    mtl_note("heromtl: library from source: %lu function(s): %s", (unsigned long)names.count, [names componentsJoinedByString:@","].UTF8String);
    return l;
}


// A .metallib ("MTLB") lists its functions with tags: NAME (u16 length, a C string) followed by TYPE (u16 length 1, u8: 0 vertex, 1 fragment, 2 kernel). Only the names
// and kinds are read: there is no AIR interpreter (M3 decides whether there will be one); a pipeline is built from the name through the table.
static HeroLibrary *library_from_metallib(NSData *data, const char *origin) {
    const uint8_t *b = data.bytes; NSUInteger n = data.length;
    NSMutableArray *names = [NSMutableArray array]; NSMutableDictionary *types = [NSMutableDictionary dictionary];
    if (n < 16 || memcmp(b, "MTLB", 4) != 0) { mtl_note("heromtl: %s: not a metallib (%lu bytes)", origin, (unsigned long)n); return nil; }
    for (NSUInteger i = 0; i + 8 < n; i++) {
        if (memcmp(b + i, "NAME", 4) != 0) continue;
        uint16_t len = (uint16_t)(b[i + 4] | (b[i + 5] << 8));
        if (len < 2 || len > 200 || i + 6 + len > n || b[i + 6 + len - 1] != 0) continue;
        NSString *name = [[NSString alloc] initWithBytes:b + i + 6 length:len - 1 encoding:NSUTF8StringEncoding];
        if (!name) continue;
        int type = -1;
        for (NSUInteger k = i + 6 + len; k + 7 < n && k < i + 6 + len + 64; k++)
            if (memcmp(b + k, "TYPE", 4) == 0) { type = b[k + 6]; break; }
        if (type < 0 || type > 2) continue;
        [names addObject:name];
        types[name] = @(type == 0 ? MTLFunctionTypeVertex : type == 1 ? MTLFunctionTypeFragment : MTLFunctionTypeKernel);
    }
    HeroLibrary *l = [HeroLibrary new]; l.names = names; l.types = types;
    mtl_note("heromtl: metallib %s: %lu bytes, %lu function(s): %s", origin, (unsigned long)n, (unsigned long)names.count, [names componentsJoinedByString:@","].UTF8String);
    return l;
}

@interface HeroPipeline : HeroMTLBase <MTLRenderPipelineState>
@property (nonatomic, assign) const ShaderEntry *entry;
@property (nonatomic, copy) NSString *label;
@end
@implementation HeroPipeline
- (id<MTLDevice>)device { return (id)g_device; }
@end

static EAGLContext *g_gl;
static GLuint compile_shader(GLenum type, const char *src) {
    GLuint s = glCreateShader(type);
    glShaderSource(s, 1, &src, NULL);
    glCompileShader(s);
    GLint ok = 0; glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) { char log[300] = ""; glGetShaderInfoLog(s, sizeof log, NULL, log); mtl_note("heromtl: GLSL %s failed: %s", type == GL_VERTEX_SHADER ? "vertex" : "fragment", log); }
    return s;
}
static GLuint program_for(const ShaderEntry *e) {
    static GLuint progs[8]; static const ShaderEntry *keys[8]; static int n;
    for (int i = 0; i < n; i++) if (keys[i] == e) return progs[i];
    GLuint p = glCreateProgram();
    glAttachShader(p, compile_shader(GL_VERTEX_SHADER, e->vs)); glAttachShader(p, compile_shader(GL_FRAGMENT_SHADER, e->fs));
    glBindAttribLocation(p, 0, "pos"); glBindAttribLocation(p, 1, "col");
    glLinkProgram(p);
    GLint ok = 0; glGetProgramiv(p, GL_LINK_STATUS, &ok);
    if (!ok) mtl_note("heromtl: GLSL link of %s failed", e->name);
    if (n < 8) { keys[n] = e; progs[n++] = p; }
    return p;
}

typedef struct { const ShaderEntry *entry; const void *vbytes; NSUInteger vlen; GLenum mode; NSUInteger start, count; } DrawCall;

// Replays one render pass on the GLES context of the EAGL bridge: clear, draws, then read the pixels back into the target's IOSurface (rows flipped: GL's origin is
// bottom-left, Metal's top-left). The application's own current context is restored afterwards.
static void run_pass(HeroTexture *tex, MTLClearColor k, BOOL clear, NSArray<NSValue *> *draws) {
    if (!g_gl) g_gl = [[EAGLContext alloc] initWithAPI:kEAGLRenderingAPIOpenGLES2];
    if (!g_gl) { mtl_note("heromtl: no EAGLContext (is the application in appgl.on?)"); return; }
    EAGLContext *saved = [EAGLContext currentContext];
    [EAGLContext setCurrentContext:g_gl];
    GLuint fbo = 0, rb = 0;
    glGenFramebuffers(1, &fbo); glGenRenderbuffers(1, &rb);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo); glBindRenderbuffer(GL_RENDERBUFFER, rb);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8_OES, (GLsizei)tex.w, (GLsizei)tex.h);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, rb);
    GLenum st = glCheckFramebufferStatus(GL_FRAMEBUFFER);
    if (st != GL_FRAMEBUFFER_COMPLETE) { mtl_note("heromtl: framebuffer status 0x%x", st); }
    else {
        glViewport(0, 0, (GLsizei)tex.w, (GLsizei)tex.h);
        glClearColor(clear ? k.red : 0, clear ? k.green : 0, clear ? k.blue : 0, clear ? k.alpha : 0); glClear(GL_COLOR_BUFFER_BIT);
        for (NSValue *v in draws) {
            DrawCall d; [v getValue:&d];
            if (!d.entry || !d.vbytes) continue;
            glUseProgram(program_for(d.entry));
            glVertexAttribPointer(0, d.entry->pos_n, GL_FLOAT, GL_FALSE, d.entry->stride, (const uint8_t *)d.vbytes + d.entry->pos_off);
            glVertexAttribPointer(1, d.entry->col_n, GL_FLOAT, GL_FALSE, d.entry->stride, (const uint8_t *)d.vbytes + d.entry->col_off);
            glEnableVertexAttribArray(0); glEnableVertexAttribArray(1);
            glDrawArrays(d.mode, (GLint)d.start, (GLsizei)d.count);
        }
        size_t w = tex.w, h = tex.h;
        uint8_t *px = malloc(w * h * 4);
        glReadPixels(0, 0, (GLsizei)w, (GLsizei)h, GL_RGBA, GL_UNSIGNED_BYTE, px);
        IOSurfaceLock(tex.surface, 0, NULL);
        uint8_t *base = IOSurfaceGetBaseAddress(tex.surface); size_t bpr = IOSurfaceGetBytesPerRow(tex.surface);
        BOOL swap = is_bgra(tex.fmt);
        for (size_t y = 0; y < h; y++) {
            const uint8_t *s = px + (h - 1 - y) * w * 4; uint8_t *dst = base + y * bpr;
            if (swap) for (size_t x = 0; x < w; x++) { dst[x*4] = s[x*4+2]; dst[x*4+1] = s[x*4+1]; dst[x*4+2] = s[x*4]; dst[x*4+3] = s[x*4+3]; }
            else memcpy(dst, s, w * 4);
        }
        IOSurfaceUnlock(tex.surface, 0, NULL);
        free(px);
    }
    glBindFramebuffer(GL_FRAMEBUFFER, 0); glBindRenderbuffer(GL_RENDERBUFFER, 0);
    glDeleteFramebuffers(1, &fbo); glDeleteRenderbuffers(1, &rb);
    [EAGLContext setCurrentContext:saved];
}

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
@property (nonatomic, strong) HeroPipeline *pipe;
@property (nonatomic, strong) NSMutableDictionary<NSNumber *, NSData *> *vbufs;
@property (nonatomic, strong) NSMutableArray<NSValue *> *draws;
@property (nonatomic, strong) NSMutableArray<NSData *> *keep;
@end
@implementation HeroRenderEncoder
- (instancetype)init { if ((self = [super init])) { _vbufs = [NSMutableDictionary dictionary]; _draws = [NSMutableArray array]; _keep = [NSMutableArray array]; } return self; }
- (id<MTLDevice>)device { return (id)g_device; }
- (void)setRenderPipelineState:(id<MTLRenderPipelineState>)s { _pipe = (HeroPipeline *)s; }
- (void)setVertexBuffer:(id<MTLBuffer>)b offset:(NSUInteger)off atIndex:(NSUInteger)i {
    HeroBuffer *hb = (HeroBuffer *)b;
    if (hb) _vbufs[@(i)] = [NSData dataWithBytes:(uint8_t *)hb.bytes + off length:hb.size - off]; else [_vbufs removeObjectForKey:@(i)];
}
- (void)setVertexBytes:(const void *)bytes length:(NSUInteger)len atIndex:(NSUInteger)i { _vbufs[@(i)] = [NSData dataWithBytes:bytes length:len]; }
- (void)setViewport:(MTLViewport)v {}
- (void)setCullMode:(MTLCullMode)m {}
- (void)setFrontFacingWinding:(MTLWinding)w {}
- (void)drawPrimitives:(MTLPrimitiveType)type vertexStart:(NSUInteger)start vertexCount:(NSUInteger)count instanceCount:(NSUInteger)n { [self drawPrimitives:type vertexStart:start vertexCount:count]; }
- (void)drawPrimitives:(MTLPrimitiveType)type vertexStart:(NSUInteger)start vertexCount:(NSUInteger)count {
    NSData *vb = _vbufs[@0];
    if (!_pipe || !_pipe.entry || !vb) { mtl_note("heromtl: draw without a known pipeline or vertex buffer 0 (pipeline %s)", _pipe ? "set" : "NOT set"); return; }
    GLenum mode = type == MTLPrimitiveTypeTriangle ? GL_TRIANGLES : type == MTLPrimitiveTypeTriangleStrip ? GL_TRIANGLE_STRIP : type == MTLPrimitiveTypeLine ? GL_LINES : type == MTLPrimitiveTypeLineStrip ? GL_LINE_STRIP : type == MTLPrimitiveTypePoint ? GL_POINTS : GL_TRIANGLES;
    [_keep addObject:vb];
    DrawCall d = { _pipe.entry, vb.bytes, vb.length, mode, start, count };
    [_draws addObject:[NSValue valueWithBytes:&d objCType:@encode(DrawCall)]];
}
- (void)endEncoding {
    MTLRenderPassColorAttachmentDescriptor *c = [_pass.colorAttachments objectAtIndexedSubscript:0];
    HeroTexture *t = (HeroTexture *)c.texture;
    if (!t || ![t isKindOfClass:[HeroTexture class]]) return;
    BOOL clear = c.loadAction == MTLLoadActionClear;
    if (!clear && _draws.count == 0) { mtl_note("heromtl: render pass of load action %ld with no draws: nothing done", (long)c.loadAction); return; }
    if (_draws.count == 0) { MTLClearColor k = c.clearColor; [t fillRed:k.red green:k.green blue:k.blue alpha:k.alpha]; return; }
    run_pass(t, c.clearColor, clear, _draws);
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
- (id<MTLLibrary>)newLibraryWithSource:(NSString *)source options:(MTLCompileOptions *)options error:(NSError **)error { return library_from_source(source); }
- (void)newLibraryWithSource:(NSString *)source options:(MTLCompileOptions *)options completionHandler:(MTLNewLibraryCompletionHandler)h { HeroLibrary *l = library_from_source(source); if (h) h(l, nil); }
- (id<MTLLibrary>)newDefaultLibrary { return [self newDefaultLibraryWithBundle:[NSBundle mainBundle] error:NULL]; }
- (id<MTLLibrary>)newDefaultLibraryWithBundle:(NSBundle *)b error:(NSError **)error {
    NSString *path = [b pathForResource:@"default" ofType:@"metallib"];
    NSData *d = path ? [NSData dataWithContentsOfFile:path] : nil;
    if (!d) { mtl_note("heromtl: newDefaultLibraryWithBundle: no default.metallib in %s", b.bundlePath.UTF8String); if (error) *error = [NSError errorWithDomain:@"heromtl" code:2 userInfo:nil]; return nil; }
    return library_from_metallib(d, path.lastPathComponent.UTF8String);
}
- (id<MTLLibrary>)newLibraryWithData:(dispatch_data_t)data error:(NSError **)error { return library_from_metallib((NSData *)data, "data"); }
- (id<MTLLibrary>)newLibraryWithFile:(NSString *)path error:(NSError **)error { return library_from_metallib([NSData dataWithContentsOfFile:path], path.lastPathComponent.UTF8String); }
- (id<MTLLibrary>)newLibraryWithURL:(NSURL *)url error:(NSError **)error { return library_from_metallib([NSData dataWithContentsOfURL:url], url.lastPathComponent.UTF8String); }
- (id<MTLComputePipelineState>)newComputePipelineStateWithFunction:(id<MTLFunction>)f error:(NSError **)error {
    mtl_note("heromtl: compute pipeline requested for '%s': not supported (M5)", ((HeroFunction *)f).fname.UTF8String);
    if (error) *error = [NSError errorWithDomain:@"heromtl" code:3 userInfo:nil];
    return nil;
}
- (id<MTLRenderPipelineState>)newRenderPipelineStateWithDescriptor:(MTLRenderPipelineDescriptor *)d error:(NSError **)error {
    HeroFunction *vf = (HeroFunction *)d.vertexFunction;
    const ShaderEntry *e = vf ? shader_for(vf.fname) : NULL;
    {   // what the application asks for, to build the table from
        MTLRenderPipelineColorAttachmentDescriptor *c0 = d.colorAttachments[0];
        mtl_note("heromtl: pipeline request: vertex '%s' fragment '%s' colour0 format %lu blend %d src %ld/%ld dst %ld/%ld vertex descriptor %lu (unused %lu) samples %lu",
                 vf ? vf.fname.UTF8String : "(none)", d.fragmentFunction ? ((HeroFunction *)d.fragmentFunction).fname.UTF8String : "(none)", (unsigned long)c0.pixelFormat, c0.blendingEnabled,
                 (long)c0.sourceRGBBlendFactor, (long)c0.sourceAlphaBlendFactor, (long)c0.destinationRGBBlendFactor, (long)c0.destinationAlphaBlendFactor,
                 (unsigned long)(d.vertexDescriptor ? 1 : 0), (unsigned long)0, (unsigned long)d.sampleCount);
    }
    if (!e) { mtl_note("heromtl: no GLSL for vertex function '%s' (table of M2)", vf ? vf.fname.UTF8String : "(none)"); if (error) *error = [NSError errorWithDomain:@"heromtl" code:1 userInfo:@{ NSLocalizedDescriptionKey: @"no shader of that name in S7GE's table" }]; return nil; }
    HeroPipeline *p = [HeroPipeline new]; p.entry = e; return p;
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
    mtl_note("heromtl: %s: hero_mtl_device: once %ld, g_device %p", getprogname(), (long)once, (__bridge void *)g_device);   // E-0377: a garbage g_device crashed twice
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

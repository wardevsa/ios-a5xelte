/*
 * libheroapp.dylib, in every application while it is in the drop zone (bsd/dev/herolte_gl.c). Two things:
 *
 * An application killed by an Objective-C exception (Photos) leaves only "abort" in the log: the exception's name and
 * reason go there first.
 *
 * OpenGL ES exists in backboardd alone. Anywhere else EAGLContext is Darwin's, over a Metal that is not there, with no
 * functions behind it, and CoreImage on it jumps to address 0 (Settings and Messages, from MobileIcons). So no context
 * is given, as on a device that cannot make one.
 */
#include <dlfcn.h>
#include <fcntl.h>
#include <objc/message.h>
#include <objc/runtime.h>
#include <stdarg.h>
#include <stdbool.h>
#include <string.h>
#include <unistd.h>

extern void herodrm_log(const char *format, ...);
extern void NSSetUncaughtExceptionHandler(void (*handler)(id));
extern const char *getprogname(void);

static const char *
text_of(id object)
{
   id string = object ? ((id (*)(id, SEL))objc_msgSend)(object, sel_registerName("description")) : nil;
   const char *text = string ? ((const char *(*)(id, SEL))objc_msgSend)(string, sel_registerName("UTF8String")) : NULL;
   return text ? text : "(none)";
}

static void
uncaught(id exception)
{
   id name = ((id (*)(id, SEL))objc_msgSend)(exception, sel_registerName("name"));
   id reason = ((id (*)(id, SEL))objc_msgSend)(exception, sel_registerName("reason"));
   herodrm_log("%s: uncaught %s: %s", getprogname(), text_of(name), text_of(reason));
}

static id
no_context(id self, SEL command, unsigned long api)
{
   (void)self;
   (void)command;
   (void)api;
   herodrm_log("%s: no EAGLContext given", getprogname());
   return nil;
}

static id
no_shared_context(id self, SEL command, unsigned long api, id sharegroup)
{
   (void)sharegroup;
   return no_context(self, command, api);
}

/*
 * CoreImage's default context is CI::GLContext whatever the system has: it fills a table of OpenGL ES's functions, empty
 * here, and calls glDisable(GL_DEPTH_TEST) through it. Every CIContext is asked for CoreImage's software renderer instead.
 */
static id (*ci_init_original)(id, SEL, id);
static id ci_software_key;

static id
ci_init(id self, SEL command, id options)
{
   id all = ((id (*)(id, SEL))objc_msgSend)((id)objc_getClass("NSMutableDictionary"), sel_registerName("dictionary"));
   if (options != nil) {
      ((void (*)(id, SEL, id))objc_msgSend)(all, sel_registerName("addEntriesFromDictionary:"), options);
   }
   id yes = ((id (*)(id, SEL, signed char))objc_msgSend)((id)objc_getClass("NSNumber"), sel_registerName("numberWithBool:"), 1);
   ((void (*)(id, SEL, id, id))objc_msgSend)(all, sel_registerName("setObject:forKey:"), yes, ci_software_key);
   return ci_init_original(self, command, all);
}

/*
 * Photos asserts that its data source has one section, and with no library it has none. Only that failure is let by, as a
 * test of what comes after it; every other goes on to the original, with its text already made.
 */
static void (*assert_original)(id, SEL, SEL, id, id, long, id, ...);

static void
assert_failed(id self, SEL command, SEL method, id object, id file, long line, id format, ...)
{
   va_list arguments;
   va_start(arguments, format);
   id text = ((id (*)(id, SEL, id, va_list))objc_msgSend)(
      ((id (*)(id, SEL))objc_msgSend)((id)objc_getClass("NSString"), sel_registerName("alloc")),
      sel_registerName("initWithFormat:arguments:"), format, arguments);
   va_end(arguments);
   if (strstr(text_of(text), "numberOfSections == 1") != NULL) {
      herodrm_log("%s: assertion let by: %s", getprogname(), text_of(text));
      return;
   }
   id percent = ((id (*)(id, SEL, const char *))objc_msgSend)((id)objc_getClass("NSString"),
      sel_registerName("stringWithUTF8String:"), "%@");
   assert_original(self, command, method, object, file, line, percent, text);
}

/*
 * PosterBoard's previews of the home screen use CARenderer with a Metal queue, and there is none: drawn into a bitmap
 * instead (as FiiO JM21's libhakios.poster, MIT, by the same way).
 */
typedef struct { double x, y, w, h; } hero_rect;
typedef struct { double w, h; } hero_size;
extern void UIGraphicsBeginImageContextWithOptions(hero_size size, bool opaque, double scale);
extern void *UIGraphicsGetCurrentContext(void);
extern id UIGraphicsGetImageFromCurrentImageContext(void);
extern void UIGraphicsEndImageContext(void);
#include <CoreGraphics/CoreGraphics.h>

static id
preview_for_view(id self, SEL command, id view)
{
   (void)self;
   (void)command;
   if (view == nil)
      return nil;
   hero_rect bounds = ((hero_rect (*)(id, SEL))objc_msgSend)(view, sel_registerName("bounds"));
   if (bounds.w <= 0 || bounds.h <= 0)
      return nil;
   UIGraphicsBeginImageContextWithOptions((hero_size){ bounds.w, bounds.h }, false, 2.0);
   void *context = UIGraphicsGetCurrentContext();
   if (context != NULL) {
      /*
       * (2026-11-14) -renderInContext: draws only this process's layers: the posters are drawn by their extensions
       * (remote layers), so the gallery's previews came out black. -drawViewHierarchyInRect:afterScreenUpdates: asks
       * the render server (backboardd, which has OpenGL ES) for the picture, remote layers included; if it says no,
       * the old way. DROP_DIR preview.cpu keeps the old way only.
       */
      static int cpu_only = -1;
      if (cpu_only < 0)
         cpu_only = access("/private/var/herolte/preview.cpu", F_OK) == 0;
      signed char drawn = 0;
      if (!cpu_only) {
         drawn = ((signed char (*)(id, SEL, hero_rect, signed char))objc_msgSend)(view,
            sel_registerName("drawViewHierarchyInRect:afterScreenUpdates:"), (hero_rect){ 0, 0, bounds.w, bounds.h }, 1);
      }
      static unsigned told;
      if (told++ < 6)
         herodrm_log("PosterBoard: preview %.0fx%.0f %s", bounds.w, bounds.h,
            drawn ? "from the render server" : "drawn here (renderInContext)");
      if (!drawn) {
         CGContextTranslateCTM((CGContextRef)context, -bounds.x, -bounds.y);
         id layer = ((id (*)(id, SEL))objc_msgSend)(view, sel_registerName("layer"));
         ((void (*)(id, SEL, void *))objc_msgSend)(layer, sel_registerName("renderInContext:"), context);
      }
   }
   id image = UIGraphicsGetImageFromCurrentImageContext();
   UIGraphicsEndImageContext();
   return image;
}

/*
 * Galaxy S7 port (wallpaper census): the original wallpaper reaches backboardd as a 1380x1812 surface over memory that is
 * all zero (0332). CollectionsPoster decodes Background.HEIC through ImageIO and VideoToolbox into 512x512 '420f' tiles,
 * and this phone has no HEVC decoder in hardware. In CollectionsPoster, 20 s and 60 s after it starts: the HEIC decoded
 * here and drawn into a bitmap (how many pixels are not zero), and the process's '420f' surfaces (how much of plane 0,
 * the brightness, is not zero).
 */
#include <CoreFoundation/CoreFoundation.h>
#include <CoreGraphics/CoreGraphics.h>
#include <ImageIO/ImageIO.h>
#include <IOSurface/IOSurfaceRef.h>
#include <pthread.h>
#include <unistd.h>

#define CLOWNFISH_HEIC "/Library/Wallpaper/Collections/Clownfish~iphone.wallpaperCollection/Wallpapers/" \
   "7420.Clownfish-375w-812h@3x~iphone.wallpaper/7420.Clownfish_Background-375w-812h@3x~iphone.ca/assets/Background.HEIC"

static void
heic_census(const char *when)
{
   CFURLRef url = CFURLCreateFromFileSystemRepresentation(NULL, (const UInt8 *)CLOWNFISH_HEIC, strlen(CLOWNFISH_HEIC), false);
   CGImageSourceRef source = url ? CGImageSourceCreateWithURL(url, NULL) : NULL;
   CGImageRef image = source ? CGImageSourceCreateImageAtIndex(source, 0, NULL) : NULL;
   size_t width = image ? CGImageGetWidth(image) : 0, height = image ? CGImageGetHeight(image) : 0;
   size_t lit = 0, all = width * height;
   unsigned long long sum[4] = { 0 };
   if (image && all) {
      uint8_t *pixels = calloc(all, 4);
      CGColorSpaceRef space = CGColorSpaceCreateDeviceRGB();
      CGContextRef bitmap = pixels ? CGBitmapContextCreate(pixels, width, height, 8, width * 4, space,
         kCGImageAlphaPremultipliedLast) : NULL;
      if (bitmap) {
         CGContextDrawImage(bitmap, CGRectMake(0, 0, width, height), image);
         for (size_t i = 0; i < all; i++) {
            const uint8_t *p = pixels + i * 4;
            lit += (p[0] | p[1] | p[2] | p[3]) != 0;
            for (int c = 0; c < 4; c++)
               sum[c] += p[c];
         }
         CGContextRelease(bitmap);
      }
      CGColorSpaceRelease(space);
      free(pixels);
   }
   size_t n = all ? all : 1;
   herodrm_log("%s: wallpaper census (%s): source %d, image %zu x %zu, type %s; %zu of %zu pixels not zero; means %llu %llu %llu %llu",
      getprogname(), when, source != NULL, width, height,
      source && CGImageSourceGetType(source) ? text_of((id)CGImageSourceGetType(source)) : "(none)", lit, all,
      sum[0] / n, sum[1] / n, sum[2] / n, sum[3] / n);
   if (image)
      CGImageRelease(image);
   if (source)
      CFRelease(source);
   if (url)
      CFRelease(url);

   unsigned told = 0;
   for (uint32_t sid = 1; sid < 800 && told < 8; sid++) {
      IOSurfaceRef surface = IOSurfaceLookup(sid);
      if (surface == NULL)
         continue;
      if (IOSurfaceGetPixelFormat(surface) == '420f' && IOSurfaceLock(surface, kIOSurfaceLockReadOnly, NULL) == 0) {
         const uint8_t *luma = IOSurfaceGetBaseAddressOfPlane(surface, 0);
         size_t row = IOSurfaceGetBytesPerRowOfPlane(surface, 0), w = IOSurfaceGetWidthOfPlane(surface, 0),
            h = IOSurfaceGetHeightOfPlane(surface, 0), nonzero = 0, total = 0;
         for (size_t y = 0; luma && y < h; y++)
            for (size_t x = 0; x < w; x++, total++)
               nonzero += luma[row * y + x] != 0;
         IOSurfaceUnlock(surface, kIOSurfaceLockReadOnly, NULL);
         herodrm_log("%s: wallpaper census (%s): surface %u '420f' %zu x %zu, plane 0 %s: %zu of %zu not zero", getprogname(),
            when, sid, w, h, luma ? "mapped" : "NULL", nonzero, total);
         told++;
      }
      CFRelease(surface);
   }
   herodrm_log("%s: wallpaper census (%s): %u '420f' surfaces looked at", getprogname(), when, told);
}

static void *
heic_census_thread(void *unused)
{
   (void)unused;
   sleep(20);
   heic_census("20 s");
   sleep(40);
   heic_census("60 s");
   return NULL;
}

/*
 * mediaserverd crashed 55-69 times a boot (SM-G930W8, sig 11, pc 0): at its start CMCapture warms up the Portrait filter,
 * +[BWCoreImageFilterRenderer _prewarmCoreImagePortraitFilterV1] -> prepareForRenderingWithParameters: -> context:err: ->
 * +[CIContext contextWithOptions:] -> internalContextWithEAGLContext:options:, which builds CI::GLContext over an
 * EAGLContext that cannot exist here (see no_context) and jumps to address 0, even with the software renderer asked for
 * above; launchd starts it again, over and over. In mediaserverd that call is refused (nil), as CoreImage does when it
 * cannot make a context: context:err: has its error path. The drop zone's mediaci.on leaves CoreImage as it was.
 */
static id
no_eagl_ci_context(id self, SEL command, id eagl, id options)
{
   (void)self;
   (void)command;
   herodrm_log("mediaserverd: CIContext over EAGLContext %p refused (options %s)", (void *)eagl, text_of(options));
   return nil;
}

static void
refuse_eagl_ci_context(void)
{
   if (access("/private/var/herolte/mediaci.on", F_OK) == 0)
      return;
   Method eagl_ci = class_getClassMethod(objc_getClass("CIContext"),
                                         sel_registerName("internalContextWithEAGLContext:options:"));
   if (eagl_ci != NULL)
      method_setImplementation(eagl_ci, (IMP)no_eagl_ci_context);
   herodrm_log("mediaserverd: CIContext over EAGLContext %s", eagl_ci != NULL ? "refused" : "not found");
}

__attribute__((constructor)) static void
install(void)
{
   /*
    * (Galaxy S7, iOS 18) DROP_DIR heroapp.off: nothing at all. The kernel copies the drop zone's files but never removes
    * one, so once this library is there every application keeps getting it. On iOS 18 its PosterBoard preview and its
    * CoreImage/EAGL changes in the poster extensions left the wallpaper gallery white (boot-18k21 on; it was fine in
    * boot-18k20, before the library), and it did not bring Settings' icons back.
    */
   if (access("/private/var/herolte/heroapp.off", F_OK) == 0) {
      return;
   }
   /*
    * The front camera's capture device (gpu/camera, libnotefecam.dylib; the Note FE port's 0458) in mediaserverd only,
    * with the drop zone's cam.media = 1. hero-run makes /dev/hakios-camera (kern.notefe_cam=7) and restarts mediaserverd.
    */
   if (strcmp(getprogname(), "mediaserverd") == 0) {
      char flag = '0';
      int ff = open("/private/var/herolte/cam.media", O_RDONLY);
      if (ff >= 0) {
         (void)read(ff, &flag, 1);
         close(ff);
      }
      if (flag == '1' && access("/private/var/herolte/lib/libnotefecam.dylib", F_OK) == 0) {
         void *cam = dlopen("/private/var/herolte/lib/libnotefecam.dylib", RTLD_NOW);
         herodrm_log("mediaserverd: libnotefecam %s", cam ? "loaded" : dlerror());
      }
   }
   if (strcmp(getprogname(), "CollectionsPoster") == 0) {
      pthread_t census;
      if (pthread_create(&census, NULL, heic_census_thread, NULL) == 0)
         pthread_detach(census);
   }
   if (strcmp(getprogname(), "PosterBoard") == 0) {
      dlopen("/System/Library/PrivateFrameworks/PosterBoard.framework/PosterBoard", RTLD_LAZY);
      Method preview = class_getInstanceMethod(objc_getClass("PBFHomeScreenPreviewImageBuilder"), sel_registerName("_imageForView:"));
      if (preview != NULL) {
         method_setImplementation(preview, (IMP)preview_for_view);
      }
      herodrm_log("PosterBoard: home preview in a bitmap: %d", preview != NULL);
   }
   NSSetUncaughtExceptionHandler(uncaught);
   dlopen("/System/Library/Frameworks/OpenGLES.framework/OpenGLES", RTLD_LAZY);
   Class context = objc_getClass("EAGLContext");
   if (context != Nil) {
      method_setImplementation(class_getInstanceMethod(context, sel_registerName("initWithAPI:")), (IMP)no_context);
      method_setImplementation(class_getInstanceMethod(context, sel_registerName("initWithAPI:sharegroup:")),
                               (IMP)no_shared_context);
   }
   Method properties = context != Nil ? class_getInstanceMethod(context, sel_registerName("initWithAPI:properties:")) : NULL;
   if (properties != NULL) {
      method_setImplementation(properties, (IMP)no_shared_context);
   }
   void *core_image = dlopen("/System/Library/Frameworks/CoreImage.framework/CoreImage", RTLD_LAZY);
   id *key = core_image ? dlsym(core_image, "kCIContextUseSoftwareRenderer") : NULL;
   Method init = class_getInstanceMethod(objc_getClass("CIContext"), sel_registerName("initWithOptions:"));
   if (key != NULL && init != NULL) {
      ci_software_key = *key;
      ci_init_original = (id (*)(id, SEL, id))method_setImplementation(init, (IMP)ci_init);
   }
   herodrm_log("%s: libheroapp: CoreImage %s", getprogname(), ci_init_original ? "in software" : "as it was");
   if (strcmp(getprogname(), "mediaserverd") == 0)
      refuse_eagl_ci_context();         /* after CoreImage is loaded: CIContext is there */
   Method assertion = class_getInstanceMethod(objc_getClass("NSAssertionHandler"),
      sel_registerName("handleFailureInMethod:object:file:lineNumber:description:"));
   if (assertion != NULL) {
      assert_original = (void (*)(id, SEL, SEL, id, id, long, id, ...))method_setImplementation(assertion, (IMP)assert_failed);
   }
}

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
#include <CoreGraphics/CoreGraphics.h>
#include <errno.h>
#include <objc/message.h>
#include <objc/runtime.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#define DROP_DIR "/private/var/herolte/"
extern void herodrm_log(const char *format, ...);
/* min112c (E-0335): stderr of assetsd did not reach assetsd.err (launchd's redirection does not seem to apply, DYLD_PRINT_LIBRARIES printed nothing
 * either), so the library also appends its lines to a world-writable file of its own: if /private/var/tmp/heroapp.log exists, the library loads. */
#include <fcntl.h>
#include <sys/stat.h>
static void
hero_note(const char *format, ...)
{
   char line[640];
   va_list ap;
   va_start(ap, format);
   int n = vsnprintf(line, sizeof line - 1, format, ap);
   va_end(ap);
   if (n <= 0)
      return;
   if (n > (int)sizeof line - 2)
      n = (int)sizeof line - 2;
   line[n++] = '\n';
   (void)!write(2, line, (size_t)n);
   int fd = open("/private/var/tmp/heroapp.log", O_WRONLY | O_CREAT | O_APPEND, 0666);
   if (fd >= 0) {
      (void)!write(fd, line, (size_t)n);
      fchmod(fd, 0666);
      close(fd);
   }
}

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
   /* min112 (E-0334): herodrm_log did not reach the kernel log from assetsd (a sandboxed daemon), and the exception's text never
    * reached stderr either (libc++abi writes to os_log). stderr is the file launchd opened for the job (assetsd.err), so writing
    * to it directly bypasses the sandbox. */
   hero_note("libheroapp: %s: uncaught %s: %s", getprogname(), text_of(name), text_of(reason));
}



/*
 * min127d (E-0352): the kernel's crash line has only addresses, and with the EAGL bridge loaded S7GE Lab dies with SIGSEGV at address 8 in a system library
 * (pc 0x209de1a78) while it calls renderbufferStorage:fromDrawable:, without saying which library. A handler for SIGSEGV, SIGBUS, SIGILL and SIGTRAP writes, to
 * /private/var/tmp/heroapp-crash.txt, the signal, the fault address and, for the pc, the link register and up to twelve frames of the frame-pointer chain, the
 * image (its path), the address inside it and the nearest exported symbol, from dladdr; then it lets the default action go on (the kernel's crash line and the
 * report stay as they were). Every program that loads libheroapp gets it. DROP_DIR crash.off turns it off.
 */
#include <signal.h>
#include <sys/ucontext.h>

static void
note_address(int fd, const char *label, uint64_t pc)
{
   Dl_info info;
   char line[420];
   if (pc != 0 && dladdr((void *)pc, &info) && info.dli_fname) {
      const char *base = strrchr(info.dli_fname, '/');
      int n = snprintf(line, sizeof line, "  %s %#llx  %s +%#llx  %s\n", label, (unsigned long long)pc, base ? base + 1 : info.dli_fname,
                       (unsigned long long)(pc - (uint64_t)info.dli_fbase), info.dli_sname ? info.dli_sname : "(no symbol)");
      (void)!write(fd, line, (size_t)n);
   } else {
      int n = snprintf(line, sizeof line, "  %s %#llx  (no image)\n", label, (unsigned long long)pc);
      (void)!write(fd, line, (size_t)n);
   }
}

static void
on_crash(int sig, siginfo_t *si, void *ctx)
{
   int fd = open("/private/var/tmp/heroapp-crash.txt", O_WRONLY | O_CREAT | O_APPEND, 0666);
   if (fd >= 0) {
      char head[200];
      ucontext_t *uc = (ucontext_t *)ctx;
      int n = snprintf(head, sizeof head, "crash in %s pid %d: signal %d, fault address %p\n", getprogname(), (int)getpid(), sig, si ? si->si_addr : NULL);
      (void)!write(fd, head, (size_t)n);
      if (uc && uc->uc_mcontext) {
         uint64_t *fp = (uint64_t *)uc->uc_mcontext->__ss.__fp;
         note_address(fd, "pc", uc->uc_mcontext->__ss.__pc);
         note_address(fd, "lr", uc->uc_mcontext->__ss.__lr);
         for (int i = 0; i < 12 && fp && ((uint64_t)fp & 7) == 0 && (uint64_t)fp > 0x1000; i++) {
            note_address(fd, "bt", fp[1]);
            uint64_t *next = (uint64_t *)fp[0];
            if (next <= fp)
               break;
            fp = next;
         }
      }
      fchmod(fd, 0666);
      close(fd);
   }
   signal(sig, SIG_DFL);
   raise(sig);
}

static void
install_crash_notes(void)
{
   if (access(DROP_DIR "crash.off", F_OK) == 0)
      return;
   struct sigaction sa;
   memset(&sa, 0, sizeof sa);
   sa.sa_sigaction = on_crash;
   sa.sa_flags = SA_SIGINFO | SA_NODEFER;
   sigemptyset(&sa.sa_mask);
   sigaction(SIGSEGV, &sa, NULL);
   sigaction(SIGBUS, &sa, NULL);
   sigaction(SIGILL, &sa, NULL);
   sigaction(SIGTRAP, &sa, NULL);
}

/*
 * min127c (E-0351): S7GE Lab, an ordinary app, got "EAGLContext(api: .openGLES2) returned nil" because the lines below make every initWithAPI: answer nil
 * (the stock renderer's table of functions is empty here and jumps to 0), and the project's EAGL bridge (libheroeagl: EAGLContext on OSMesa and
 * Panfrost, renderbufferStorage:fromDrawable: and presentRenderbuffer: into an IOSurface) is only loaded in backboardd. DROP_DIR appgl.on, one program name a
 * line (or "all"), lets those programs load the bridge instead: the nil answers are not installed for them and libheroeagl, whose constructor puts its methods
 * into the real EAGLContext, is loaded after OpenGLES.
 */
static bool
appgl_wanted(void)
{
   FILE *f = fopen(DROP_DIR "appgl.on", "r");
   char line[128];
   bool want = false;
   while (f && fgets(line, sizeof line, f)) {
      size_t n = strlen(line);
      while (n && (line[n - 1] == '\n' || line[n - 1] == '\r' || line[n - 1] == ' '))
         line[--n] = 0;
      if (strcmp(line, "all") == 0 || strcmp(line, getprogname()) == 0)
         want = true;
   }
   if (f)
      fclose(f);
   return want;
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
 * min113c (E-0337): with the drop zone reachable, assetsd's own words are "assetsd requires TCCPhotosService access", and Messages still
 * dies in CI::GLContext although CoreImage is asked for software. Two looks from inside the processes, into files of their own:
 *  - assetsd: its entitlements (csops 7) and what TCC answers for Photos, to see which of the two the check fails on;
 *  - MobileSMS: the selectors of CIContext, to find a way into CoreImage that does not go through EAGL.
 */
#include <stdint.h>
#include <string.h>
extern int csops(int pid, unsigned int ops, void *useraddr, size_t usersize);

static void
hero_file(const char *name, const char *text, size_t len)
{
   char path[160];
   snprintf(path, sizeof path, "/private/var/tmp/%s", name);
   int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0666);
   if (fd >= 0) {
      (void)!write(fd, text, len);
      fchmod(fd, 0666);
      close(fd);
   }
}

static void
look_at_assetsd(void)
{
   uint8_t blob[16384];
   char out[16384 + 256];
   memset(blob, 0, sizeof blob);
   int r = csops(getpid(), 7, blob, sizeof blob);
   int n = snprintf(out, sizeof out, "csops(ENTITLEMENTS_BLOB) = %d, errno %d\n", r, r != 0 ? errno : 0);
   uint32_t length = ((uint32_t)blob[4] << 24) | ((uint32_t)blob[5] << 16) | ((uint32_t)blob[6] << 8) | blob[7];
   n += snprintf(out + n, sizeof out - (size_t)n, "blob length %u\n", length);
   for (size_t i = 8; i < sizeof blob && i < length && n < (int)sizeof out - 2; i++)
      out[n++] = (blob[i] >= 32 && blob[i] < 127) || blob[i] == '\n' ? (char)blob[i] : ' ';
   out[n++] = '\n';
   void *tcc = dlopen("/System/Library/PrivateFrameworks/TCC.framework/TCC", RTLD_LAZY);
   int (*preflight)(id, id) = tcc ? (int (*)(id, id))dlsym(tcc, "TCCAccessPreflight") : NULL;
   id service = ((id (*)(id, SEL, const char *))objc_msgSend)((id)objc_getClass("NSString"), sel_registerName("stringWithUTF8String:"), "kTCCServicePhotos");
   n += snprintf(out + n, sizeof out - (size_t)n, "TCC framework %s, TCCAccessPreflight(kTCCServicePhotos) = %d\n", tcc ? "loaded" : "NOT loaded",
                 preflight ? preflight(service, nil) : -99);
   hero_file("heroapp-assetsd.txt", out, (size_t)n);
}

static void
look_at_coreimage(void)
{
   static char out[65536];
   size_t n = 0;
   Class cls = objc_getClass("CIContext");
   for (int meta = 0; meta < 2 && cls != Nil; meta++) {
      Class c = meta ? object_getClass((id)cls) : cls;
      unsigned count = 0;
      Method *list = class_copyMethodList(c, &count);
      n += (size_t)snprintf(out + n, sizeof out - n, "== %s methods of CIContext (%u)\n", meta ? "class" : "instance", count);
      for (unsigned i = 0; i < count && n + 160 < sizeof out; i++)
         n += (size_t)snprintf(out + n, sizeof out - n, "%s\n", sel_getName(method_getName(list[i])));
      free(list);
   }
   hero_file("heroapp-coreimage.txt", out, n);
}
/*
 * CoreImage's default context is CI::GLContext whatever the system has: it fills a table of OpenGL ES's functions, empty
 * here, and calls glDisable(GL_DEPTH_TEST) through it. Every CIContext is asked for CoreImage's software renderer instead.
 */
static id (*ci_init_original)(id, SEL, id);
static id ci_software_key;

/*
 * min113d (E-0337): asking for the software renderer was not enough, and a CGContext-backed context (initWithCGContext:options:) ends in the same
 * CI::GLContext: in this CoreImage every context is GL-based and fills the table of OpenGL ES functions that no GL driver in an app fills. Messages
 * dies in MobileIcons' shared icon compositor (+[CIContext _MI_sharedIconCompositorContext], and IconServices' twin _IS_...), which only wants a
 * context to scale icons with Lanczos: both are answered with nil, and what MobileIcons does without it is what min113e shows.
 */
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

static id
no_icon_context(id self, SEL command)
{
   (void)self;
   (void)command;
   hero_note("libheroapp: %s: icon compositor context refused", getprogname());
   return nil;
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
      CGContextTranslateCTM((CGContextRef)context, -bounds.x, -bounds.y);
      id layer = ((id (*)(id, SEL))objc_msgSend)(view, sel_registerName("layer"));
      ((void (*)(id, SEL, void *))objc_msgSend)(layer, sel_registerName("renderInContext:"), context);
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

__attribute__((constructor)) static void
install(void)
{
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
   install_crash_notes();
   hero_note("libheroapp: %s: loaded (pid %d)", getprogname(), (int)getpid());
   dlopen("/System/Library/Frameworks/OpenGLES.framework/OpenGLES", RTLD_LAZY);
   Class context = objc_getClass("EAGLContext");
   bool bridge = false;
   if (appgl_wanted()) {
      void *handle = dlopen(DROP_DIR "lib/libheroeagl.dylib", RTLD_NOW);
      bridge = handle != NULL;
      hero_note("libheroapp: %s: EAGL bridge %s%s", getprogname(), bridge ? "loaded" : "NOT loaded: ", bridge ? "" : (dlerror() ? dlerror() : "?"));
      if (bridge) {
         /* E-0352: which image each EAGLContext method comes from now: libheroeagl means the bridge's, OpenGLES the stock one */
         static const char *const names[] = { "initWithAPI:", "initWithAPI:sharegroup:", "renderbufferStorage:fromDrawable:", "presentRenderbuffer:" };
         Class real = objc_getClass("EAGLContext");
         hero_note("libheroapp: %s: BGEAGLContext %s, EAGLSharegroup %s, EAGLContext %s", getprogname(), objc_getClass("BGEAGLContext") ? "exists" : "MISSING",
                   objc_getClass("EAGLSharegroup") ? "exists" : "MISSING", real ? "exists" : "MISSING");
         for (int k = 0; real && k < 4; k++) {
            IMP imp = class_getMethodImplementation(real, sel_registerName(names[k]));
            Dl_info info;
            const char *where = (dladdr((void *)imp, &info) && info.dli_fname) ? strrchr(info.dli_fname, '/') : NULL;
            hero_note("libheroapp: %s: EAGLContext %s is in %s", getprogname(), names[k], where ? where + 1 : "(unknown)");
         }
      }
   }
   if (context != Nil && !bridge) {
      method_setImplementation(class_getInstanceMethod(context, sel_registerName("initWithAPI:")), (IMP)no_context);
      method_setImplementation(class_getInstanceMethod(context, sel_registerName("initWithAPI:sharegroup:")),
                               (IMP)no_shared_context);
   }
   Method properties = context != Nil && !bridge ? class_getInstanceMethod(context, sel_registerName("initWithAPI:properties:")) : NULL;
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
   {
      Class ci_class = objc_getClass("CIContext");
      static const char *const names[] = { "_MI_sharedIconCompositorContext", "_IS_sharedIconCompositorContext" };
      for (int k = 0; k < 2 && ci_class != Nil; k++) {
         Method m = class_getClassMethod(ci_class, sel_registerName(names[k]));
         if (m != NULL) {
            method_setImplementation(m, (IMP)no_icon_context);
            hero_note("libheroapp: %s: %s answers nil", getprogname(), names[k]);
         }
      }
   }
   if (strcmp(getprogname(), "assetsd") == 0)
      look_at_assetsd();
   if (strcmp(getprogname(), "MobileSMS") == 0)
      look_at_coreimage();
   herodrm_log("%s: libheroapp: CoreImage %s", getprogname(), ci_init_original ? "in software" : "as it was");
   hero_note("libheroapp: %s: CoreImage %s", getprogname(), ci_init_original ? "in software" : "as it was");
   Method assertion = class_getInstanceMethod(objc_getClass("NSAssertionHandler"),
      sel_registerName("handleFailureInMethod:object:file:lineNumber:description:"));
   if (assertion != NULL) {
      assert_original = (void (*)(id, SEL, SEL, id, id, long, id, ...))method_setImplementation(assertion, (IMP)assert_failed);
   }
}

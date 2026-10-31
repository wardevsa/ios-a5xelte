/*
 * libherosb.dylib, in SpringBoard (boot-arg herosb=1, bsd/dev/herolte_gl.c): PosterBoard has no poster providers on this
 * root, so the wallpaper windows stay black. The picture of the drop zone goes into them, and behind the home screen.
 * DROP_DIR wallpaper.off turns it off.
 */
#include <CoreFoundation/CoreFoundation.h>
#include <dispatch/dispatch.h>
#include <objc/message.h>
#include <objc/runtime.h>
#include <stdbool.h>
#include <string.h>
#include <unistd.h>

#define DROP_DIR "/private/var/herolte/"
#define VIEW_TAG 0x48455230

typedef struct { double x, y, w, h; } rect_t;

extern void herodrm_log(const char *format, ...);

static id
nsstring(const char *text)
{
   return ((id (*)(id, SEL, const char *))objc_msgSend)((id)objc_getClass("NSString"),
      sel_registerName("stringWithUTF8String:"), text);
}

static id
send0(id target, const char *selector)
{
   return ((id (*)(id, SEL))objc_msgSend)(target, sel_registerName(selector));
}

static id picture;
static bool gestures_on;
static bool status_bar_kept;
static unsigned rounds;

static void
give_picture(id window, bool behind_all)
{
   if (((id (*)(id, SEL, long))objc_msgSend)(window, sel_registerName("viewWithTag:"), VIEW_TAG))
      return;
   id view = ((id (*)(id, SEL, id))objc_msgSend)(send0((id)objc_getClass("UIImageView"), "alloc"),
      sel_registerName("initWithImage:"), picture);
   rect_t bounds = ((rect_t (*)(id, SEL))objc_msgSend)(window, sel_registerName("bounds"));
   ((void (*)(id, SEL, rect_t))objc_msgSend)(view, sel_registerName("setFrame:"), bounds);
   ((void (*)(id, SEL, long))objc_msgSend)(view, sel_registerName("setContentMode:"), 2);          /* aspect fill */
   ((void (*)(id, SEL, unsigned long))objc_msgSend)(view, sel_registerName("setAutoresizingMask:"), 18);
   ((void (*)(id, SEL, long))objc_msgSend)(view, sel_registerName("setTag:"), VIEW_TAG);
   ((void (*)(id, SEL, BOOL))objc_msgSend)(view, sel_registerName("setUserInteractionEnabled:"), NO);
   if (behind_all)
      ((void (*)(id, SEL, id, long))objc_msgSend)(window, sel_registerName("insertSubview:atIndex:"), view, 0);
   else
      ((void (*)(id, SEL, id))objc_msgSend)(window, sel_registerName("addSubview:"), view);
   herodrm_log("herosb: picture in %s, %.0f x %.0f", object_getClassName(window), bounds.w, bounds.h);
}

static void
look_at_windows(void *unused)
{
   rounds++;
   Class windows_class = objc_getClass("UIWindow");
   SEL all = sel_registerName("allWindowsIncludingInternalWindows:onlyVisibleWindows:");
   id windows = windows_class && class_respondsToSelector(object_getClass((id)windows_class), all) ?
      ((id (*)(id, SEL, BOOL, BOOL))objc_msgSend)((id)windows_class, all, YES, NO) : nil;
   if (!picture && objc_getClass("UIImage")) {
      picture = ((id (*)(id, SEL, id))objc_msgSend)((id)objc_getClass("UIImage"), sel_registerName("imageWithContentsOfFile:"),
         nsstring(DROP_DIR "wallpaper.png"));
      if (picture)
         send0(picture, "retain");
   }
   size_t count = windows ? ((size_t (*)(id, SEL))objc_msgSend)(windows, sel_registerName("count")) : 0;
   if (rounds == 1 || rounds == 6)
      herodrm_log("herosb: round %u, %zu windows, picture %d, gestures %d, status bar %d", rounds, count, picture != nil, gestures_on, status_bar_kept);
   for (size_t i = 0; picture && i < count; i++) {
      id window = ((id (*)(id, SEL, size_t))objc_msgSend)(windows, sel_registerName("objectAtIndex:"), i);
      const char *name = object_getClassName(window);
      if (rounds == 6)
         herodrm_log("herosb: window %s", name);
      if (strstr(name, "Wallpaper"))
         give_picture(window, false);
      else if (strcmp(name, "SBHomeScreenWindow") == 0)
         give_picture(window, true);
   }
   if (rounds < 60)
      dispatch_after_f(dispatch_time(DISPATCH_TIME_NOW, 5 * NSEC_PER_SEC), dispatch_get_main_queue(), NULL, look_at_windows);
}

/*
 * The ADT says "home button" (home-button-type 1): UIKit then has a status bar for this 750x1334 screen, where type 2
 * gets the red rdar:45025538 one. SpringBoard alone is told type 2, which is where the home gestures are decided, as
 * the old home-gesture tweaks did. DROP_DIR gestures.off turns it off.
 */
static long
says_gestures(id self, SEL cmd)
{
   return 2;
}

static BOOL
says_yes(id self, SEL cmd)
{
   return YES;
}

/*
 * ...but told type 2, UIKit in SpringBoard falls back to the red rdar:45025538 status bar for a 750x1334 screen. There
 * the plain phone's status bar is what it gets, as the other processes do.
 */
static Class (*status_bar_was)(id, SEL, id, id);

static Class
status_bar_for_screen(id self, SEL cmd, id screen, id info)
{
   Class chosen = status_bar_was(self, cmd, screen, info);
   Class phone = objc_getClass("_UIStatusBarVisualProvider_Phone");
   if (chosen == objc_getClass("_UIStatusBarVisualProvider_Fallback") && phone)
      return phone;
   return chosen;
}

static void
keep_status_bar(void)
{
   Class provider = objc_getClass("_UIStatusBarVisualProvider_iOS");
   Method pick = provider ? class_getClassMethod(provider, sel_registerName("visualProviderSubclassForScreen:visualProviderInfo:")) : NULL;
   if (pick)
      status_bar_was = (Class (*)(id, SEL, id, id))method_setImplementation(pick, (IMP)status_bar_for_screen);
   status_bar_kept = pick != NULL;
}

static void
ask_for_gestures(void)
{
   keep_status_bar();
   Class platform = objc_getClass("BSPlatform");
   Method type = platform ? class_getInstanceMethod(platform, sel_registerName("homeButtonType")) : NULL;
   if (type) {
      method_setImplementation(type, (IMP)says_gestures);
      gestures_on = true;
   }
   Class settings = objc_getClass("SBHomeGestureSettings");
   Method enabled = settings ? class_getInstanceMethod(settings, sel_registerName("isHomeGestureEnabled")) : NULL;
   if (enabled)
      method_setImplementation(enabled, (IMP)says_yes);
}

__attribute__((constructor)) static void
herosb_start(void)
{
   if (access(DROP_DIR "gestures.off", F_OK) != 0)
      ask_for_gestures();
   if (access(DROP_DIR "wallpaper.off", F_OK) == 0)
      return;
   dispatch_after_f(dispatch_time(DISPATCH_TIME_NOW, 10 * NSEC_PER_SEC), dispatch_get_main_queue(), NULL, look_at_windows);
}

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
#include <stdlib.h>
#include <stdio.h>
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
static int status_bar_kept, status_bar_asked, status_bar_replaced;
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


/*
 * min124 (E-0345): the status bar is not visible at the top although libherosb reports gestures 1, two provider hooks, the plain phone provider
 * asked once and nothing replaced, and the UIStatusBarWindow exists. What the bar's windows hold, the geometry of each view and whether it is
 * hidden or transparent, is written to the log (rounds 6 and 20), together with the selectors of the status bar classes that mention a provider.
 */
typedef struct { double top, left, bottom, right; } insets_t;

static void
dump_view(id view, int depth)
{
   if (!view || depth > 5)
      return;
   rect_t f = ((rect_t (*)(id, SEL))objc_msgSend)(view, sel_registerName("frame"));
   BOOL hidden = ((BOOL (*)(id, SEL))objc_msgSend)(view, sel_registerName("isHidden"));
   double alpha = ((double (*)(id, SEL))objc_msgSend)(view, sel_registerName("alpha"));
   herodrm_log("herosb: bar %*s%s frame %.1f,%.1f %.1f x %.1f hidden %d alpha %.2f", depth * 2, "", object_getClassName(view), f.x, f.y, f.w, f.h,
      hidden, alpha);
   id subs = send0(view, "subviews");
   size_t n = subs ? ((size_t (*)(id, SEL))objc_msgSend)(subs, sel_registerName("count")) : 0;
   for (size_t i = 0; i < n && i < 12; i++)
      dump_view(((id (*)(id, SEL, size_t))objc_msgSend)(subs, sel_registerName("objectAtIndex:"), i), depth + 1);
}

static void
dump_selectors(const char *class_name)
{
   Class c = objc_getClass(class_name);
   for (int meta = 0; c && meta < 2; meta++) {
      unsigned count = 0;
      Method *list = class_copyMethodList(meta ? object_getClass((id)c) : c, &count);
      for (unsigned i = 0; i < count; i++) {
         const char *s = sel_getName(method_getName(list[i]));
         if (strcasestr(s, "provider") || strcasestr(s, "hidden") || strcasestr(s, "height") || strcasestr(s, "style") || strcasestr(s, "region"))
            herodrm_log("herosb: sel %s %s%s", class_name, meta ? "+" : "-", s);
      }
      free(list);
   }
}

static void
look_at_status_bar(id windows, size_t count, unsigned round)
{
   for (size_t i = 0; i < count; i++) {
      id window = ((id (*)(id, SEL, size_t))objc_msgSend)(windows, sel_registerName("objectAtIndex:"), i);
      const char *name = object_getClassName(window);
      if (strcmp(name, "UIStatusBarWindow") == 0 || strcmp(name, "SBStatusBarReusePoolWindow") == 0 || strcmp(name, "SBHomeScreenWindow") == 0) {
         rect_t b = ((rect_t (*)(id, SEL))objc_msgSend)(window, sel_registerName("bounds"));
         insets_t s = ((insets_t (*)(id, SEL))objc_msgSend)(window, sel_registerName("safeAreaInsets"));
         herodrm_log("herosb: bar round %u window %s bounds %.0f x %.0f safe insets %.1f %.1f %.1f %.1f", round, name, b.w, b.h, s.top, s.left, s.bottom, s.right);
         if (strcmp(name, "SBHomeScreenWindow") != 0 || round == 20)
            dump_view(window, 0);
      }
   }
   if (round == 6) {
      dump_selectors("_UIStatusBar");
      dump_selectors("UIStatusBar_Modern");
      unsigned n = 0;
      Class *all = objc_copyClassList(&n);
      for (unsigned i = 0; i < n; i++) {
         const char *cn = class_getName(all[i]);
         if (strstr(cn, "_UIStatusBarVisualProvider") || strstr(cn, "StatusBarManager"))
            herodrm_log("herosb: class %s", cn);
      }
      free(all);
   }
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
      herodrm_log("herosb: round %u, %zu windows, picture %d, gestures %d, status bar hooks %d asked %d replaced %d", rounds, count, picture != nil, gestures_on, status_bar_kept, status_bar_asked, status_bar_replaced);
   if (windows && (rounds == 6 || rounds == 20))
      look_at_status_bar(windows, count, rounds);
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
 * ...but told type 2, UIKit in SpringBoard asks each provider class in turn, none takes a 750x1334 screen and it ends on
 * the red rdar:45025538 fallback. The plain phone's class takes any screen here, and is put in where the fallback
 * still reaches the status bar.
 */
static Class
phone_takes_it(id self, SEL cmd, id screen, id info)
{
   status_bar_asked++;
   return objc_getClass("_UIStatusBarVisualProvider_Phone");
}

static void (*set_provider_was)(id, SEL, Class);

static void
set_provider(id self, SEL cmd, Class provider)
{
   if (provider == objc_getClass("_UIStatusBarVisualProvider_Fallback")) {
      status_bar_replaced++;
      provider = objc_getClass("_UIStatusBarVisualProvider_Phone");
   }
   set_provider_was(self, cmd, provider);
}

static void
keep_status_bar(void)
{
   static const char *const providers[] = { "_UIStatusBarVisualProvider_iOS", "_UIStatusBarVisualProvider_Phone",
      "_UIStatusBarVisualProvider_Fallback" };
   SEL pick = sel_registerName("visualProviderSubclassForScreen:visualProviderInfo:");
   for (size_t i = 0; i < sizeof(providers) / sizeof(providers[0]); i++) {
      Class provider = objc_getClass(providers[i]);
      Method method = provider ? class_getClassMethod(provider, pick) : NULL;
      if (method) {
         method_setImplementation(method, (IMP)phone_takes_it);
         status_bar_kept++;
      }
   }
   Class bar = objc_getClass("_UIStatusBar");
   Method setter = bar ? class_getInstanceMethod(bar, sel_registerName("setVisualProviderClass:")) : NULL;
   if (setter) {
      set_provider_was = (void (*)(id, SEL, Class))method_setImplementation(setter, (IMP)set_provider);
      status_bar_kept += 10;
   }
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

/*
 * SpringBoard's own frame rate caps (from Scion's inject_sb.c, Galaxy S9). Some of its animations ask for fewer frames
 * than the panel has: the crossfade of the page dots and the search pill after every page's slide is
 * CAFrameRateRangeMake(20, 30, 0), and CoreAnimation gives SpringBoard 30 a second for as long as it runs -- on the S9
 * half of all the refreshes missed while swiping. A range whose most is under 60 gets 60 as its most and preferred.
 * DROP_DIR fps.off leaves them as Apple set them.
 */
typedef struct { float minimum, maximum, preferred; } frame_rate_range_t;
static void (*fluid_set_range_was)(id, SEL, frame_rate_range_t, unsigned);
static void (*animation_set_range_was)(id, SEL, frame_rate_range_t, unsigned);
static unsigned ranges_raised;

static frame_rate_range_t
raise_range(frame_rate_range_t range)
{
   if (range.maximum > 0.0f && range.maximum < 60.0f) {
      range.maximum = 60.0f;
      range.preferred = 60.0f;
      ranges_raised++;
   }
   return range;
}

static void
fluid_set_range(id self, SEL cmd, frame_rate_range_t range, unsigned reason)
{
   fluid_set_range_was(self, cmd, raise_range(range), reason);
}

static void
animation_set_range(id self, SEL cmd, frame_rate_range_t range, unsigned reason)
{
   animation_set_range_was(self, cmd, raise_range(range), reason);
}

static void
raise_frame_rates(void)
{
   SEL set = sel_registerName("setFrameRateRange:highFrameRateReason:");
   Class fluid = objc_getClass("SBFFluidBehaviorSettings"), animation = objc_getClass("SBFAnimationSettings");
   Method m = fluid && !fluid_set_range_was ? class_getInstanceMethod(fluid, set) : NULL;
   if (m)
      fluid_set_range_was = (void (*)(id, SEL, frame_rate_range_t, unsigned))method_setImplementation(m, (IMP)fluid_set_range);
   m = animation && !animation_set_range_was ? class_getInstanceMethod(animation, set) : NULL;
   if (m)
      animation_set_range_was = (void (*)(id, SEL, frame_rate_range_t, unsigned))method_setImplementation(m, (IMP)animation_set_range);
   herodrm_log("herosb: frame rate caps raised to 60: fluid settings %s, animation settings %s",
      fluid_set_range_was ? "yes" : "NO", animation_set_range_was ? "yes" : "NO");
}

static void
report_ranges(void *unused)
{
   herodrm_log("herosb: %u frame rate ranges raised to 60 so far", ranges_raised);
}


/*
 * min125b (E-0347): sbmode 1 (the platform on home-button type 1) shows the bar, UIStatusBar_Modern 375 x 20 with the clock, the carrier and the battery,
 * but the home gestures are not there; sbmode 0 (platform type 2, which makes the gestures) leaves UIStatusBar_Modern at 375 x 0 and hidden. Mode 2 is
 * mode 0 with the class method that sizes the bar answering 20 points (what mode 1 measured): +[UIStatusBar_Modern
 * _heightForStyle:orientation:forStatusBarFrame:inWindow:isAzulBLinked:].
 */
static double
bar_is_twenty(id self, SEL cmd, long style, long orientation, BOOL for_frame, id window, BOOL azul)
{
   return 20.0;
}

static void
fix_bar_height(void)
{
   Class bar = objc_getClass("UIStatusBar_Modern");
   SEL height = sel_registerName("_heightForStyle:orientation:forStatusBarFrame:inWindow:isAzulBLinked:");
   Method m = bar ? class_getClassMethod(bar, height) : NULL;
   if (m)
      method_setImplementation(m, (IMP)bar_is_twenty);
   herodrm_log("herosb: status bar height class method %s", m ? "answers 20" : "NOT found");
}

__attribute__((constructor)) static void
herosb_start(void)
{
   if (access(DROP_DIR "fps.off", F_OK) != 0) {
      raise_frame_rates();
      dispatch_after_f(dispatch_time(DISPATCH_TIME_NOW, 120 * NSEC_PER_SEC), dispatch_get_main_queue(), NULL, report_ranges);
   }
   /*
    * min125 (E-0346): in SpringBoard the status bar was found with height 0 and hidden (UIStatusBar_Modern 375 x 0) after the platform was told
    * home-button-type 2, although the Phone provider class exists in this iOS. DROP_DIR sbmode, one character, chooses how the gestures are asked for:
    *   0 (or no file): the platform says type 2 and the status bar providers are hooked (as before);
    *   1: only SBHomeGestureSettings isHomeGestureEnabled says yes; the platform keeps saying home button (type 1), whose status bar is the one that
    *      showed in min100-min117, and no provider is touched.
    * What the bar looks like in each mode is in the round 6 and 20 lines of the log.
    */
   if (access(DROP_DIR "gestures.off", F_OK) != 0) {
      char mode = '0';
      FILE *mf = fopen(DROP_DIR "sbmode", "r");
      if (mf) {
         int c = fgetc(mf);
         if (c == '0' || c == '1' || c == '2')
            mode = (char)c;
         fclose(mf);
      }
      herodrm_log("herosb: sbmode %c", mode);
      if (mode == '1') {
         Class settings = objc_getClass("SBHomeGestureSettings");
         Method enabled = settings ? class_getInstanceMethod(settings, sel_registerName("isHomeGestureEnabled")) : NULL;
         if (enabled) {
            method_setImplementation(enabled, (IMP)says_yes);
            gestures_on = true;
         }
      } else {
         ask_for_gestures();
         if (mode == '2')
            fix_bar_height();
      }
   }
   if (access(DROP_DIR "wallpaper.off", F_OK) == 0)
      return;
   dispatch_after_f(dispatch_time(DISPATCH_TIME_NOW, 10 * NSEC_PER_SEC), dispatch_get_main_queue(), NULL, look_at_windows);
}

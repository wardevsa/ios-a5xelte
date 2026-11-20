/*
 * The Metal plug-in of the S7 port (docs/herolte-metal.md, M3): the bundle Metal.framework loads for the kernel's
 * IOAcceleratorES (patch 9198: MetalPluginName HeroMetal, MetalPluginClassName HeroMetalDevice), installed by hero-run
 * as /System/Library/Extensions/HeroMetal.bundle.
 *
 * It is light on purpose: every process that asks Metal for a device loads it, and the driver behind it (Scion's
 * libhakiosmetal, ios-b1lte's Panfrost version, over libhakiosair -- Mesa) is about 10 MB. Only the processes named in
 * /private/var/herolte/metal.allow (one name a line, read once) get a device; they load the driver then and are handed
 * its HakiosMetalDevice. Everybody else gets nil, which is what Metal answered before this plug-in existed: the window
 * server and SpringBoard stay on OpenGL (gpu/hakios-gl) until Metal is proven on this GPU.
 */
#import <Foundation/Foundation.h>
#include <IOKit/IOKitLib.h>
#include <dlfcn.h>
#include <objc/runtime.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#define DRIVER "/private/var/herolte/lib/libhakiosmetal.dylib"
#define ALLOW "/private/var/herolte/metal.allow"

static void
say(const char *fmt, ...)
{
	static void (*log)(const char *, ...);
	static int looked;
	char line[300];
	va_list ap;

	va_start(ap, fmt);
	vsnprintf(line, sizeof(line), fmt, ap);
	va_end(ap);
	if (!looked) {
		looked = 1;
		void *drm = dlopen("/private/var/herolte/lib/libdrm.2.dylib", RTLD_NOW);
		if (drm != NULL)
			log = (void (*)(const char *, ...))dlsym(drm, "herodrm_log");
	}
	if (log != NULL)
		log("hero-metal: %s", line);
	fprintf(stderr, "hero-metal: %s\n", line);
}

static bool
allowed(const char *me)
{
	FILE *f = fopen(ALLOW, "r");
	char line[128];
	bool ok = false;

	if (f == NULL || me == NULL)
		return false;
	while (!ok && fgets(line, sizeof(line), f) != NULL) {
		line[strcspn(line, "\r\n \t#")] = 0;
		ok = line[0] != 0 && strcmp(line, me) == 0;
	}
	fclose(f);
	return ok;
}

@interface HeroMetalDevice : NSObject
- (instancetype)initWithAcceleratorPort:(io_service_t)port;
@end

@implementation HeroMetalDevice
- (instancetype)initWithAcceleratorPort:(io_service_t)port
{
	const char *me = getprogname();

	if (!allowed(me)) {
		[self release];
		return nil;     /* no device, as before the plug-in */
	}
	say("%s (pid %d) asks for a device: the T880's", me, getpid());
	if (dlopen(DRIVER, RTLD_NOW) == NULL) {
		say("driver not loaded: %s", dlerror());
		[self release];
		return nil;
	}
	Class driver = objc_getClass("HakiosMetalDevice");
	id device = driver != Nil ? [[driver alloc] initWithAcceleratorPort:port] : nil;
	say("device %s", device != nil ? "made" : "NOT made");
	[self release];
	return device;
}
@end

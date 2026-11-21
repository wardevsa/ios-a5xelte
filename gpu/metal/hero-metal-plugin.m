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

/*
 * A subclass of Metal's private _MTLDevice, because Metal checks the plug-in class with isSubclassOfClass: before it
 * sends it anything (ios-b1lte B1L-0044; boot-18k46: an NSObject subclass was passed over without a call). Only the name
 * is declared; the class comes from Metal.framework at link time, as for Scion's HakiosMetalDevice.
 *
 * The object Metal allocated is never initialised by _MTLDevice and never released: -[_MTLDevice dealloc] on such an
 * object crashed SpringBoard (ios-b1lte B1L-0085..0087). One leaked allocation a process that asks.
 */
@interface _MTLDevice : NSObject
@end

@interface HeroMetalDevice : _MTLDevice
- (instancetype)initWithAcceleratorPort:(io_service_t)port;
@end

@implementation HeroMetalDevice
- (instancetype)initWithAcceleratorPort:(io_service_t)port
{
	const char *me = getprogname();

	if (!allowed(me))
		return nil;     /* no device, as before the plug-in */
	say("%s (pid %d) asks for a device: the T880's", me, getpid());
	if (dlopen(DRIVER, RTLD_NOW) == NULL) {
		say("driver not loaded: %s", dlerror());
		return nil;
	}
	Class driver = objc_getClass("HakiosMetalDevice");
	id device = driver != Nil ? [[driver alloc] initWithAcceleratorPort:port] : nil;
	say("device %s", device != nil ? "made" : "NOT made");
	return device;
}

/* iOS 26's Metal sends this one (ios-b1lte B1L-0044); the class it names is ours either way */
- (instancetype)initWithAcceleratorPort:(io_service_t)port deviceClass:(Class)cls
{
	(void)cls;
	return [self initWithAcceleratorPort:port];
}
@end

/* Seen in the log once per process that loads the bundle, allowed or not: whether Metal got this far. */
__attribute__((constructor)) static void
loaded(void)
{
	if (allowed(getprogname()))
		say("bundle loaded in %s (pid %d)", getprogname(), getpid());
}

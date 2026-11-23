// SPDX-License-Identifier: BSD-2-Clause
// Galaxy S7 port, iOS 26 (23G90, iPhone12,1 cache): CoreAnimation's render server (backboardd) on OpenGL ES over our EAGL bridge
// (eagl.c over Panfrost on the Mali-T880). After malthiscode/ios-b1lte userspace/b2l_accel_gles.c (B1L-0032..0042, BSD-2-Clause),
// with the addresses of this cache: its QuartzCore lies 0x4000 below the iPhone17,2 cache's that b1lte patched (same code).
//
// iOS 26 removed the server that made an EAGLContext. CA::WindowServer::AccelServer::renderer() calls CAMetalContextCreate()
// and, with no Metal device, gives up (cbz x0) instead of falling back. Its success path is generic: it takes the OGL::Context
// that new_metal_context() returns and builds the Renderer around it. So, in backboardd only:
//   1. renderer()'s cbz becomes a nop and its bl CAMetalContextCreate a mov x0, #0 (no Metal probe);
//   2. new_metal_context() jumps to herolte_gles_context(), which makes an EAGLContext of API 3 (eagl.c answers it) and returns
//      QuartzCore's own GLESContext from gles_new_context() ({ u32 type = 3; void *eagl }).
//   3. Context::push_surface()'s "found != slist->end ()" assertion: GLESContext::make_buffer_current() makes the display
//      surface without tracking it; the not-found branch goes on (tools/ios18/dsc_patch.py already does it in the cache;
//      here only when the word is still the original).
// Every patched word is compared with this cache's first; any mismatch and nothing is written. If no GLES renderer is made
// within 120 s, or backboardd crashes once the patches are in, a marker for this boot keeps the next backboardd on the
// software renderer (the kernel's herogl also gives up after two deaths). BGL_CA_HOOK=0 turns it off.
#include <dlfcn.h>
#include <fcntl.h>
#include <libkern/OSCacheControl.h>
#include <mach-o/dyld.h>
#include <mach/mach.h>
#include <objc/message.h>
#include <objc/runtime.h>
#include <pthread.h>
#include <signal.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/sysctl.h>
#include <sys/time.h>
#include <unistd.h>

void hakios_gl_set_ca_context(void *context);   /* eagl.c reads the function of each draw from it */
extern const void *_dyld_get_shared_cache_range(size_t *length);

#define MARKER                  "/private/var/tmp/herolte-gl-fallback"
#define CACHE_BASE              0x180000000UL
#define A_RENDERER_CBZ          0x183f37df0UL   /* AccelServer::renderer() 0x183f37dc0 + 0x30: cbz x0 */
#define W_RENDERER_CBZ          0xb4000a20u
#define A_RENDERER_BL_METAL     0x183f37de8UL   /* bl CAMetalContextCreate (0x184215998) */
#define W_RENDERER_BL_METAL     0x940b76ecu
#define W_MOV_X0_0              0xd2800000u
#define A_NEW_METAL_CONTEXT     0x1841560c0UL   /* CA::OGL::new_metal_context(...) */
#define A_GLES_NEW_CONTEXT      0x184105d38UL   /* static gles_new_context(void *, void *, unsigned) */
#define W_GLES_NEW_CONTEXT      0xb9400008u     /* ldr w8, [x0] */
#define A_PUSH_NOTFOUND         0x183f0f1e4UL   /* cbnz x8, +0x3c in Context::push_surface */
#define W_PUSH_NOTFOUND         0xb50001e8u
#define W_PUSH_GO_ON            0x1400000fu     /* b +0x3c */
static const uint32_t w_new_metal[4] = { 0xd503237f, 0xa9ba6ffc, 0xa90167fa, 0xa9025ff8 };

static uintptr_t slide;
static char session[64];
static volatile int made_ok;
static unsigned made;

static void
say(const char *format, ...) __attribute__((format(printf, 1, 2)));

static void
say(const char *format, ...)
{
	char line[300];
	va_list ap;
	int n;

	va_start(ap, format);
	n = vsnprintf(line, sizeof(line), format, ap);
	va_end(ap);
	if (n > (int)sizeof(line) - 1) {
		n = sizeof(line) - 1;
	}
	write(2, line, (size_t)n);              /* the kernel sends backboardd's stderr to its log (herogl) */
}

static void
mark_and_stop(const char *why)
{
	int fd = open(MARKER, O_WRONLY | O_CREAT | O_TRUNC, 0644);

	if (fd >= 0) {
		(void)write(fd, session, strlen(session));
		close(fd);
	}
	say("ca_server_hook26: %s: software renderer for the rest of this boot (marker %d)\n", why, fd >= 0);
	abort();
}

static void *
watchdog(void *unused)
{
	(void)unused;
	for (int i = 0; i < 1200 && !made_ok; i++) {
		usleep(100000);
	}
	if (!made_ok) {
		mark_and_stop("no GLES renderer 120 s after backboardd started");
	}
	return NULL;
}

/* async-signal-safe: a crash once the patches are in marks this boot, the next backboardd stays on the software renderer */
static void
crash_mark(int sig)
{
	int fd = open(MARKER, O_WRONLY | O_CREAT | O_TRUNC, 0644);

	if (fd >= 0) {
		(void)write(fd, session, strlen(session));
		close(fd);
	}
	signal(sig, SIG_DFL);
	raise(sig);
}

/* Replaces CA::OGL::new_metal_context(): its arguments are ignored (the device is nil here). */
static void *
herolte_gles_context(void)
{
	Class eagl = objc_getClass("EAGLContext");
	id context = nil;

	if (eagl != Nil) {
		id a = ((id (*)(Class, SEL))objc_msgSend)(eagl, sel_registerName("alloc"));
		context = ((id (*)(id, SEL, unsigned long))objc_msgSend)(a, sel_registerName("initWithAPI:"), 3);
	}
	if (context == nil) {
		mark_and_stop("-[EAGLContext initWithAPI:3] failed");
		return NULL;
	}
	((signed char (*)(id, SEL, id))objc_msgSend)((id)eagl, sel_registerName("setCurrentContext:"), context);
	struct { uint32_t type, pad; void *eagl; } desc = { 3, 0, (void *)context };
	void *(*make)(void *, void *, unsigned) = (void *(*)(void *, void *, unsigned))(A_GLES_NEW_CONTEXT + slide);
	void *gles = make(&desc, NULL, 0);
	if (gles == NULL) {
		mark_and_stop("gles_new_context returned NULL");
		return NULL;
	}
	hakios_gl_set_ca_context(gles);
	made_ok = 1;
	made++;
	say("ca_server_hook26: window server renderer #%u: GLESContext %p over EAGLContext %p\n", made, gles, (void *)context);
	return gles;
}

static int
write_code(uintptr_t at, const void *bytes, size_t n)
{
	vm_address_t page = at & ~(vm_address_t)(vm_page_size - 1);
	vm_size_t len = ((at + n + vm_page_size - 1) & ~(uintptr_t)(vm_page_size - 1)) - page;
	kern_return_t kr = vm_protect(mach_task_self(), page, len, FALSE, VM_PROT_READ | VM_PROT_WRITE | VM_PROT_COPY);

	if (kr != KERN_SUCCESS) {
		return (int)kr;
	}
	memcpy((void *)at, bytes, n);
	kr = vm_protect(mach_task_self(), page, len, FALSE, VM_PROT_READ | VM_PROT_EXECUTE);
	sys_icache_invalidate((void *)at, n);
	return (int)kr;
}

static void
install(intptr_t image_slide)
{
	size_t length = 0;
	const char *setting = getenv("BGL_CA_HOOK");
	struct timeval bt = { 0, 0 };
	size_t bl = sizeof(bt);
	char seen[64] = "";
	int fd;

	if (setting != NULL && strcmp(setting, "0") == 0) {
		say("ca_server_hook26: off (BGL_CA_HOOK=0)\n");
		return;
	}
	if (sysctlbyname("kern.boottime", &bt, &bl, NULL, 0) == 0) {
		snprintf(session, sizeof(session), "%ld.%06d", (long)bt.tv_sec, (int)bt.tv_usec);
	}
	if ((fd = open(MARKER, O_RDONLY)) >= 0) {
		ssize_t n = read(fd, seen, sizeof(seen) - 1);
		close(fd);
		if (n > 0) {
			seen[n] = 0;
		}
	}
	if (session[0] && strcmp(seen, session) == 0) {
		say("ca_server_hook26: GLES failed earlier this boot: software renderer\n");
		return;
	}
	/* boot 26k7: nothing was printed past this point, so _dyld_get_shared_cache_range() gave NULL on this system; dyld's
	 * image callback passes the slide of QuartzCore, which for an image of the shared cache is the cache's slide */
	const void *cache = _dyld_get_shared_cache_range(&length);
	slide = cache != NULL ? (uintptr_t)cache - CACHE_BASE : (uintptr_t)image_slide;
	say("ca_server_hook26: backboardd, cache %p, image slide %#lx: slide %#lx\n", cache, (unsigned long)image_slide,
	    (unsigned long)slide);
	const uint32_t *cbz = (const uint32_t *)(A_RENDERER_CBZ + slide);
	const uint32_t *nmc = (const uint32_t *)(A_NEW_METAL_CONTEXT + slide);
	const uint32_t *gnc = (const uint32_t *)(A_GLES_NEW_CONTEXT + slide);
	const uint32_t *blm = (const uint32_t *)(A_RENDERER_BL_METAL + slide);
	/* Renegade's PAC rewrite turns pacibsp into a nop: the first word of new_metal_context may be either */
	bool first_ok = nmc[0] == w_new_metal[0] || nmc[0] == 0xd503201fu;
	if (*cbz != W_RENDERER_CBZ || *gnc != W_GLES_NEW_CONTEXT || !first_ok || *blm != W_RENDERER_BL_METAL ||
	    memcmp(nmc + 1, w_new_metal + 1, sizeof(w_new_metal) - sizeof(w_new_metal[0])) != 0) {
		say("ca_server_hook26: QuartzCore is not this 23G90 cache's (cbz %08x, gles %08x, metal %08x %08x, bl %08x): "
		    "nothing patched\n", *cbz, *gnc, nmc[0], nmc[1], *blm);
		return;
	}
	/* ldr x16, #8 ; br x16 ; .quad herolte_gles_context */
	struct { uint32_t ldr, br; uint64_t target; } __attribute__((packed)) jump = {
		0x58000050u, 0xd61f0200u, (uint64_t)(uintptr_t)herolte_gles_context
	};
	static const uint32_t nop = 0xd503201fu, mov0 = W_MOV_X0_0, go_on = W_PUSH_GO_ON;
	int e1 = write_code((uintptr_t)nmc, &jump, sizeof(jump));
	int e2 = e1 ? -1 : write_code((uintptr_t)cbz, &nop, sizeof(nop));
	int e3 = e2 ? -1 : write_code((uintptr_t)blm, &mov0, sizeof(mov0));
	const uint32_t *ps = (const uint32_t *)(A_PUSH_NOTFOUND + slide);
	int e4 = *ps == W_PUSH_GO_ON ? 0 : *ps == W_PUSH_NOTFOUND ? write_code((uintptr_t)ps, &go_on, sizeof(go_on)) : -2;
	if (!e1 && !e2 && !e3) {
		pthread_t t;
		static const int sigs[] = { SIGABRT, SIGSEGV, SIGBUS, SIGILL, SIGTRAP };

		if (pthread_create(&t, NULL, watchdog, NULL) == 0) {
			pthread_detach(t);
		}
		for (unsigned i = 0; i < sizeof(sigs) / sizeof(sigs[0]); i++) {
			signal(sigs[i], crash_mark);
		}
	}
	say("ca_server_hook26: AccelServer on OpenGL ES: new_metal_context %d, cbz %d, no Metal probe %d, push_surface %d "
	    "(slide %#lx)\n", e1, e2, e3, e4, (unsigned long)slide);
}

static void
on_image(const struct mach_header *mh, intptr_t image_slide)
{
	static int done;
	Dl_info di;

	if (done || !dladdr(mh, &di) || di.dli_fname == NULL || strstr(di.dli_fname, "/QuartzCore.framework/QuartzCore") == NULL) {
		return;
	}
	done = 1;
	if (strcmp(getprogname(), "backboardd") == 0) {
		install(image_slide);
	}
}

__attribute__((constructor)) static void
ca_server_hook26_init(void)
{
	_dyld_register_func_for_add_image(on_image);
}

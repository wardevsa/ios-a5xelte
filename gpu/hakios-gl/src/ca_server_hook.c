// SPDX-License-Identifier: MIT
// Galaxy S7 port, iOS 18: make CoreAnimation's render server (backboardd) draw with its OpenGL ES renderer on our EAGL bridge
// (eagl.c over Panfrost). From Bergamota's gpu/eagl/src/ca_server_hook.m (ry-diffusion/Bergamota, MIT), for the same QuartzCore
// (22H352), written in C and on by default here.
//
// iOS 18's render server asks for its renderer through a C++ virtual, slot 49 (+0x188) of the two server classes
// (CA::WindowServer::AccelServer::renderer() and its sibling). The only implementation builds a CA::OGL::MetalContext when there is an
// MTLDevice and otherwise returns NULL: every frame then goes to the CPU software renderer (backboardd at 250-400 % on the S7,
// boot-18k16g/18k17g). iOS 16 still had a server that made an EAGLContext; iOS 18 has none, and CA_ENABLE_OGL is read and thrown
// away. CA::OGL::GLESContext (constructor 0x1848f968c, an object of 2232 bytes taking an EAGLContext) is still there and implements the
// same interface. The hook wraps slot 49: when the original returns NULL it builds what the Metal path builds -- the context and the
// renderer object of 104 bytes around it -- with a GLES context on an EAGLContext of API 3, which eagl.c answers.
//
// Every address is an unslid address of QuartzCore 22H352 and every function is checked by its first instruction word before
// anything is touched (the PACIBSP hint stays after Renegade's PAC rewrite). Any doubt leaves the original behaviour.
// BGL_CA_HOOK=0 in the environment (gl.env) turns it off.
#include <dispatch/dispatch.h>
#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach/mach.h>
#include <malloc/malloc.h>
#include <objc/message.h>
#include <objc/runtime.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define QC_BASE 0x18470f000ull
#define A(x) ((void *)(qc_base + ((x) - QC_BASE)))

static const struct {
	uint64_t addr;
	uint32_t first;
	const char *what;
} SIG[] = {
	{ 0x1848f968c, 0xd503237f, "CA::OGL::GLESContext ctor" },
	{ 0x184a33b0c, 0xd503237f, "CARenderer init (caller of the ctor)" },
	{ 0x18476d7c4, 0xd503237f, "server renderer() class A" },
	{ 0x1848c4908, 0xd503237f, "server renderer() class B" },
	{ 0x18488ef40, 0xf9405008, "context flags update" },
};
#define SLOT_A        0x1ef97ce70ull   /* vtable slot 49 of class A (original -> 0x18476d7c4) */
#define SLOT_B        0x1ef97e908ull   /* vtable slot 49 of class B (original -> 0x1848c4908) */
#define FN_A          0x18476d7c4ull
#define FN_B          0x1848c4908ull
#define FN_GLES_CTOR  0x1848f968cull   /* void *ctor(void *obj, EAGLContext *) */
#define FN_FLAGS_UPD  0x18488ef40ull   /* void f(ctx), when the 0x2000200 flag bits changed */
#define G_DWORD_FLAGS 0x1eb38328cull
#define G_ZONE_ONCE   0x1ed834c88ull   /* dispatch_once predicate of CoreAnimation's malloc zone */
#define FN_ZONE_INIT  0x1847f84c8ull
#define G_ZONE        0x1ed836630ull   /* CoreAnimation's malloc zone */

void hakios_gl_set_ca_context(void *context);   /* eagl.c */

static uintptr_t qc_base;
static void *(*orig_a)(char *), *(*orig_b)(char *);
static id g_ctx;

static void
say(const char *format, ...) __attribute__((format(printf, 1, 2)));

static void
say(const char *format, ...)
{
	char line[256];
	va_list ap;
	int n;

	va_start(ap, format);
	n = vsnprintf(line, sizeof(line), format, ap);
	va_end(ap);
	if (n > (int)sizeof(line) - 1) {
		n = sizeof(line) - 1;
	}
	write(2, line, (size_t)n);
}

static void *
zone_calloc(size_t n)
{
	static void *(*zc)(malloc_zone_t *, size_t, size_t, unsigned long long);
	long *pred = A(G_ZONE_ONCE);
	malloc_zone_t *z;

	if (zc == NULL) {
		zc = dlsym(RTLD_DEFAULT, "malloc_type_zone_calloc");
	}
	if (*pred != -1) {
		dispatch_once_f((dispatch_once_t *)pred, NULL, (dispatch_function_t)A(FN_ZONE_INIT));
	}
	z = *(malloc_zone_t **)A(G_ZONE);
	if (zc != NULL && z != NULL) {
		return zc(z, 1, n, 3740020753ull);
	}
	return calloc(1, n);
}

static id
shim_context(void)
{
	Class c;
	id o;

	if (g_ctx != nil) {
		return g_ctx;
	}
	if ((c = objc_getClass("EAGLContext")) == Nil) {
		say("ca_server_hook: no EAGLContext class in this process\n");
		return nil;
	}
	o = ((id (*)(id, SEL))objc_msgSend)((id)c, sel_registerName("alloc"));
	o = ((id (*)(id, SEL, unsigned long))objc_msgSend)(o, sel_registerName("initWithAPI:"), 3);
	if (o == nil) {
		say("ca_server_hook: -[EAGLContext initWithAPI:3] gave nil\n");
		return nil;
	}
	g_ctx = o;
	return o;
}

/* The body of the Metal implementation after the device exists, with a GLES context in place of the Metal one.
 * off_ctx/off_ren: where the server keeps the context and the renderer (class A: 1024/1032, class B: 696/704). */
static void *
make_gl_renderer(char *srv, int off_ctx, int off_ren, uint32_t flags_or, int use_753)
{
	char *shared = *(char **)(srv + 96);
	id ec = shim_context();
	char *ctx, *wrap;
	void *scratch;
	uint32_t v10, old;

	if (ec == nil) {
		return NULL;
	}
	((signed char (*)(id, SEL, id))objc_msgSend)((id)objc_getClass("EAGLContext"), sel_registerName("setCurrentContext:"), ec);
	if ((ctx = zone_calloc(2232)) == NULL) {
		return NULL;
	}
	((void *(*)(void *, id))A(FN_GLES_CTOR))(ctx, ec);
	hakios_gl_set_ca_context(ctx);          /* eagl.c reads the function of each draw from it */
	wrap = zone_calloc(104);
	scratch = malloc(0x40000);
	if (wrap == NULL || scratch == NULL) {
		return NULL;
	}
	*(void **)wrap = ctx;
	*(void **)(wrap + 48) = scratch;
	*(int *)(wrap + 96) = 1;
	*(void **)(srv + off_ctx) = ctx;
	*(void **)(srv + off_ren) = wrap;
	*(void **)(shared + 312) = wrap;
	/* the context's flags, as the original's tail sets them */
	if (use_753) {
		v10 = ((*(uint32_t *)(shared + 753) & 0x4000) ? 33685520u : 131088u) | *(uint32_t *)(srv + 184);
	} else {
		v10 = *(uint32_t *)(srv + 184) | flags_or;
	}
	old = *(uint32_t *)(ctx + 224);
	*(uint32_t *)(ctx + 224) = v10;
	*(uint32_t *)(ctx + 432) = *(uint32_t *)A(G_DWORD_FLAGS) | v10;
	/* class A compares with the new value, class B with the server's own flag word (as the originals do) */
	if (((old ^ (use_753 ? v10 : *(uint32_t *)(srv + 184))) & 0x2000200) != 0) {
		((void (*)(void *))A(FN_FLAGS_UPD))(ctx);
	}
	say("ca_server_hook: GLES renderer %p (context %p) in server %p\n", (void *)wrap, (void *)ctx, (void *)srv);
	return wrap;
}

static void *
hook_a(char *srv)
{
	static int said;
	void *r = orig_a(srv);

	if (r != NULL) {
		return r;
	}
	if (!said++) {
		say("ca_server_hook: class A renderer() is NULL (no Metal device): building GLES\n");
	}
	return make_gl_renderer(srv, 1024, 1032, 0, 1);
}

static void *
hook_b(char *srv)
{
	static int said;
	void *r = orig_b(srv);

	if (r != NULL) {
		return r;
	}
	if (!said++) {
		say("ca_server_hook: class B renderer() is NULL (no Metal device): building GLES\n");
	}
	return make_gl_renderer(srv, 696, 704, 0x20010, 0);
}

static int
patch_slot(uint64_t slot_unslid, uint64_t expected_unslid, void *hook, void **orig)
{
	void **p = A(slot_unslid);
	vm_address_t page = (vm_address_t)p & ~(vm_address_t)(vm_page_size - 1);
	kern_return_t kr;

	/* the slot must hold the function checked above (the cache is slid; PAC is gone from these pointers on this CPU) */
	if (((uintptr_t)*p & 0x0000007fffffffffull) != (uintptr_t)A(expected_unslid)) {
		say("ca_server_hook: slot %#llx holds %p, not %p: left alone\n", slot_unslid, *p, A(expected_unslid));
		return 0;
	}
	kr = vm_protect(mach_task_self(), page, vm_page_size, FALSE, VM_PROT_READ | VM_PROT_WRITE | VM_PROT_COPY);
	if (kr != KERN_SUCCESS) {
		say("ca_server_hook: vm_protect %#lx failed (%d)\n", (unsigned long)page, kr);
		return 0;
	}
	*orig = A(expected_unslid);
	*p = hook;
	vm_protect(mach_task_self(), page, vm_page_size, FALSE, VM_PROT_READ);
	return 1;
}

static void
try_install(const struct mach_header *mh)
{
	static int done;
	const char *setting = getenv("BGL_CA_HOOK");
	Dl_info di;
	int a, b;

	if (done || !dladdr(mh, &di) || di.dli_fname == NULL || strstr(di.dli_fname, "/QuartzCore.framework/QuartzCore") == NULL) {
		return;
	}
	done = 1;
	qc_base = (uintptr_t)mh;
	if (strcmp(getprogname(), "backboardd") != 0) {
		return;
	}
	if (setting != NULL && strcmp(setting, "0") == 0) {
		say("ca_server_hook: off (BGL_CA_HOOK=0)\n");
		return;
	}
	if (qc_base - QC_BASE > 0x400000000ull) {
		say("ca_server_hook: QuartzCore at %p, not near %#llx: not this cache\n", (void *)mh, QC_BASE);
		return;
	}
	for (unsigned i = 0; i < sizeof(SIG) / sizeof(SIG[0]); i++) {
		uint32_t w = *(uint32_t *)A(SIG[i].addr);

		if (w != SIG[i].first) {
			say("ca_server_hook: QuartzCore is not 22H352's (%s: %08x): not hooking\n", SIG[i].what, w);
			return;
		}
	}
	a = patch_slot(SLOT_A, FN_A, (void *)hook_a, (void **)&orig_a);
	b = patch_slot(SLOT_B, FN_B, (void *)hook_b, (void **)&orig_b);
	say("ca_server_hook: QuartzCore %p: class A %s, class B %s\n", (void *)mh, a ? "hooked" : "NOT hooked",
	    b ? "hooked" : "NOT hooked");
}

static void
on_image(const struct mach_header *mh, intptr_t slide)
{
	(void)slide;
	try_install(mh);
}

__attribute__((constructor)) static void
ca_server_hook_init(void)
{
	_dyld_register_func_for_add_image(on_image);
}

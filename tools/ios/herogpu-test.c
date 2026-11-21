/*
 * herogpu-test: first user-space program on the S7's Mali-T880, through
 * the kernel's HeroGPU service (iokit/Kernel/arm/HeroGPU.cpp). Runs as
 * /private/var/herolte/autorun (tools/herolte-drop.py); its output goes to
 * the kernel log through HeroGPU's Log call (tools/herolte-log-pull.py).
 *
 *   1. GetParam: the Panfrost DRM params Mesa reads first.
 *   2. A WRITE_VALUE job in a buffer of ours, run on JS1.
 *   3. A fragment job that clears a 64x64 RGBA8 render target in a buffer
 *      of ours (multi-target framebuffer, tiler disabled, as the kernel's
 *      herogpu=6 test); every pixel is checked.
 *
 * The iOS SDK has no IOKitLib.h; the few calls used are declared here.
 */
#include <CoreFoundation/CoreFoundation.h>
#include <mach/mach.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

typedef mach_port_t io_object_t;
typedef io_object_t io_service_t;
typedef io_object_t io_connect_t;
CFMutableDictionaryRef IOServiceMatching(const char *name);
io_service_t IOServiceGetMatchingService(mach_port_t mainPort, CFDictionaryRef matching);
kern_return_t IOServiceOpen(io_service_t service, task_port_t owningTask, uint32_t type,
    io_connect_t *connect);
kern_return_t IOServiceClose(io_connect_t connect);
kern_return_t IOObjectRelease(io_object_t object);
kern_return_t IOConnectCallScalarMethod(io_connect_t connection, uint32_t selector,
    const uint64_t *input, uint32_t inputCnt, uint64_t *output, uint32_t *outputCnt);
kern_return_t IOConnectCallStructMethod(io_connect_t connection, uint32_t selector,
    const void *inputStruct, size_t inputStructCnt, void *outputStruct, size_t *outputStructCnt);

enum { GET_PARAM = 0, CREATE_BO = 1, FREE_BO = 2, MAP_BO = 3, SUBMIT = 4, LOG = 5 };

static io_connect_t gpu;

static void
say(const char *fmt, ...)
{
	char line[512];
	va_list ap;
	va_start(ap, fmt);
	int n = vsnprintf(line, sizeof(line), fmt, ap);
	va_end(ap);
	printf("%s\n", line);
	if (gpu != MACH_PORT_NULL && n > 0) {
		IOConnectCallStructMethod(gpu, LOG, line, (size_t)n < sizeof(line) ? (size_t)n : sizeof(line) - 1,
		    NULL, NULL);
	}
}

static kern_return_t
call(uint32_t sel, const uint64_t *in, uint32_t nin, uint64_t *out, uint32_t nout)
{
	uint32_t cnt = nout;
	return IOConnectCallScalarMethod(gpu, sel, in, nin, out, &cnt);
}

struct bo {
	uint64_t handle, va, size;
	volatile uint8_t *cpu;
};

static int
bo_new(struct bo *b, uint64_t size)
{
	uint64_t out[3] = { 0 }, map = 0;
	kern_return_t kr = call(CREATE_BO, &size, 1, out, 3);
	if (kr != KERN_SUCCESS) {
		say("CreateBO(%llu) failed: 0x%x", size, kr);
		return -1;
	}
	b->handle = out[0];
	b->va = out[1];
	b->size = out[2];
	kr = call(MAP_BO, &b->handle, 1, &map, 1);
	if (kr != KERN_SUCCESS || map == 0) {
		say("MapBO(%llu) failed: 0x%x", b->handle, kr);
		return -1;
	}
	b->cpu = (volatile uint8_t *)(uintptr_t)map;
	say("BO %llu: %llu bytes, GPU VA 0x%llx, CPU %p", b->handle, b->size, b->va, (void *)map);
	return 0;
}

static uint32_t
submit(uint64_t jc, unsigned js, uint64_t *us)
{
	uint64_t in[2] = { jc, js }, out[2] = { ~0ull, 0 };
	kern_return_t kr = call(SUBMIT, in, 2, out, 2);
	*us = out[1];
	return kr == KERN_SUCCESS ? (uint32_t)out[0] : 0xdead0000u | (kr & 0xffff);
}

static void
wr32(volatile uint8_t *p, uint32_t off, uint32_t v)
{
	*(volatile uint32_t *)(p + off) = v;
}

static void
wr64(volatile uint8_t *p, uint32_t off, uint64_t v)
{
	*(volatile uint64_t *)(p + off) = v;
}

int
main(void)
{
	/* Let the GPU present path and the UI come up first. */
	sleep(20);
	io_service_t svc = IOServiceGetMatchingService(MACH_PORT_NULL, IOServiceMatching("HeroGPU"));
	if (svc == MACH_PORT_NULL) {
		printf("no HeroGPU service\n");
		return 1;
	}
	kern_return_t kr = IOServiceOpen(svc, mach_task_self(), 0, &gpu);
	IOObjectRelease(svc);
	if (kr != KERN_SUCCESS) {
		printf("IOServiceOpen: 0x%x\n", kr);
		return 1;
	}
	say("hello from user space, pid %d", getpid());

	/* 1. The params Mesa's panfrost_kmod reads first. */
	static const struct { uint64_t id; const char *name; } params[] = {
		{ 0, "GPU_PROD_ID" }, { 1, "GPU_REVISION" }, { 2, "SHADER_PRESENT" },
		{ 3, "TILER_PRESENT" }, { 6, "AS_PRESENT" }, { 7, "JS_PRESENT" },
		{ 9, "CORE_FEATURES" }, { 10, "TILER_FEATURES" }, { 11, "MEM_FEATURES" },
		{ 12, "MMU_FEATURES" }, { 13, "THREAD_FEATURES" }, { 14, "MAX_THREADS" },
		{ 18, "TEXTURE_FEATURES0" }, { 22, "JS_FEATURES0" },
	};
	for (unsigned i = 0; i < sizeof(params) / sizeof(params[0]); i++) {
		uint64_t v = 0;
		call(GET_PARAM, &params[i].id, 1, &v, 1);
		say("param %s = 0x%llx", params[i].name, v);
	}

	/* 2. WRITE_VALUE: zero 64 bits over a canary. */
	struct bo job, rt;
	if (bo_new(&job, 0x10000) || bo_new(&rt, 64 * 64 * 4)) {
		return 1;
	}
	wr32(job.cpu, 16, 1 | (2 << 1) | (1u << 16));  /* 64-bit, WRITE_VALUE, index 1 */
	wr64(job.cpu, 32, job.va + 0x100);
	wr64(job.cpu, 40, 3);                           /* zero 64 bits */
	wr64(job.cpu, 0x100, 0xa5a5a5a55a5a5a5aull);
	__asm__ volatile ("dsb sy" ::: "memory");
	uint64_t us = 0;
	uint32_t st = submit(job.va, 1, &us);
	uint64_t v = *(volatile uint64_t *)(job.cpu + 0x100);
	say("WRITE_VALUE: status 0x%x, %llu us, output 0x%llx -> %s", st, us, v,
	    st == 0 && v == 0 ? "OK" : "FAILED");

	/* 3. Fragment clear of the 64x64 target: job at +0x1000, framebuffer at
	 * +0x2000 (Mesa v5 MFBD), its empty polygon list at +0x3000. */
	memset((void *)job.cpu, 0, 0x4000);
	for (unsigned i = 0; i < 64 * 64; i++) {
		wr32(rt.cpu, i * 4, 0x12345678);
	}
	uint32_t w = 64, h = 64, color = 0xff20c0ff;
	uint64_t fb = job.va + 0x2000, poly = job.va + 0x3000;
	volatile uint8_t *j = job.cpu + 0x1000, *f = job.cpu + 0x2000;
	wr32(j, 16, 0x00010013);                        /* 64-bit, FRAGMENT, index 1 */
	wr32(j, 32, 0);
	wr32(j, 36, (((h + 15) / 16 - 1) << 16) | ((w + 15) / 16 - 1));
	wr64(j, 40, fb | 1);                            /* MFBD, 1 render target */
	wr32(f, 4, 31);                                 /* no workgroup memory */
	wr32(f, 32, ((h - 1) << 16) | (w - 1));
	wr32(f, 40, ((h - 1) << 16) | (w - 1));
	wr32(f, 44, (2u << 6) | (8u << 9) | (1u << 24));
	wr32(f, 48, 1u << 16);
	wr32(f, 56, 512);                               /* tiler disabled (Mesa) */
	wr32(f, 60, 4096);
	wr64(f, 64, poly);
	wr64(f, 72, poly + 512);
	wr64(f, 80, poly);
	wr64(f, 88, poly);
	wr32(f, 128 + 0, 1u << 26);                     /* RT: R8G8B8A8 */
	wr32(f, 128 + 4, 1u | (19u << 3) | (2u << 10) | (1u << 15) | (0x688u << 16) | (1u << 31));
	wr64(f, 128 + 32, rt.va);
	wr32(f, 128 + 40, w * 4);
	for (unsigned i = 0; i < 4; i++) {
		wr32(f, 128 + 48 + i * 4, color);
	}
	__asm__ volatile ("dsb sy" ::: "memory");
	st = submit(job.va + 0x1000, 0, &us);
	unsigned good = 0;
	for (unsigned i = 0; i < w * h; i++) {
		good += *(volatile uint32_t *)(rt.cpu + i * 4) == color;
	}
	say("FRAGMENT clear 64x64: status 0x%x, %llu us, %u/%u pixels 0x%08x (first 0x%08x) -> %s",
	    st, us, good, w * h, color, *(volatile uint32_t *)rt.cpu,
	    st == 0 && good == w * h ? "OK" : "FAILED");

	uint64_t hnd = job.handle;
	call(FREE_BO, &hnd, 1, NULL, 0);
	hnd = rt.handle;
	call(FREE_BO, &hnd, 1, NULL, 0);
	say("done");
	IOServiceClose(gpu);
	return 0;
}

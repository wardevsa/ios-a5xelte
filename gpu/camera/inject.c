/*
 * Note FE: libnotefecam.dylib's hooks in mediaserverd, after danstronics/ios-s9plus-exynos
 * core/userland/src/inject_media.c (MIT, LICENSE.HakiOS beside this file): the camera part only.
 *
 * +[BWFigCaptureDeviceVendor sharedCaptureDeviceVendor] answers nil on a phone without Apple's ISP; with
 * /dev/hakios-camera there (our kernel 0456, made by sysctl kern.notefe_cam=7) it answers a vendor made with
 * camera_device.c's create function instead, so Camera.app's capture session gets our front camera's frames.
 * Two more, as the S9 port found them needed: the portrait filter's prewarm (CoreImage on a Metal that is not
 * there) does nothing, and video stabilization is off. The S9's hooks check each method's address against their
 * iOS 16.5 (20F66) build; our image is not that build, so only the class and the method are checked here.
 * Loaded by libheroapp's constructor in mediaserverd only (gracerlte/heroapp/heroapp.c).
 */
#include <dlfcn.h>
#include <execinfo.h>
#include <libkern/OSCacheControl.h>
#include <mach/mach.h>
#include <stdint.h>
#include <mach-o/dyld.h>
#include <objc/message.h>
#include <objc/runtime.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

extern int hakios_camera_device_create(const void *allocator, const void *options, void **out);
extern void hakios_camera_say(const char *format, ...);
extern const char *getprogname(void);
extern const void *_dyld_get_shared_cache_range(size_t *length);
#define say hakios_camera_say

static IMP original_shared_vendor;

static id
shared_vendor(id self, SEL selector)
{
	id vendor = ((id (*)(id, SEL))original_shared_vendor)(self, selector);
	static id camera_vendor;
	static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
	if (vendor != NULL || access("/dev/hakios-camera", F_OK) != 0) {
		return vendor;
	}
	pthread_mutex_lock(&lock);
	if (camera_vendor == NULL) {
		id made = ((id (*)(Class, SEL))objc_msgSend)(objc_getClass("BWFigCaptureDeviceVendor"), sel_registerName("alloc"));
		camera_vendor = ((id (*)(id, SEL, void *))objc_msgSend)(made, sel_registerName("initWithDeviceCreateFunction:"),
		    (void *)hakios_camera_device_create);
		say("mediaserverd: the camera's device vendor %s", camera_vendor ? "made (camera_device.c)" : "CANNOT BE MADE");
	}
	pthread_mutex_unlock(&lock);
	return camera_vendor;
}

static void
prewarm_portrait_filter(__unused id self, __unused SEL selector, __unused int version, __unused BOOL styles)
{
}

static long
video_stabilization_method(__unused id self, __unused SEL selector)
{
	return 0;
}

/* the stabilization type the stack acts on is read straight from the connection configuration, not computed from the
 * method above: refused here too, or the graph asks for a VIS pipeline that needs Apple's ISP, gets nil, and the whole
 * graph (preview included) is torn down (S9: inject_media.c video_stabilization_type) */
static long
video_stabilization_type(__unused id self, __unused SEL selector)
{
	return 0;                       /* kFigCaptureVideoStabilizationType_None */
}

/* Camera.app's session has an audio input; with no capture audio its source node fails with 'nope' and the graph takes
 * that error for the whole session's (AVCaptureSessionRuntimeError, restart, for ever). That one error is swallowed: the
 * node "started" and gives no sound (S9: inject_media.c audio_source_start) */
#define ERROR_NO_SUCH_THING 1852797029  /* 'nope' */
static IMP original_audio_source_start;
static BOOL
audio_source_start(id self, SEL selector, id *error)
{
	BOOL started = ((BOOL (*)(id, SEL, id *))original_audio_source_start)(self, selector, error);
	id made = error != NULL ? *error : NULL;
	static bool said;
	if (started || made == NULL || ((long (*)(id, SEL))objc_msgSend)(made, sel_registerName("code")) != ERROR_NO_SUCH_THING) {
		return started;
	}
	*error = NULL;
	if (!said) {
		said = true;
		say("mediaserverd: no capture audio: the session's audio source gives nothing, the camera runs without it");
	}
	return true;
}

/* the silent audio source's output is given no sample buffer: not passed on (a NULL went through the graph and
 * mediaserverd died with SIGSEGV right after the first preview picture, cam-app10) (S9: emit_sample_buffer) */
static IMP original_emit_sample_buffer;
static void
emit_sample_buffer(id self, SEL selector, void *sample_buffer)
{
	static bool said;
	if (sample_buffer == NULL) {
		if (!said) {
			said = true;
			say("mediaserverd: a node's output was given no sample buffer (the silent audio source's): not passed on");
		}
		return;
	}
	((void (*)(id, SEL, void *))original_emit_sample_buffer)(self, selector, sample_buffer);
}

/* a photograph's noise reduction is the iPhone's ISP's and never hands the picture back: passed on as it came */
static void
gnr_render(id self, __unused SEL selector, void *sample_buffer, __unused id input)
{
	id output = ((id (*)(id, SEL))objc_msgSend)(self, sel_registerName("output"));
	if (output != nil) {
		((void (*)(id, SEL, void *))objc_msgSend)(output, sel_registerName("emitSampleBuffer:"), sample_buffer);
	}
}

/* a photograph's quality prioritization at most 1 (speed): one frame, no SIS bracket of four it has nothing to fuse */
static IMP original_quality_prioritization;
static long
quality_prioritization(id self, SEL selector)
{
	long asked = ((long (*)(id, SEL))original_quality_prioritization)(self, selector);
	return asked > 1 ? 1 : asked;
}

/* the live filter thumbnails' node reads through a NULL (Metal/CoreImage that is not here: SIGSEGV at 0x8 in
 * -[BWMultiFilterThumbnailNode prepareForCurrentConfigurationToBecomeLive]+0x128, cam-app11, right after the first
 * preview picture): left unprepared, so the filter thumbnails stay empty and the preview runs */
static void
thumbnail_prepare(__unused id self, __unused SEL selector)
{
	static bool said;
	if (!said) {
		said = true;
		say("mediaserverd: the filter thumbnails' node left unprepared (no Metal here)");
	}
}

/* cam-mem3/5: the silent audio source's -_generateSamples zero-fills sample buffers of ~820 MB each
 * (-_createSampleBufferForTimestampedAudioBufferList:audioBufferIndex: -> bzero) until jetsam kills mediaserverd
 * ("low swap: killing largest compressed process"): no samples generated (no microphone here anyway) */
static void
audio_generate_samples(__unused id self, __unused SEL selector)
{
	static bool said;
	if (!said) {
		said = true;
		say("mediaserverd: the silent audio source's generated samples skipped (they grew to ~820 MB buffers)");
	}
}

/* -[BWAudioSourceNode _generateSamples] is an objc_direct method (no runtime entry, "not there" to the swizzler,
 * cam-mem6): its first instruction is made a `ret` in this process's copy of the shared cache, at its 20H392 address,
 * only when the instruction there is the one expected (sub sp, sp, #0x110). */
#define GENERATE_SAMPLES_20H392 0x1a1ef39e4ull
static void
patch_generate_samples(uintptr_t slide)
{
	uint32_t *at = (uint32_t *)(uintptr_t)(GENERATE_SAMPLES_20H392 + slide);
	Dl_info di;
	if (!dladdr(at, &di) || di.dli_fname == NULL || strstr(di.dli_fname, "CMCapture") == NULL || *at != 0xd10443ffu) {
		say("mediaserverd: _generateSamples not where 20H392 has it (%s, %#x): left alone",
		    di.dli_fname ? di.dli_fname : "?", *at);
		return;
	}
	vm_address_t page = (vm_address_t)at & ~(vm_address_t)(vm_page_size - 1);
	kern_return_t kr = vm_protect(mach_task_self(), page, vm_page_size, false, VM_PROT_READ | VM_PROT_WRITE | VM_PROT_COPY);
	if (kr != KERN_SUCCESS) {
		say("mediaserverd: _generateSamples: page not writable (%d)", kr);
		return;
	}
	*at = 0xd65f03c0u;     /* ret */
	vm_protect(mach_task_self(), page, vm_page_size, false, VM_PROT_READ | VM_PROT_EXECUTE);
	sys_icache_invalidate(at, 4);
	say("mediaserverd: -[BWAudioSourceNode _generateSamples] patched to return (the silent audio source's ~820 MB buffers)");
}

static struct replacement {
	const char *class_name, *selector;
	IMP replacement, *original;
	bool instance, done;
} replacements[] = {
	{ "BWFigCaptureDeviceVendor", "sharedCaptureDeviceVendor", (IMP)shared_vendor, &original_shared_vendor, false, false },
	{ "BWCoreImageFilterRenderer", "prewarmPortraitFilterVersion:semanticStyleFilters:", (IMP)prewarm_portrait_filter,
	  NULL, false, false },
	{ "FigVideoCaptureConnectionConfiguration", "videoStabilizationMethod", (IMP)video_stabilization_method, NULL, true,
	  false },
	{ "FigVideoCaptureConnectionConfiguration", "videoStabilizationType", (IMP)video_stabilization_type, NULL, true, false },
	{ "BWAudioSourceNode", "start:", (IMP)audio_source_start, &original_audio_source_start, true, false },
	{ "BWAudioSourceNode", "_generateSamples", (IMP)audio_generate_samples, NULL, true, false },
	{ "BWNodeOutput", "emitSampleBuffer:", (IMP)emit_sample_buffer, &original_emit_sample_buffer, true, false },
	{ "BWGNRNode", "renderSampleBuffer:forInput:", (IMP)gnr_render, NULL, true, false },
	{ "BWMultiFilterThumbnailNode", "prepareForCurrentConfigurationToBecomeLive", (IMP)thumbnail_prepare, NULL, true, false },
	{ "FigCaptureStillImageSettings", "qualityPrioritization", (IMP)quality_prioritization, &original_quality_prioritization,
	  true, false },
};

static bool generate_patched;
static void
image_added(__unused const struct mach_header *header, __unused intptr_t slide)
{
	if (!generate_patched && objc_getClass("BWAudioSourceNode") != NULL) {
		size_t length = 0;
		const char *cache = (const char *)_dyld_get_shared_cache_range(&length);
		generate_patched = true;
		if (cache != NULL) {
			patch_generate_samples((uintptr_t)cache - 0x180000000ul);
		}
	}
	for (size_t i = 0; i < sizeof(replacements) / sizeof(replacements[0]); i++) {
		struct replacement *r = &replacements[i];
		Class cls;
		if (r->done || (cls = objc_getClass(r->class_name)) == NULL) {
			continue;
		}
		r->done = true;
		Method m = r->instance ? class_getInstanceMethod(cls, sel_registerName(r->selector)) :
		    class_getClassMethod(cls, sel_registerName(r->selector));
		if (m == NULL) {
			say("mediaserverd: %c[%s %s] not there; left alone", r->instance ? '-' : '+', r->class_name, r->selector);
			continue;
		}
		IMP was = method_setImplementation(m, r->replacement);
		if (r->original) {
			*r->original = was;
		}
		say("mediaserverd: %c[%s %s] replaced", r->instance ? '-' : '+', r->class_name, r->selector);
	}
}


/*
 * Note FE (cam-mem1): mediaserverd grows to ~850 MB within a second or two of the first preview picture, and it is not
 * the capture device's buffers (ten IOSurfaces). A tracer: malloc_logger / __syscall_logger (the stack logging hooks)
 * see every allocation; one of 4 MB or more is logged with its return addresses (40 at most, each caller once), and a
 * thread logs the footprint every 250 ms once it passes 100 MB.
 */
typedef void (malloc_logger_t)(uint32_t type, uintptr_t a1, uintptr_t a2, uintptr_t a3, uintptr_t result, uint32_t skip);
static __thread int in_tracer;
static int traced;
static uintptr_t traced_callers[64];
static void
big_allocation(uint32_t type, uintptr_t a1, uintptr_t a2, uintptr_t a3, uintptr_t result, uint32_t skip)
{
	(void)a1; (void)a3; (void)result; (void)skip;
	/* malloc: type & 2 (allocate) with a2 = size; realloc 6: a3 = size; vm_allocate: type & 0x10, a2 = size */
	uintptr_t size = (type & 4) ? a3 : a2;
	if (!(type & 0x12) || size < (4u << 20) || in_tracer || traced >= 40) {
		return;
	}
	in_tracer = 1;
	void *bt[12];
	int n = backtrace(bt, 12);
	uintptr_t key = n > 3 ? (uintptr_t)bt[3] ^ (uintptr_t)bt[4] : 0;
	int seen = 0;
	for (int i = 0; i < traced && i < 64; i++) {
		seen |= traced_callers[i] == key;
	}
	if (!seen) {
		traced_callers[traced++ % 64] = key;
		say("big allocation: type %#x size %lu MB: %p %p %p %p %p %p %p %p %p", type, (unsigned long)(size >> 20),
		    n > 2 ? bt[2] : 0, n > 3 ? bt[3] : 0, n > 4 ? bt[4] : 0, n > 5 ? bt[5] : 0, n > 6 ? bt[6] : 0,
		    n > 7 ? bt[7] : 0, n > 8 ? bt[8] : 0, n > 9 ? bt[9] : 0, n > 10 ? bt[10] : 0);
	}
	in_tracer = 0;
}

#define STRIP(p) ((uintptr_t)(p) & 0x0000000fffffffffull)
static void
sample_threads(void)
{
	thread_act_array_t th;
	mach_msg_type_number_t n;
	thread_t self = mach_thread_self();
	if (task_threads(mach_task_self(), &th, &n) != KERN_SUCCESS) {
		return;
	}
	uintptr_t pcs[64][10];
	int depth[64] = { 0 };
	unsigned count = n < 64 ? n : 64;
	for (unsigned i = 0; i < count; i++) {
		if (th[i] == self || thread_suspend(th[i]) != KERN_SUCCESS) {
			continue;
		}
		arm_thread_state64_t st;
		mach_msg_type_number_t c = ARM_THREAD_STATE64_COUNT;
		if (thread_get_state(th[i], ARM_THREAD_STATE64, (thread_state_t)&st, &c) == KERN_SUCCESS) {
			uintptr_t fp = STRIP(arm_thread_state64_get_fp(st));
			pcs[i][depth[i]++] = STRIP(arm_thread_state64_get_pc(st));
			pcs[i][depth[i]++] = STRIP(arm_thread_state64_get_lr(st));
			while (depth[i] < 10 && fp != 0 && (fp & 7) == 0) {
				uintptr_t *frame = (uintptr_t *)fp;
				uintptr_t next = STRIP(frame[0]), ret = STRIP(frame[1]);
				if (ret == 0 || next <= fp) {
					break;
				}
				pcs[i][depth[i]++] = ret;
				fp = next;
			}
		}
		thread_resume(th[i]);
	}
	for (unsigned i = 0; i < count; i++) {
		if (depth[i] < 2) {
			continue;
		}
		/* only the threads with a frame outside the shared cache (the cache's frames are symbolized on the Mac) */
		bool outside = false;
		for (int d = 0; d < depth[i]; d++) {
			outside |= pcs[i][d] > 0x100000 && pcs[i][d] < 0x180000000ull;
		}
		if (!outside) {
			continue;
		}
		char line[900];
		int o = snprintf(line, sizeof line, "thread %u:", i);
		for (int d = 0; d < depth[i] && o < (int)sizeof line - 80; d++) {
			Dl_info di;
			if (pcs[i][d] < 0x180000000ull && dladdr((void *)pcs[i][d], &di) && di.dli_fname) {
				const char *b = strrchr(di.dli_fname, '/');
				o += snprintf(line + o, sizeof line - o, " %s+%#lx(%s)", b ? b + 1 : di.dli_fname,
				    (unsigned long)(pcs[i][d] - (uintptr_t)di.dli_fbase), di.dli_sname ? di.dli_sname : "?");
			} else {
				o += snprintf(line + o, sizeof line - o, " %#lx", (unsigned long)pcs[i][d]);
			}
		}
		say("%s", line);
	}
	for (unsigned i = 0; i < n; i++) {
		mach_port_deallocate(mach_task_self(), th[i]);
	}
	vm_deallocate(mach_task_self(), (vm_address_t)th, n * sizeof(thread_t));
	mach_port_deallocate(mach_task_self(), self);
}

extern kern_return_t mach_vm_region(vm_map_t, mach_vm_address_t *, mach_vm_size_t *, vm_region_flavor_t, vm_region_info_t,
    mach_msg_type_number_t *, mach_port_t *);

/* the address space by VM tag: virtual and resident MB of the biggest five, and the biggest single region */
static void
tally_regions(void)
{
	static uint64_t virt[256], res[256];
	memset(virt, 0, sizeof virt);
	memset(res, 0, sizeof res);
	mach_vm_address_t a = 0, big_at = 0;
	mach_vm_size_t sz = 0, big = 0;
	unsigned big_tag = 0;
	for (int guard = 0; guard < 100000; guard++) {
		vm_region_extended_info_data_t info;
		mach_msg_type_number_t c = VM_REGION_EXTENDED_INFO_COUNT;
		mach_port_t obj;
		if (mach_vm_region(mach_task_self(), &a, &sz, VM_REGION_EXTENDED_INFO, (vm_region_info_t)&info, &c, &obj) != KERN_SUCCESS) {
			break;
		}
		unsigned tag = info.user_tag & 255;
		virt[tag] += sz;
		res[tag] += (uint64_t)info.pages_resident * vm_page_size;
		if (sz > big) {
			big = sz; big_at = a; big_tag = tag;
		}
		a += sz;
	}
	char line[300];
	int o = snprintf(line, sizeof line, "regions by tag (virtual/resident MB):");
	for (int k = 0; k < 6; k++) {
		int best = -1;
		for (int t = 0; t < 256; t++) {
			if (res[t] > 0 && (best < 0 || res[t] > res[best])) {
				best = t;
			}
		}
		if (best < 0) {
			break;
		}
		o += snprintf(line + o, sizeof line - o, " tag %d %llu/%llu;", best, (unsigned long long)(virt[best] >> 20),
		    (unsigned long long)(res[best] >> 20));
		res[best] = 0;
	}
	say("%s biggest %llu MB at %#llx tag %u", line, (unsigned long long)(big >> 20), (unsigned long long)big_at, big_tag);
}

static void *
footprint_watch(__unused void *arg)
{
	uint64_t last = 0;
	int samples = 0;
	for (;;) {
		task_vm_info_data_t vi;
		mach_msg_type_number_t cnt = TASK_VM_INFO_COUNT;
		usleep(250000);
		if (task_info(mach_task_self(), TASK_VM_INFO, (task_info_t)&vi, &cnt) != KERN_SUCCESS) {
			continue;
		}
		uint64_t mb = vi.phys_footprint >> 20;
		if (mb >= 100 && (mb > last + 40 || mb + 40 < last)) {
			say("footprint %llu MB (resident %llu MB, compressed %llu MB)", (unsigned long long)mb,
			    (unsigned long long)(vi.resident_size >> 20), (unsigned long long)(vi.compressed >> 20));
			if (mb > last && samples < 6) {
				samples++;
				tally_regions();
				sample_threads();
			}
			last = mb;
		}
	}
	return NULL;
}

static void
tracer_start(void)
{
	malloc_logger_t **ml = dlsym(RTLD_DEFAULT, "malloc_logger");
	malloc_logger_t **sl = dlsym(RTLD_DEFAULT, "__syscall_logger");
	(void)ml; (void)sl;     /* cam-mem2: the loggers slowed mediaserverd until Camera.app could not launch: not set */
	say("mediaserverd: footprint watch on (thread stacks sampled when it jumps)");
	pthread_t t;
	pthread_create(&t, NULL, footprint_watch, NULL);
	pthread_detach(t);
}

__attribute__((constructor))
static void
notefe_camera_init(void)
{
	const char *name = getprogname();
	if (name == NULL || strcmp(name, "mediaserverd") != 0) {
		return;
	}
	size_t length = 0;
	const char *cache = (const char *)_dyld_get_shared_cache_range(&length);
	say("mediaserverd: libnotefecam loaded; /dev/hakios-camera %s; shared cache slide %#lx (for symbolize.py)",
	    access("/dev/hakios-camera", F_OK) == 0 ? "there" : "not there yet", cache ? (unsigned long)cache - 0x180000000ul : 0);
	_dyld_register_func_for_add_image(image_added);
	tracer_start();

}

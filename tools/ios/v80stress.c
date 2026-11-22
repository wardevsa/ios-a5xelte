/*
 * v80stress - exercises the kernel's ARMv8.1+ emulation (v80emu) on the S7.
 *
 * The S7's cores are ARMv8.0, so every LSE / LRCPC / FlagM / PAuth
 * instruction below traps and is executed by herolte_v80emu.c. Each result is
 * compared with what the ARM ARM specifies, computed here in plain C:
 *
 *   1. single-thread semantics of every class and size
 *   2. atomicity: 8 threads mixing emulated LDADD/CAS/SWP/CASP with native
 *      LDAXR/STLXR on the same words (totals must be exact)
 *   3. page faults inside the emulation: zero-fill, copy-on-write after fork,
 *      and the signals for read-only, unmapped and misaligned addresses
 *   4. cost of an emulated instruction against the native LL/SC equivalent
 *   5. kern.v80emu counters before/after
 *
 * Built by the ios-tools workflow (plain arm64, iOS 16) and run by hero-run
 * from the drop zone (/private/var/herolte/test); stdout goes to the kernel
 * log, at most 400 lines, killed after 180 s. V80_K in test.env sets the
 * iterations per thread (default 20000).
 */
#include <errno.h>
#include <pthread.h>
#include <setjmp.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/sysctl.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

/*
 * The wrappers below are the only code built with these features; the
 * compiler cannot inline them into plain-arm64 callers, so the threads' native
 * __atomic operations stay LDAXR/STLXR (Apple clang ignores .arch in inline asm).
 */
#define EMU __attribute__((target("lse,rcpc,rcpc-immo,lor,pauth,flagm,altnzcv,sb,dit,ssbs"), noinline))
#define ARCH ""
#define NTHREADS 8

static int failures, checks;
static const char *current = "init";

#define CHECK(cond, ...) do { \
	checks++; \
	if (!(cond)) { \
		failures++; \
		if (failures <= 60) { printf("FAIL %s: ", current); printf(__VA_ARGS__); printf("\n"); } \
	} \
} while (0)

/* ------------------------------------------------------------------ */
/* deterministic random values biased towards edge cases               */

static uint64_t rng_state = 0x8890889088908890ULL;

static uint64_t
rnd(void)
{
	rng_state ^= rng_state << 13;
	rng_state ^= rng_state >> 7;
	rng_state ^= rng_state << 17;
	switch (rng_state & 7) {
	case 0: return 0;
	case 1: return ~0ULL;
	case 2: return 0x80ULL << ((rng_state >> 8) & 56);
	case 3: return (rng_state >> 3) & 0xFF;
	default: return rng_state * 0x9E3779B97F4A7C15ULL;
	}
}

static uint64_t
mask(unsigned size)
{
	return size == 8 ? ~0ULL : ((1ULL << (8 * size)) - 1);
}

static int64_t
sext(uint64_t v, unsigned size)
{
	if (size == 8) {
		return (int64_t)v;
	}
	const uint64_t m = 1ULL << (8 * size - 1);
	v &= mask(size);
	return (int64_t)((v ^ m) - m);
}

/* ------------------------------------------------------------------ */
/* the instructions under test                                         */

#define CAS(name, insn, r) \
static EMU uint64_t name(void *p, uint64_t expected, uint64_t desired) { \
	__asm__ volatile(ARCH insn " %" r "0, %" r "2, [%1]" \
	    : "+r"(expected) : "r"(p), "r"(desired) : "memory"); \
	return expected; }
CAS(casb, "casb", "w")
CAS(casalh, "casalh", "w")
CAS(casa_w, "casa", "w")
CAS(casl_w, "casl", "w")
CAS(casal_x, "casal", "x")
CAS(cas_x, "cas", "x")

#define LDOP(name, insn, r) \
static EMU uint64_t name(void *p, uint64_t operand) { \
	uint64_t old; \
	__asm__ volatile(ARCH insn " %" r "1, %" r "0, [%2]" \
	    : "=&r"(old) : "r"(operand), "r"(p) : "memory"); \
	return old; }
#define LDOP4(op) \
	LDOP(op##b, #op "alb", "w") LDOP(op##h, #op "alh", "w") \
	LDOP(op##w, #op "al", "w") LDOP(op##x, #op "al", "x")
LDOP4(ldadd) LDOP4(ldclr) LDOP4(ldeor) LDOP4(ldset)
LDOP4(ldsmax) LDOP4(ldsmin) LDOP4(ldumax) LDOP4(ldumin) LDOP4(swp)

typedef uint64_t (*ldop_fn)(void *, uint64_t);
static const struct {
	const char *name;
	ldop_fn fn[4];          /* B H W X */
} ldops[] = {
	{ "ldadd", { ldaddb, ldaddh, ldaddw, ldaddx } },
	{ "ldclr", { ldclrb, ldclrh, ldclrw, ldclrx } },
	{ "ldeor", { ldeorb, ldeorh, ldeorw, ldeorx } },
	{ "ldset", { ldsetb, ldseth, ldsetw, ldsetx } },
	{ "ldsmax", { ldsmaxb, ldsmaxh, ldsmaxw, ldsmaxx } },
	{ "ldsmin", { ldsminb, ldsminh, ldsminw, ldsminx } },
	{ "ldumax", { ldumaxb, ldumaxh, ldumaxw, ldumaxx } },
	{ "ldumin", { lduminb, lduminh, lduminw, lduminx } },
	{ "swp", { swpb, swph, swpw, swpx } },
};

static uint64_t
ldop_ref(unsigned op, unsigned size, uint64_t old, uint64_t v)
{
	const uint64_t m = mask(size);
	old &= m;
	v &= m;
	switch (op) {
	case 0: return (old + v) & m;
	case 1: return old & ~v;
	case 2: return old ^ v;
	case 3: return old | v;
	case 4: return sext(old, size) > sext(v, size) ? old : v;
	case 5: return sext(old, size) < sext(v, size) ? old : v;
	case 6: return old > v ? old : v;
	case 7: return old < v ? old : v;
	default: return v;
	}
}

static EMU void
caspal_x(uint64_t *p, uint64_t e0, uint64_t e1, uint64_t n0, uint64_t n1, uint64_t *o0, uint64_t *o1)
{
	register uint64_t s0 __asm__("x4") = e0, s1 __asm__("x5") = e1;
	register uint64_t t0 __asm__("x6") = n0, t1 __asm__("x7") = n1;
	__asm__ volatile(ARCH "caspal x4, x5, x6, x7, [%2]"
	    : "+r"(s0), "+r"(s1) : "r"(p), "r"(t0), "r"(t1) : "memory");
	*o0 = s0;
	*o1 = s1;
}

static EMU void
casp_w(uint32_t *p, uint32_t e0, uint32_t e1, uint32_t n0, uint32_t n1, uint32_t *o0, uint32_t *o1)
{
	register uint64_t s0 __asm__("x4") = e0, s1 __asm__("x5") = e1;
	register uint64_t t0 __asm__("x6") = n0, t1 __asm__("x7") = n1;
	__asm__ volatile(ARCH "casp w4, w5, w6, w7, [%2]"
	    : "+r"(s0), "+r"(s1) : "r"(p), "r"(t0), "r"(t1) : "memory");
	*o0 = (uint32_t)s0;
	*o1 = (uint32_t)s1;
}

#define LOAD(name, insn, r, off) \
static EMU uint64_t name(const void *p) { \
	uint64_t v; \
	__asm__ volatile(ARCH insn " %" r "0, [%1" off "]" : "=r"(v) : "r"(p) : "memory"); \
	return v; }
LOAD(ldaprb, "ldaprb", "w", "")
LOAD(ldaprh, "ldaprh", "w", "")
LOAD(ldapr_w, "ldapr", "w", "")
LOAD(ldapr_x, "ldapr", "x", "")
LOAD(ldapur_w_m4, "ldapur", "w", ", #-4")
LOAD(ldapursb_x_p3, "ldapursb", "x", ", #3")
LOAD(ldapursh_w_m2, "ldapursh", "w", ", #-2")
LOAD(ldapursw_p8, "ldapursw", "x", ", #8")
LOAD(ldlar_x, "ldlar", "x", "")

static EMU void
stlur_w_p4(void *p, uint64_t v)
{
	__asm__ volatile(ARCH "stlur %w0, [%1, #4]" : : "r"(v), "r"(p) : "memory");
}

static EMU void
stllrh(void *p, uint64_t v)
{
	__asm__ volatile(ARCH "stllrh %w0, [%1]" : : "r"(v), "r"(p) : "memory");
}

/* flags: NZCV in bits 31..28 */
#define FLAGOP(name, insn) \
static EMU uint64_t name(uint64_t nzcv, uint64_t x) { \
	uint64_t out; \
	__asm__ volatile(ARCH "msr nzcv, %1\n\t" insn "\n\tmrs %0, nzcv" \
	    : "=r"(out) : "r"(nzcv), "r"(x) : "cc"); \
	return out; }
FLAGOP(f_cfinv, "cfinv")
FLAGOP(f_xaflag, "xaflag")
FLAGOP(f_axflag, "axflag")
FLAGOP(f_rmif_3_a, "rmif %2, #3, #0xa")
FLAGOP(f_rmif_63_f, "rmif %2, #63, #0xf")
FLAGOP(f_setf8, "setf8 %w2")
FLAGOP(f_setf16, "setf16 %w2")

#define N_ (1ULL << 31)
#define Z_ (1ULL << 30)
#define C_ (1ULL << 29)
#define V_ (1ULL << 28)

static uint64_t
flag_ref(int which, uint64_t f, uint64_t x)
{
	const int Z = !!(f & Z_), C = !!(f & C_), V = !!(f & V_);
	switch (which) {
	case 0: return f ^ C_;
	case 1: return ((!C && !Z) ? N_ : 0) | ((Z && C) ? Z_ : 0) | ((C || Z) ? C_ : 0) | ((!C && Z) ? V_ : 0);
	case 2: return ((Z || V) ? Z_ : 0) | ((C && !V) ? C_ : 0);
	case 3: case 4: {
		const unsigned sh = which == 3 ? 3 : 63, msk = which == 3 ? 0xa : 0xf;
		const uint64_t t = (x >> sh) | (x << (64 - sh));
		const uint64_t sel = (uint64_t)msk << 28;
		return (f & ~sel) | (((t & 0xf) << 28) & sel);
	}
	default: {
		const unsigned msb = which == 5 ? 7 : 15;
		const int n = (x >> msb) & 1;
		const int z = (x & ((2ULL << msb) - 1)) == 0;
		const int v = ((x >> (msb + 1)) & 1) ^ n;
		return (C ? C_ : 0) | (n ? N_ : 0) | (z ? Z_ : 0) | (v ? V_ : 0);
	}
	}
}

/* PAuth: nothing is signed on this CPU, so these must leave values alone */
static EMU uint64_t
pac_roundtrip(uint64_t ptr, uint64_t mod)
{
	__asm__ volatile(ARCH "pacia %0, %1\n\tautia %0, %1\n\tpacda %0, %1\n\tautda %0, %1\n\txpaci %0"
	    : "+r"(ptr) : "r"(mod));
	return ptr;
}

static EMU uint64_t
pacga_of(uint64_t a, uint64_t b)
{
	uint64_t d;
	__asm__ volatile(ARCH "pacga %0, %1, %2" : "=r"(d) : "r"(a), "r"(b));
	return d;
}

static EMU uint64_t
ldraa_at(const uint64_t *p)
{
	uint64_t v;
	__asm__ volatile(ARCH "ldraa %0, [%1, #16]" : "=r"(v) : "r"(p) : "memory");
	return v;
}

static EMU int
branch_auth(void)
{
	uint64_t a = 0, b = 0, c = 0;
	__asm__ volatile(ARCH
	    "adr x16, 1f\n\tmov x17, #0x55\n\tbraa x16, x17\n\tb 2f\n1:\tmov %0, #1\n2:\n\t"
	    "adr x16, 3f\n\tblraa x16, x17\n\tb 4f\n3:\tmov %1, #1\n\tret\n4:\n\t"
	    "adr x30, 5f\n\tretab\n\tb 6f\n5:\tmov %2, #1\n6:"
	    : "+r"(a), "+r"(b), "+r"(c) : : "x16", "x17", "x30", "memory");
	return (int)(a + b + c);
}

static EMU void
misc_pstate(void)
{
	uint64_t dit;
	/* msr dit, #1 / mrs DIT / msr dit, #0 by encoding: not every assembler knows the name */
	__asm__ volatile(ARCH ".inst 0xd503415f\n\tmrs %0, s3_3_c4_c2_5\n\t.inst 0xd503405f\n\tsb\n\tmsr ssbs, #0"
	    : "=r"(dit) : : "memory");
	CHECK(dit == 0, "MRS DIT = %#llx (RAZ esperado)", (unsigned long long)dit);
}

/* ------------------------------------------------------------------ */
/* kern.v80emu                                                         */

static const char *class_names[] = { "none", "cas", "casp", "ldop", "swp", "ldapr", "rcpc2", "lor",
	                             "pac", "pacga", "brauth", "ldraa", "flagm", "pstate", "barrier", "sysreg" };

struct v80_counts {
	int ok;
	uint32_t ncls, nsites;
	uint64_t c[16][4];
};

static struct v80_counts
read_counts(void)
{
	struct v80_counts r;
	memset(&r, 0, sizeof(r));
	size_t len = 0;
	/* struct v80emu_export_header: 6 x u32 + 3 x u64 = 48 bytes */
	if (sysctlbyname("kern.v80emu", NULL, &len, NULL, 0) != 0 || len < 48) {
		return r;
	}
	uint8_t *buf = malloc(len);
	if (buf && sysctlbyname("kern.v80emu", buf, &len, NULL, 0) == 0 && len >= 48 &&
	    memcmp(buf, "V80E", 4) == 0) {
		memcpy(&r.ncls, buf + 8, 4);
		memcpy(&r.nsites, buf + 12, 4);
		for (uint32_t i = 0; i < r.ncls && i < 16 && 48 + 32 * (i + 1) <= len; i++) {
			memcpy(r.c[i], buf + 48 + 32 * i, 32);
		}
		r.ok = 1;
	}
	free(buf);
	return r;
}

/* ------------------------------------------------------------------ */
/* 1. semantics                                                        */

static void
test_semantics(void)
{
	static uint64_t mem[8] __attribute__((aligned(64)));
	const unsigned sizes[4] = { 1, 2, 4, 8 };

	current = "cas";
	for (int i = 0; i < 4000; i++) {
		static uint64_t (*const fns[])(void *, uint64_t, uint64_t) = { casb, casalh, casa_w, casl_w, casal_x, cas_x };
		static const unsigned fsz[] = { 1, 2, 4, 4, 8, 8 };
		const int k = i % 6;
		const unsigned sz = fsz[k];
		const uint64_t m = mask(sz);
		const uint64_t init = rnd();
		const uint64_t exp = (i & 1) ? (init & m) : rnd();
		const uint64_t des = rnd();
		mem[0] = init;
		const uint64_t got = fns[k](mem, exp & m, des & m);
		const uint64_t want_mem = ((init & m) == (exp & m)) ? ((init & ~m) | (des & m)) : init;
		CHECK(got == (init & m) && mem[0] == want_mem, "k=%d init=%#llx exp=%#llx des=%#llx got=%#llx mem=%#llx",
		    k, (unsigned long long)init, (unsigned long long)exp, (unsigned long long)des,
		    (unsigned long long)got, (unsigned long long)mem[0]);
	}

	current = "ldop/swp";
	for (unsigned op = 0; op < 9; op++) {
		for (unsigned s = 0; s < 4; s++) {
			for (int i = 0; i < 300; i++) {
				const unsigned sz = sizes[s];
				const uint64_t m = mask(sz);
				const uint64_t init = rnd(), v = rnd();
				mem[1] = init;
				const uint64_t got = ldops[op].fn[s](&mem[1], v);
				const uint64_t want = (init & ~m) | ldop_ref(op, sz, init, v);
				CHECK(got == (init & m) && mem[1] == want, "%s size %u init=%#llx v=%#llx got=%#llx mem=%#llx want=%#llx",
				    ldops[op].name, sz, (unsigned long long)init, (unsigned long long)v,
				    (unsigned long long)got, (unsigned long long)mem[1], (unsigned long long)want);
			}
		}
	}

	current = "casp";
	for (int i = 0; i < 1000; i++) {
		const uint64_t a = rnd(), b = rnd(), c = rnd(), d = rnd();
		const int hit = i & 1;
		uint64_t o0, o1;
		mem[2] = a;
		mem[3] = b;
		caspal_x(&mem[2], hit ? a : c, hit ? b : d, c, d, &o0, &o1);
		const int same = hit || (a == c && b == d);
		CHECK(o0 == a && o1 == b && mem[2] == (same ? c : a) && mem[3] == (same ? d : b), "caspal x i=%d", i);
		uint32_t *w = (uint32_t *)&mem[4];
		uint32_t p0, p1;
		w[0] = (uint32_t)a;
		w[1] = (uint32_t)b;
		casp_w(w, hit ? (uint32_t)a : (uint32_t)c, hit ? (uint32_t)b : (uint32_t)d, (uint32_t)c, (uint32_t)d, &p0, &p1);
		const int same32 = hit || ((uint32_t)a == (uint32_t)c && (uint32_t)b == (uint32_t)d);
		CHECK(p0 == (uint32_t)a && p1 == (uint32_t)b && w[0] == (uint32_t)(same32 ? c : a) &&
		    w[1] == (uint32_t)(same32 ? d : b), "casp w i=%d", i);
	}

	current = "ldapr/ldapur/stlur/lor";
	for (int i = 0; i < 1000; i++) {
		uint8_t *b = (uint8_t *)mem;
		for (int j = 0; j < 64; j++) {
			b[j] = (uint8_t)rnd();
		}
		uint64_t q[8];
		memcpy(q, mem, 64);
		CHECK(ldaprb(b + 3) == b[3], "ldaprb");
		CHECK(ldaprh(b + 6) == *(uint16_t *)(b + 6), "ldaprh");
		CHECK(ldapr_w(b + 12) == *(uint32_t *)(b + 12), "ldapr w");
		CHECK(ldapr_x(b + 16) == q[2], "ldapr x");
		CHECK(ldapur_w_m4(b + 24) == *(uint32_t *)(b + 20), "ldapur w #-4");
		CHECK(ldapursb_x_p3(b + 29) == (uint64_t)(int64_t)(int8_t)b[32], "ldapursb x #3");
		CHECK(ldapursh_w_m2(b + 36) == (uint64_t)(uint32_t)(int32_t)*(int16_t *)(b + 34), "ldapursh w #-2");
		CHECK(ldapursw_p8(b + 32) == (uint64_t)(int64_t)*(int32_t *)(b + 40), "ldapursw #8");
		CHECK(ldlar_x(b + 48) == q[6], "ldlar x");
		const uint64_t v = rnd();
		stlur_w_p4(b + 52, v);
		CHECK(*(uint32_t *)(b + 56) == (uint32_t)v, "stlur w #4");
		stllrh(b + 60, v);
		CHECK(*(uint16_t *)(b + 60) == (uint16_t)v, "stllrh");
	}

	current = "flagm";
	static uint64_t (*const flagfns[])(uint64_t, uint64_t) = {
		f_cfinv, f_xaflag, f_axflag, f_rmif_3_a, f_rmif_63_f, f_setf8, f_setf16 };
	for (int i = 0; i < 2000; i++) {
		const int k = i % 7;
		const uint64_t f = (rnd() & 0xf) << 28, x = rnd();
		const uint64_t got = flagfns[k](f, x) & 0xF0000000ULL;
		CHECK(got == flag_ref(k, f, x), "op %d nzcv=%#llx x=%#llx got=%#llx want=%#llx", k,
		    (unsigned long long)f, (unsigned long long)x, (unsigned long long)got,
		    (unsigned long long)flag_ref(k, f, x));
	}

	current = "pauth";
	for (int i = 0; i < 500; i++) {
		const uint64_t ptr = 0x100000000ULL + (rnd() & 0xFFFFFFF0ULL), mod = rnd();
		CHECK(pac_roundtrip(ptr, mod) == ptr, "pac/aut/xpac cambian el puntero %#llx", (unsigned long long)ptr);
		const uint64_t g = pacga_of(ptr, mod);
		CHECK((g & 0xFFFFFFFFULL) == 0 && g == pacga_of(ptr, mod), "pacga %#llx", (unsigned long long)g);
		mem[2] = rnd();
		CHECK(ldraa_at(mem) == mem[2], "ldraa #16");
	}
	CHECK(branch_auth() == 3, "braa/blraa/retab");

	current = "pstate";
	misc_pstate();
}

/* ------------------------------------------------------------------ */
/* 2. atomicity across cores                                           */

static unsigned K = 20000;
static struct {
	uint64_t add __attribute__((aligned(128)));
	uint64_t cas __attribute__((aligned(128)));
	uint64_t lock __attribute__((aligned(128)));
	uint64_t plain __attribute__((aligned(128)));
	uint64_t pair[2] __attribute__((aligned(128)));
	uint64_t pair_bad;
	uint32_t small[4] __attribute__((aligned(128)));
} shared;

static void *
worker(void *arg)
{
	const unsigned id = (unsigned)(uintptr_t)arg;
	for (unsigned i = 0; i < K; i++) {
		if (id & 1) {
			ldaddx(&shared.add, 1);                       /* emulated */
		} else {
			__atomic_fetch_add(&shared.add, 1, __ATOMIC_SEQ_CST);  /* native LDAXR/STLXR */
		}

		uint64_t old = ldapr_x(&shared.cas), seen;           /* emulated CAS loop */
		while ((seen = casal_x(&shared.cas, old, old + 1)) != old) {
			old = seen;
		}

		while (swpx(&shared.lock, 1) != 0) {                 /* emulated SWP spinlock */
		}
		shared.plain++;
		__atomic_store_n(&shared.lock, 0, __ATOMIC_RELEASE);

		uint64_t lo = shared.pair[0], hi = shared.pair[1];   /* emulated 128-bit CAS */
		for (;;) {
			uint64_t o0, o1;
			caspal_x(shared.pair, lo, hi, lo + 1, hi + 2, &o0, &o1);
			if (o0 == lo && o1 == hi) {
				break;
			}
			if (o1 != 2 * o0) {
				__atomic_fetch_add(&shared.pair_bad, 1, __ATOMIC_RELAXED);
			}
			lo = o0;
			hi = o1;
		}

		ldaddh((uint8_t *)shared.small + 2 * (id & 1), 1);   /* neighbouring halfwords */
		ldaddb((uint8_t *)shared.small + 8 + (id & 3), 1);   /* neighbouring bytes */
	}
	return NULL;
}

static void
test_threads(void)
{
	current = "threads";
	memset(&shared, 0, sizeof(shared));
	pthread_t t[NTHREADS];
	const uint64_t t0 = clock_gettime_nsec_np(CLOCK_UPTIME_RAW);
	for (unsigned i = 0; i < NTHREADS; i++) {
		pthread_create(&t[i], NULL, worker, (void *)(uintptr_t)i);
	}
	for (unsigned i = 0; i < NTHREADS; i++) {
		pthread_join(t[i], NULL);
	}
	const uint64_t dt = clock_gettime_nsec_np(CLOCK_UPTIME_RAW) - t0;
	const uint64_t n = (uint64_t)NTHREADS * K;
	CHECK(shared.add == n, "LDADD emulado + LL/SC nativo: %llu, esperado %llu", (unsigned long long)shared.add, (unsigned long long)n);
	CHECK(shared.cas == n, "bucle CASAL: %llu, esperado %llu", (unsigned long long)shared.cas, (unsigned long long)n);
	CHECK(shared.plain == n, "cerrojo SWPAL: %llu, esperado %llu", (unsigned long long)shared.plain, (unsigned long long)n);
	CHECK(shared.pair[0] == n && shared.pair[1] == 2 * n && shared.pair_bad == 0,
	    "CASPAL: lo=%llu hi=%llu lecturas rotas=%llu", (unsigned long long)shared.pair[0],
	    (unsigned long long)shared.pair[1], (unsigned long long)shared.pair_bad);
	const uint16_t *h = (const uint16_t *)shared.small;
	const uint8_t *b = (const uint8_t *)shared.small + 8;
	CHECK(h[0] == (uint16_t)(n / 2) && h[1] == (uint16_t)(n / 2), "LDADDH vecinas: %u %u", h[0], h[1]);
	CHECK(b[0] == (uint8_t)(n / 4) && b[1] == (uint8_t)(n / 4) && b[2] == (uint8_t)(n / 4) && b[3] == (uint8_t)(n / 4),
	    "LDADDB vecinas: %u %u %u %u", b[0], b[1], b[2], b[3]);
	printf("threads: %u hilos x %u iteraciones en %.2f s\n", NTHREADS, K, dt / 1e9);
}

/* ------------------------------------------------------------------ */
/* 3. faults                                                           */

static sigjmp_buf jb;
static volatile sig_atomic_t got_sig;
static void *volatile got_addr;

static void
on_fault(int sig, siginfo_t *si, void *uc)
{
	(void)uc;
	got_sig = sig;
	got_addr = si->si_addr;
	siglongjmp(jb, 1);
}

static int
expect_signal(void *p, int size8, const char *what)
{
	got_sig = 0;
	got_addr = NULL;
	if (sigsetjmp(jb, 1) == 0) {
		if (size8) {
			casal_x(p, 0, 1);
		} else {
			ldaddw(p, 1);
		}
		CHECK(0, "%s: no hubo senal", what);
		return 0;
	}
	CHECK(got_sig == SIGSEGV || got_sig == SIGBUS, "%s: senal %d", what, (int)got_sig);
	CHECK(got_addr == p, "%s: si_addr=%p, esperado %p", what, got_addr, p);
	return got_sig;
}

static void
test_faults(void)
{
	const size_t pg = (size_t)getpagesize();
	current = "zero-fill";
	uint8_t *z = mmap(NULL, 64 * pg, PROT_READ | PROT_WRITE, MAP_ANON | MAP_PRIVATE, -1, 0);
	for (int i = 0; i < 64; i++) {
		CHECK(ldaddx(z + i * pg + 8, 5) == 0, "pagina %d: old != 0", i);
		CHECK(*(uint64_t *)(z + i * pg + 8) == 5, "pagina %d: valor", i);
	}

	current = "cow";
	uint64_t *c = mmap(NULL, pg, PROT_READ | PROT_WRITE, MAP_ANON | MAP_PRIVATE, -1, 0);
	c[0] = 41;
	pid_t pid = fork();
	if (pid == 0) {
		const uint64_t o = casal_x(c, 41, 42);           /* first write after fork: COW */
		_exit(o == 41 && c[0] == 42 ? 0 : 1);
	}
	if (pid < 0) {
		printf("cow: fork no disponible (%s), prueba saltada\n", strerror(errno));
	} else {
		int st = 0;
		waitpid(pid, &st, 0);
		CHECK(WIFEXITED(st) && WEXITSTATUS(st) == 0, "hijo tras fork: estado %#x", st);
		CHECK(c[0] == 41, "el padre ve %llu (debia seguir 41)", (unsigned long long)c[0]);
	}

	struct sigaction sa, old_segv, old_bus;
	memset(&sa, 0, sizeof(sa));
	sa.sa_sigaction = on_fault;
	sa.sa_flags = SA_SIGINFO;
	sigaction(SIGSEGV, &sa, &old_segv);
	sigaction(SIGBUS, &sa, &old_bus);

	current = "solo-lectura";
	uint64_t *ro = mmap(NULL, pg, PROT_READ, MAP_ANON | MAP_PRIVATE, -1, 0);
	expect_signal(ro, 1, "CASAL en pagina de solo lectura");
	current = "sin-mapear";
	uint64_t *um = mmap(NULL, pg, PROT_READ | PROT_WRITE, MAP_ANON | MAP_PRIVATE, -1, 0);
	munmap(um, pg);
	expect_signal(um, 1, "CASAL en pagina sin mapear");
	current = "desalineado";
	const int s = expect_signal((uint8_t *)c + 4, 1, "CASAL x en direccion +4");
	CHECK(s == SIGBUS, "desalineado: senal %d, esperaba SIGBUS", s);
	expect_signal((uint8_t *)c + 2, 0, "LDADD w en direccion +2");

	sigaction(SIGSEGV, &old_segv, NULL);
	sigaction(SIGBUS, &old_bus, NULL);
}

/* ------------------------------------------------------------------ */
/* 4. cost                                                             */

static void
test_cost(void)
{
	static uint64_t w __attribute__((aligned(64)));
	const unsigned n = 100000;
	uint64_t t0 = clock_gettime_nsec_np(CLOCK_UPTIME_RAW);
	for (unsigned i = 0; i < n; i++) {
		__atomic_fetch_add(&w, 1, __ATOMIC_SEQ_CST);
	}
	uint64_t t1 = clock_gettime_nsec_np(CLOCK_UPTIME_RAW);
	for (unsigned i = 0; i < n; i++) {
		ldaddx(&w, 1);
	}
	uint64_t t2 = clock_gettime_nsec_np(CLOCK_UPTIME_RAW);
	for (unsigned i = 0; i < n; i++) {
		(void)ldapr_x(&w);
	}
	uint64_t t3 = clock_gettime_nsec_np(CLOCK_UPTIME_RAW);
	for (unsigned i = 0; i < n; i++) {
		(void)pac_roundtrip(0x100000000ULL, i);
	}
	uint64_t t4 = clock_gettime_nsec_np(CLOCK_UPTIME_RAW);
	printf("coste: LL/SC nativo %.0f ns | LDADDAL emulado %.0f ns | LDAPR emulado %.0f ns | 5 PAC emuladas %.0f ns\n",
	    (double)(t1 - t0) / n, (double)(t2 - t1) / n, (double)(t3 - t2) / n, (double)(t4 - t3) / n);
	current = "coste";
	CHECK(w == 2ULL * n, "contador %llu", (unsigned long long)w);
}

/* ------------------------------------------------------------------ */

static void
on_sigill(int sig, siginfo_t *si, void *uc)
{
	(void)sig;
	(void)uc;
	printf("FATAL SIGILL en %s, pc=%p: instruccion no emulada\n", current, si->si_addr);
	fflush(stdout);
	_exit(2);
}

int
main(void)
{
	setvbuf(stdout, NULL, _IOLBF, 0);
	const char *k = getenv("V80_K");
	if (k && atoi(k) > 0) {
		K = (unsigned)atoi(k);
	}
	struct sigaction sa;
	memset(&sa, 0, sizeof(sa));
	sa.sa_sigaction = on_sigill;
	sa.sa_flags = SA_SIGINFO;
	sigaction(SIGILL, &sa, NULL);

	int ncpu = 0;
	size_t l = sizeof(ncpu);
	sysctlbyname("hw.ncpu", &ncpu, &l, NULL, 0);
	struct v80_counts before = read_counts();
	printf("v80stress: hw.ncpu=%d kern.v80emu=%s K=%u\n", ncpu, before.ok ? "si" : "NO", K);

	test_semantics();
	printf("semantica: %d comprobaciones, %d fallos\n", checks, failures);
	test_threads();
	test_faults();
	test_cost();

	struct v80_counts after = read_counts();
	if (after.ok) {
		printf("kern.v80emu (traps/emuladas/fallos/SIGILL de esta prueba), sitios=%u:\n", after.nsites);
		for (uint32_t i = 0; i < after.ncls && i < 16; i++) {
			const uint64_t d0 = after.c[i][0] - before.c[i][0];
			if (d0) {
				printf("  %-8s %llu / %llu / %llu / %llu\n", class_names[i], (unsigned long long)d0,
				    (unsigned long long)(after.c[i][1] - before.c[i][1]),
				    (unsigned long long)(after.c[i][2] - before.c[i][2]),
				    (unsigned long long)(after.c[i][3] - before.c[i][3]));
			}
		}
	}
	printf("v80stress: %s (%d comprobaciones, %d fallos)\n", failures ? "FALLOS" : "TODO OK", checks, failures);
	return failures ? 1 : 0;
}

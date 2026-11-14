// SPDX-License-Identifier: MIT
// Galaxy S7 port: a sampling profiler for backboardd (HERO_PROF=1 in gl.env). With the GPU path a frame took
// ~100 ms, of which the GPU and the kernel submits explained ~35 ms: this finds the rest. Every 2 ms the threads
// that are on a CPU are suspended one at a time and their pc recorded; every 10 s the samples are grouped by
// function (dladdr, after every thread runs again: a suspended thread may hold dyld's lock) and the top ones
// logged with their image offset, so functions dladdr cannot name (Mesa's static ones) can be looked up offline.
#include <dlfcn.h>
#include <mach/mach.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MAX_SAMPLES 16384
#define MAX_FUNCS 2048

static uint64_t g_pc[MAX_SAMPLES];
static unsigned g_n, g_ticks, g_idle;

static void sample(thread_t self) {
    thread_act_array_t th;
    mach_msg_type_number_t n;
    if (task_threads(mach_task_self(), &th, &n) != KERN_SUCCESS) return;
    int any = 0;
    for (unsigned i = 0; i < n; i++) {
        struct thread_basic_info bi;
        mach_msg_type_number_t c = THREAD_BASIC_INFO_COUNT;
        if (th[i] != self && g_n < MAX_SAMPLES &&
            thread_info(th[i], THREAD_BASIC_INFO, (thread_info_t)&bi, &c) == KERN_SUCCESS &&
            bi.run_state == TH_STATE_RUNNING && !(bi.flags & TH_FLAGS_IDLE) &&
            thread_suspend(th[i]) == KERN_SUCCESS) {
            arm_thread_state64_t st;
            mach_msg_type_number_t sc = ARM_THREAD_STATE64_COUNT;
            if (thread_get_state(th[i], ARM_THREAD_STATE64, (thread_state_t)&st, &sc) == KERN_SUCCESS) {
                g_pc[g_n++] = arm_thread_state64_get_pc(st);
                any = 1;
            }
            thread_resume(th[i]);
        }
        mach_port_deallocate(mach_task_self(), th[i]);
    }
    vm_deallocate(mach_task_self(), (vm_address_t)th, n * sizeof(thread_t));
    g_ticks++;
    if (!any) g_idle++;
}

typedef struct { uintptr_t key, base; const char *img, *sym; unsigned count; } Func;
static Func g_f[MAX_FUNCS];

static int by_count(const void *a, const void *b) {
    return (int)((const Func *)b)->count - (int)((const Func *)a)->count;
}

static Func *slot(uintptr_t key) {
    for (unsigned i = 0; i < MAX_FUNCS; i++) {
        Func *f = &g_f[(key / 16 + i) % MAX_FUNCS];
        if (f->key == key || f->key == 0) return f;
    }
    return NULL;
}

static void report(void) {
    unsigned n = g_n;
    if (!n) return;
    memset(g_f, 0, sizeof g_f);
    unsigned imgs = 0;
    Func img[48];
    for (unsigned i = 0; i < n; i++) {
        Dl_info di;
        memset(&di, 0, sizeof di);
        int ok = dladdr((void *)g_pc[i], &di);
        uintptr_t key = ok && di.dli_saddr ? (uintptr_t)di.dli_saddr : (g_pc[i] & ~(uintptr_t)0xff);
        Func *f = slot(key);
        if (f) {
            if (!f->key) *f = (Func){ key, (uintptr_t)di.dli_fbase, ok ? di.dli_fname : NULL, ok ? di.dli_sname : NULL, 0 };
            f->count++;
        }
        const char *fn = ok && di.dli_fname ? di.dli_fname : "?";
        unsigned k = 0;
        while (k < imgs && strcmp(img[k].img, fn)) k++;
        if (k == imgs && imgs < 48) img[imgs++] = (Func){ 0, 0, fn, NULL, 0 };
        if (k < imgs) img[k].count++;
    }
    qsort(img, imgs, sizeof img[0], by_count);
    fprintf(stderr, "PROF %u samples in %u ticks (%.0f%% of ticks with no thread on a CPU)\n", n, g_ticks,
            g_ticks ? 100.0 * g_idle / g_ticks : 0.0);
    for (unsigned k = 0; k < imgs && k < 12; k++) {
        const char *b = strrchr(img[k].img, '/');
        fprintf(stderr, "PROF image %5.1f%% %s\n", 100.0 * img[k].count / n, b ? b + 1 : img[k].img);
    }
    qsort(g_f, MAX_FUNCS, sizeof g_f[0], by_count);
    for (unsigned k = 0; k < MAX_FUNCS && k < 45 && g_f[k].count; k++) {
        const char *b = g_f[k].img ? strrchr(g_f[k].img, '/') : NULL;
        fprintf(stderr, "PROF fn %5.1f%% %s!%s +0x%lx\n", 100.0 * g_f[k].count / n,
                b ? b + 1 : (g_f[k].img ? g_f[k].img : "?"), g_f[k].sym ? g_f[k].sym : "?",
                (unsigned long)(g_f[k].key - g_f[k].base));
    }
    g_n = g_ticks = g_idle = 0;
}

static void *prof_main(void *arg) {
    (void)arg;
    sleep(3);                   // gl.env is loaded by hero_log.c's constructor
    const char *e = getenv("HERO_PROF");
    if (!e || e[0] != '1') return NULL;
    thread_t self = pthread_mach_thread_np(pthread_self());
    fprintf(stderr, "PROF: sampling backboardd every 2 ms\n");
    for (;;) {
        for (unsigned t = 0; t < 5000; t++) {   // 10 s
            sample(self);
            usleep(2000);
        }
        report();
    }
    return NULL;
}

__attribute__((visibility("hidden"))) void hero_prof_start(void) {
    pthread_t t;
    if (pthread_create(&t, NULL, prof_main, NULL) == 0) pthread_detach(t);
}

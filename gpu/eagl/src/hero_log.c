// SPDX-License-Identifier: MIT
// Galaxy S7 port: with HERO_LOG_STDERR=1 (the kernel sets it for backboardd, bsd/dev/herolte_gl.c), this
// process's stderr becomes a pipe whose lines go to the kernel log through the libdrm stand-in's herodrm_log
// (gpu/mesa/herodrm.c), so the shim's and Mesa's messages from inside a system daemon reach the USERDATA log
// ring that TWRP can read. At most HERO_LOG_MAX lines (default 3000), then one line saying the rest is dropped.
#include <dlfcn.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void (*klog)(const char *fmt, ...);
static int log_fd = -1;

static void *pump(void *arg) {
    (void)arg;
    char buf[1024], line[512];
    size_t len = 0;
    long max = getenv("HERO_LOG_MAX") ? atol(getenv("HERO_LOG_MAX")) : 3000, sent = 0;
    const char *prog = getprogname();
    for (;;) {
        ssize_t n = read(log_fd, buf, sizeof buf);
        if (n <= 0) return NULL;
        for (ssize_t i = 0; i < n; i++) {
            char c = buf[i];
            if (c != '\n' && len < sizeof line - 1) { line[len++] = c; continue; }
            line[len] = 0;
            // herodrm_log() also prints its line to stderr: it is already in the kernel log.
            if (len && strncmp(line, "herodrm: ", 9) != 0) {
                if (sent < max) klog("%s: %s", prog, line);
                else if (sent == max) klog("%s: further stderr lines dropped (HERO_LOG_MAX %ld)", prog, max);
                sent++;
            }
            len = 0;
        }
    }
}

// Extra KEY=VALUE lines for the shim (debug and trace switches) from the drop zone, so they change without a new
// kernel: the kernel only sets DYLD_INSERT_LIBRARIES and HERO_LOG_STDERR.
static void load_gl_env(void) {
    FILE *f = fopen("/private/var/herolte/gl.env", "r");
    char line[256];
    while (f && fgets(line, sizeof line, f)) {
        line[strcspn(line, "\r\n")] = 0;
        char *eq = strchr(line, '=');
        if (line[0] == '#' || !eq) continue;
        *eq = 0;
        setenv(line, eq + 1, 1);
    }
    if (f) fclose(f);
}

__attribute__((constructor)) static void hero_log_init(void) {
    if (getenv("HERO_LOG_STDERR")) load_gl_env();
    const char *on = getenv("HERO_LOG_STDERR");
    if (!on || *on != '1') return;
    klog = (void (*)(const char *, ...))dlsym(RTLD_DEFAULT, "herodrm_log");
    int fds[2];
    if (!klog || pipe(fds) != 0) return;
    if (dup2(fds[1], STDERR_FILENO) < 0) { close(fds[0]); close(fds[1]); return; }
    close(fds[1]);
    log_fd = fds[0];
    setvbuf(stderr, NULL, _IOLBF, 0);
    pthread_t t;
    if (pthread_create(&t, NULL, pump, NULL) == 0) pthread_detach(t);
    klog("%s: EAGL shim loaded (pid %d), stderr -> kernel log", getprogname(), getpid());
}

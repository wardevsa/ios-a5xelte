// SPDX-License-Identifier: MIT
// Fills gl_tab: every exported gl* entry point forwards to the Mesa glapi dispatcher, which routes to the
// context made current by OSMesaMakeCurrent on this thread. Names Mesa lacks get a vendor-suffix-stripped alias
// or a no-op / "unimplemented" handler that logs once.
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdarg.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include "osm.h"
#include "gl_tab.h"

static void gl_noop(void) {}

// Debug/marker/label entry points: harmless to ignore.
static const char *const noop_names[] = {
    "glInsertEventMarkerEXT", "glPushGroupMarkerEXT", "glPopGroupMarkerEXT", "glLabelObjectEXT",
    "glDiscardFramebufferEXT", "glCopyTextureLevelsAPPLE", "glGetObjectLabelEXT", 0 };

static const char *const suffixes[] = { "OES", "EXT", "APPLE", "ANGLE", "KHR", "IMG", "ARB", 0 };

static void gl_note(const char *fmt, ...);
// Called (through gl_unimpl in gl_unimpl.S) when a client calls an exported entry point Mesa could not provide.
static unsigned char reported[1024];
void gl_report_unimplemented(int idx) {
    if (idx >= 0 && idx < gl_nfuncs && !reported[idx]) {
        reported[idx] = 1;
        fprintf(stderr, "OpenGLES(shim): %s is not implemented\n", gl_names[idx]);
        gl_note("GL: %s: %s is not implemented", getprogname(), gl_names[idx]);
    }
}

extern void gl_unimpl(void);


// E-0365: what an application's shaders and unimplemented calls are, in /private/var/tmp/heroeagl.log (apps' stderr goes nowhere). Not in the system
// daemons (backboardd, SpringBoard), whose messages have their own route.
static int notes_wanted(void) {
    static int w = -1;
    if (w < 0) { const char *n = getprogname(); w = !(n && (!strcmp(n, "backboardd") || !strcmp(n, "SpringBoard"))); }
    return w;
}
static void gl_note(const char *fmt, ...) {
    if (!notes_wanted()) return;
    char line[700];
    va_list ap; va_start(ap, fmt);
    int n = vsnprintf(line, sizeof line - 1, fmt, ap);
    va_end(ap);
    if (n <= 0) return;
    if (n > (int)sizeof line - 2) n = (int)sizeof line - 2;
    line[n++] = '\n';
    int fd = open("/private/var/tmp/heroeagl.log", O_WRONLY | O_CREAT | O_APPEND, 0666);
    if (fd >= 0) { (void)!write(fd, line, (size_t)n); fchmod(fd, 0666); close(fd); }
}
static void *lookup(const char *n);
static void gl_ShaderSourceNote(unsigned shader, int count, const char *const *src, const int *len) {
    static void (*f)(unsigned, int, const char *const *, const int *); static int shown;
    if (!f) f = (void (*)(unsigned, int, const char *const *, const int *))lookup("glShaderSource");
    if (shown < 6 && count > 0 && src && src[0] && notes_wanted()) { shown++; gl_note("GL: %s glShaderSource(%u) %.500s", getprogname(), shader, src[0]); }
    f(shader, count, src, len);
}
static void gl_CompileShaderNote(unsigned shader) {
    static void (*f)(unsigned), (*gi)(unsigned, unsigned, int *), (*gl)(unsigned, int, int *, char *); static int shown;
    if (!f) { f = (void (*)(unsigned))lookup("glCompileShader"); gi = (void (*)(unsigned, unsigned, int *))lookup("glGetShaderiv"); gl = (void (*)(unsigned, int, int *, char *))lookup("glGetShaderInfoLog"); }
    f(shader);
    int ok = 1; gi(shader, 0x8b81, &ok);
    if (!ok && shown++ < 8) { char log[400] = ""; gl(shader, sizeof log, 0, log); gl_note("GL: %s glCompileShader(%u) FAILED: %.400s", getprogname(), shader, log); }
}
static void gl_LinkProgramNote(unsigned program) {
    static void (*f)(unsigned), (*gi)(unsigned, unsigned, int *), (*gl)(unsigned, int, int *, char *); static int shown;
    if (!f) { f = (void (*)(unsigned))lookup("glLinkProgram"); gi = (void (*)(unsigned, unsigned, int *))lookup("glGetProgramiv"); gl = (void (*)(unsigned, int, int *, char *))lookup("glGetProgramInfoLog"); }
    f(program);
    int ok = 1; gi(program, 0x8b82, &ok);
    if (!ok && shown++ < 8) { char log[400] = ""; gl(program, sizeof log, 0, log); gl_note("GL: %s glLinkProgram(%u) FAILED: %.400s", getprogname(), program, log); }
}
static void *lookup(const char *n) {
    void *p = osm_getproc(n);
    return p;
}

// Galaxy S7 port: GL_APPLE_fence and the object waits of GL_APPLE_flush_buffer_range's family, which Mesa does not
// have. iOS 16's CoreAnimation calls glFinishObjectAPPLE before it deletes a render target; it landed in
// gl_unimpl. Our submits are synchronous in the kernel, so finishing is a glFinish and every fence is signalled.
typedef unsigned GLu;
static void apple_finish(void) { static void (*f)(void); if (!f) f = (void (*)(void))lookup("glFinish"); if (f) f(); }
static void apple_flush(void) { static void (*f)(void); if (!f) f = (void (*)(void))lookup("glFlush"); if (f) f(); }
static void gl_FinishObjectAPPLE(GLu object, int name) { (void)object; (void)name; apple_finish(); }
static unsigned char gl_TestObjectAPPLE(GLu object, GLu name) { (void)object; (void)name; return 1; }
static void gl_GenFencesAPPLE(int n, GLu *fences) { static GLu next = 1; for (int i = 0; i < n; i++) fences[i] = next++; }
static void gl_DeleteFencesAPPLE(int n, const GLu *fences) { (void)n; (void)fences; }
static void gl_SetFenceAPPLE(GLu fence) { (void)fence; apple_flush(); }
static unsigned char gl_IsFenceAPPLE(GLu fence) { return fence != 0; }
static unsigned char gl_TestFenceAPPLE(GLu fence) { (void)fence; return 1; }
static void gl_FinishFenceAPPLE(GLu fence) { (void)fence; apple_finish(); }
static const struct { const char *name; void *fn; } apple_fns[] = {
    { "glFinishObjectAPPLE", (void *)gl_FinishObjectAPPLE }, { "glTestObjectAPPLE", (void *)gl_TestObjectAPPLE },
    { "glGenFencesAPPLE", (void *)gl_GenFencesAPPLE }, { "glDeleteFencesAPPLE", (void *)gl_DeleteFencesAPPLE },
    { "glShaderSource", (void *)gl_ShaderSourceNote }, { "glCompileShader", (void *)gl_CompileShaderNote }, { "glLinkProgram", (void *)gl_LinkProgramNote },
    { "glSetFenceAPPLE", (void *)gl_SetFenceAPPLE }, { "glIsFenceAPPLE", (void *)gl_IsFenceAPPLE },
    { "glTestFenceAPPLE", (void *)gl_TestFenceAPPLE }, { "glFinishFenceAPPLE", (void *)gl_FinishFenceAPPLE },
    { 0, 0 } };

void gl_resolve_all(void) {
    static int done;
    if (done) return;
    done = 1;
    for (int i = 0; i < gl_nfuncs; i++) {
        const char *n = gl_names[i];
        void *p = 0;
        for (int k = 0; noop_names[k]; k++)
            if (!strcmp(n, noop_names[k])) p = (void *)gl_noop;
        for (int k = 0; apple_fns[k].name && !p; k++)
            if (!strcmp(n, apple_fns[k].name)) p = apple_fns[k].fn;
        if (!p) p = lookup(n);
        if (!p) {
            size_t l = strlen(n);
            for (int k = 0; suffixes[k] && !p; k++) {
                size_t sl = strlen(suffixes[k]);
                if (l > sl + 2 && !strcmp(n + l - sl, suffixes[k])) {
                    char buf[128];
                    memcpy(buf, n, l - sl); buf[l - sl] = 0;
                    p = lookup(buf);
                }
            }
        }
        if (!p) {                       // glVertexAttrib4f -> glVertexAttrib4fARB and similar
            char buf[128];
            snprintf(buf, sizeof buf, "%sARB", n);
            p = lookup(buf);
            if (!p) { snprintf(buf, sizeof buf, "%sEXT", n); p = lookup(buf); }   // glVertexAttribI4i -> ...EXT
        }
        gl_tab[i] = p ? p : (void *)gl_unimpl;
    }
}

__attribute__((constructor)) static void gl_resolve_ctor(void) { gl_resolve_all(); }

// SPDX-License-Identifier: MIT
// Galaxy S7 port: CoreAnimation settings for backboardd when the shim is in it (bsd/dev/herolte_gl.c).
// With a GLES context available, iOS 16's render server picked a deep, two-plane display format ('b3a8',
// 10-bit colour plus an alpha plane) that neither this GPU path nor the display driver writes: the panel
// stayed black. As Chlorophyll's backboardd injector does (ry-diffusion/Chlorophyll, inject/, MIT), deep and
// compressed framebuffers and IOSurfaces are turned off before QuartzCore reads its preferences, so the
// display stays 8-bit BGRA.
#include <CoreFoundation/CoreFoundation.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

void hero_prof_start(void);         // hero_prof.c: sampling profiler, HERO_PROF=1

__attribute__((constructor)) static void hero_backboardd_init(void) {
    if (strcmp(getprogname(), "backboardd") != 0) return;
    hero_prof_start();
    setenv("CA_DISABLE_FRAMEBUFFER_COMPRESSION", "1", 1);
    CFPreferencesSetAppValue(CFSTR("CAEnableFramebufferCompression"), kCFBooleanFalse, kCFPreferencesCurrentApplication);
    CFPreferencesSetAppValue(CFSTR("CAEnableIOSurfaceCompression"), kCFBooleanFalse, kCFPreferencesCurrentApplication);
    CFPreferencesSetAppValue(CFSTR("CAEnableDeepFramebuffer"), kCFBooleanFalse, kCFPreferencesCurrentApplication);
}

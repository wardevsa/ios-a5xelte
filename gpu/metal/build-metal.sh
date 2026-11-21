#!/bin/bash
# Metal M3 (docs/herolte-metal.md): the Metal device of the S7 port, after build-mesa.sh (which leaves libhakiosair,
# libdrm.2 and ios-b1lte's checkout at B2L_REF in WORK). Runs on the macOS runner.
#
#   build-metal.sh WORK OUT
#
# OUT gets:
#   lib/libhakiosmetal.dylib   Scion's Metal device for Panfrost, ios-b1lte's version (userspace/metal/scion, MIT:
#                              hakiosmetal_air.m + hakiosdrawable.m), its paths moved to the drop zone and its log
#                              line sent to our kernel log (herodrm_log) instead of HakiOS's kern.hakios.say
#   metal/HeroMetal, metal/Info.plist
#                              the plug-in bundle (hero-metal-plugin.m), installed by hero-run as
#                              /System/Library/Extensions/HeroMetal.bundle
#   hero_mtl_test              MTLCreateSystemDefaultDevice() and one MercuryPoster draw through Metal
set -euo pipefail
WORK=$(cd "$1" && pwd)
OUT=$(mkdir -p "$2" && cd "$2" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
SDK=$(xcrun --sdk iphoneos --show-sdk-path)
CC="xcrun --sdk iphoneos clang -arch arm64 -miphoneos-version-min=16.0 -isysroot $SDK -O2 -Wno-deprecated-declarations -Wno-unused"
S=$WORK/b2l/userspace/metal/scion
T=$WORK/metal-src
rm -rf "$T"; mkdir -p "$T" "$OUT/lib" "$OUT/metal"

for f in "$S"/hakiosmetal_air.m "$S"/hakiosdrawable.m "$S"/*.h; do
  sed -e 's#/redwood/lib/#/private/var/herolte/lib/#g' \
      -e 's#(void)sysctlbyname("kern.hakios.say", NULL, NULL, line, len);#hero_say(line);#' "$f" > "$T/$(basename "$f")"
done
# the kernel log line: libdrm.2's herodrm_log (gpu/mesa/herodrm.c), looked up once
cat > "$T/hero_say.h" <<'H'
#include <dlfcn.h>
#include <stddef.h>
static void hero_say(const char *line)
{
	static void (*log)(const char *, ...);
	static int looked;
	if (!looked) {
		looked = 1;
		void *drm = dlopen("/private/var/herolte/lib/libdrm.2.dylib", RTLD_NOW);
		if (drm != NULL)
			log = (void (*)(const char *, ...))dlsym(drm, "herodrm_log");
	}
	if (log != NULL)
		log("%s", line);
}
H
grep -q 'hero_say(line)' "$T/hakiosmetal_air.m"
sed -i '' '1i\
#include "hero_say.h"
' "$T/hakiosmetal_air.m"
grep -c '/private/var/herolte/lib/libhakiosair.dylib' "$T/hakiosmetal_air.m" "$T/hakiosdrawable.m"

$CC -dynamiclib -install_name /private/var/herolte/lib/libhakiosmetal.dylib -I"$T" \
  -framework Foundation -framework IOKit -framework Metal -framework IOSurface -lobjc -Wl,-rpath,/private/var/herolte/lib \
  -o "$OUT/lib/libhakiosmetal.dylib" "$T/hakiosmetal_air.m" "$T/hakiosdrawable.m"
$CC -bundle -o "$OUT/metal/HeroMetal" "$HERE/hero-metal-plugin.m" -framework Foundation -framework IOKit -lobjc -Wl,-rpath,/private/var/herolte/lib
cat > "$OUT/metal/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleIdentifier</key><string>org.herolte.metal</string>
	<key>CFBundleName</key><string>HeroMetal</string>
	<key>CFBundleExecutable</key><string>HeroMetal</string>
	<key>CFBundlePackageType</key><string>BNDL</string>
	<key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
	<key>CFBundleVersion</key><string>1</string>
	<key>CFBundleSupportedPlatforms</key><array><string>iPhoneOS</string></array>
	<key>NSPrincipalClass</key><string>HeroMetalDevice</string>
</dict>
</plist>
PLIST
$CC -o "$OUT/hero_mtl_test" "$HERE/hero-mtl-test.m" -framework Foundation -framework Metal -lobjc -Wl,-rpath,/private/var/herolte/lib
for f in "$OUT/lib/libhakiosmetal.dylib" "$OUT/metal/HeroMetal" "$OUT/hero_mtl_test"; do
  codesign -s - -f "$f"
  otool -L "$f" | head -12
done
rm -rf "$T"

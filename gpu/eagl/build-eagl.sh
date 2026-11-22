#!/bin/bash
# The EAGL shim (Bergamota's gpu/eagl, MIT) for the Galaxy S7's iOS 16, over
# the Panfrost libOSMesa from gpu/mesa/build-mesa.sh. Injection build only:
# the system OpenGLES.framework is in the dyld cache, so libheroeagl.dylib
# copies its EAGLContext/EAGLSharegroup methods into the real classes when
# loaded. iOS 16's CoreAnimation then gets a working ES3 context and uses its
# own GLES renderer (no QuartzCore hook needed, unlike iOS 18).
#
#   build-eagl.sh OUT        (OUT as given to build-mesa.sh: lib/libOSMesa.8.dylib, lib/libdrm.2.dylib)
#
# Adds lib/libheroeagl.dylib, eagl_ca_test (CARenderer through the shim) and
# hero-run (the autorun that runs a test and logs its output).
set -euo pipefail
OUT=$(cd "$1" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
MESA_INC=${MESA_INC:?set MESA_INC to the Mesa source include/ directory}
SDK=$(xcrun --sdk iphoneos --show-sdk-path)
CC="xcrun --sdk iphoneos clang -arch arm64 -miphoneos-version-min=16.0 -isysroot $SDK"
OBJ=$(mktemp -d)

python3 "$HERE/tools/gen_gl_stubs.py" > "$OBJ/gl_stubs.c"
CF="-O2 -g -fvisibility=hidden -Wall -Wno-deprecated-declarations -Wno-unused-function -I$HERE/src -I$MESA_INC"
$CC $CF -c "$OBJ/gl_stubs.c" -o "$OBJ/gl_stubs.o"
for f in gl_resolve gl_unimpl osm macro_ctx macro_slots hero_log hero_backboardd hero_prof; do
  $CC $CF -c "$HERE/src/$f.c" -o "$OBJ/$f.o"
done
$CC $CF -fno-objc-arc -fobjc-exceptions -DEAGL_INJECT -c "$HERE/src/eagl.m" -o "$OBJ/eagl.o"
$CC -dynamiclib -o "$OUT/lib/libheroeagl.dylib" "$OBJ"/{gl_stubs,gl_resolve,gl_unimpl,osm,macro_ctx,macro_slots,hero_log,hero_backboardd,hero_prof,eagl}.o \
  -install_name @rpath/libheroeagl.dylib \
  -framework Foundation -framework CoreFoundation -framework CoreGraphics -framework IOSurface \
  -L "$OUT/lib" -lOSMesa.8 -Wl,-rpath,/private/var/herolte/lib -Wl,-undefined,error

# HakiOS's EAGL bridge (gpu/hakios-gl, MIT) as lib/libhakiosgl.dylib: its function table is generated from
# the slot table, Mesa's gl.xml and what our libOSMesa exports; gl_hero.c puts it over our OSMesa.
HG="$HERE/../hakios-gl"
nm -gU "$OUT/lib/libOSMesa.8.dylib" | awk '$3 ~ /^_gl/ { print substr($3, 2) }' > "$OBJ/exported-gl.txt"
python3 "$HG/mkeagl.py" "$HG/src/eagl_slots.txt" "$MESA_INC/../src/mapi/glapi/registry/gl.xml" \
  "$OBJ/exported-gl.txt" "$HG/src/eagl.c" > "$OBJ/eagl_gen.h"
$CC -O2 -g -w -I"$OBJ" -I"$HG/src" -I"$HG/include" -c "$HG/src/eagl.c" -o "$OBJ/hg_eagl.o"
$CC -O2 -g -Wall -I"$HG/src" -c "$HG/src/gl_hero.c" -o "$OBJ/hg_gl_hero.o"
$CC -O2 -g -Wall -c "$HG/src/ca_hooks.c" -o "$OBJ/hg_ca_hooks.o"
# iOS 18: the render server's GLES renderer (ca_server_hook.c, after Bergamota's); it does nothing on iOS 16's QuartzCore.
$CC -O2 -g -Wall -c "$HG/src/ca_server_hook.c" -o "$OBJ/hg_ca_server_hook.o"
# iOS 26 (23G90, iPhone12,1 cache): the same through QuartzCore's renderer()/new_metal_context (after ios-b1lte's);
# each hook checks its QuartzCore's words and does nothing on the other one.
$CC -O2 -g -Wall -c "$HG/src/ca_server_hook26.c" -o "$OBJ/hg_ca_server_hook26.o"
# hero_log first: its constructor sends stderr to the kernel log before eagl.c and the hooks write to it.
$CC -dynamiclib -o "$OUT/lib/libhakiosgl.dylib" "$OBJ"/{hero_log,hg_eagl,hg_gl_hero,hg_ca_hooks,hg_ca_server_hook,hg_ca_server_hook26,hero_backboardd,hero_prof}.o \
  -install_name @rpath/libhakiosgl.dylib \
  -framework CoreFoundation -framework IOKit -framework IOSurface -lobjc \
  -L "$OUT/lib" -lOSMesa.8 -Wl,-rpath,/private/var/herolte/lib -Wl,-undefined,error

# The CoreAnimation test links the SDK's OpenGLES and QuartzCore; EAGL_INJECT_LIB names the shim.
$CC -O1 -g -Wno-deprecated-declarations -fno-objc-arc -I"$HERE/src" "$HERE/test/eagl_ca_test.m" \
  -o "$OUT/eagl_ca_test" \
  -framework Foundation -framework CoreFoundation -framework CoreGraphics -framework IOSurface \
  -framework QuartzCore -framework OpenGLES
$CC -O2 -Wall -o "$OUT/hero-run" "$HERE/test/hero-run.c" -L "$OUT/lib" -ldrm.2 -lobjc -framework Foundation \
  -Wl,-rpath,/private/var/herolte/lib

$CC -O2 -Wall -dynamiclib -o "$OUT/lib/libherosb.dylib" "$HERE/src/herosb.c" -install_name @rpath/libherosb.dylib \
  -framework CoreFoundation -lobjc -L "$OUT/lib" -ldrm.2 -Wl,-rpath,/private/var/herolte/lib

$CC -O2 -Wall -dynamiclib -o "$OUT/lib/libheroapp.dylib" "$HERE/src/heroapp.c" -install_name @rpath/libheroapp.dylib \
  -framework Foundation -framework UIKit -framework CoreGraphics -framework ImageIO -framework IOSurface \
  -lobjc -L "$OUT/lib" -ldrm.2 -Wl,-rpath,/private/var/herolte/lib

# The front camera's capture device in mediaserverd (gpu/camera, from the Note FE port's gracerlte/camera, after the S9
# port's camera_device.c/camera_isp.c, MIT: LICENSE.HakiOS), loaded by libheroapp with the drop zone's cam.media = 1.
$CC -O2 -fblocks -Wall -Wno-unused-function -Wno-deprecated-declarations -dynamiclib -o "$OUT/lib/libnotefecam.dylib" \
  "$HERE/../camera/inject.c" "$HERE/../camera/camera_device.c" "$HERE/../camera/camera_isp.c" \
  -install_name @rpath/libnotefecam.dylib -framework CoreFoundation -framework CoreMedia -framework CoreVideo \
  -framework IOSurface -lobjc
codesign -s - -f "$OUT/lib/libnotefecam.dylib"

# The audio plug-in of mediaserverd, for hero-run to put in /System/Library/Audio/Plug-Ins/HAL/HakiosAudio.driver.
mkdir -p "$OUT/audio"
$CC -O2 -w -bundle -I"$HERE/../hakios-audio" -o "$OUT/audio/HakiosAudio" "$HERE/../hakios-audio/audio_plugin.c" \
  -framework CoreFoundation -lm
cp "$HERE/../hakios-audio/audio_plugin.plist" "$OUT/audio/Info.plist"
codesign -s - -f "$OUT/audio/HakiosAudio"

for f in "$OUT/lib/libheroeagl.dylib" "$OUT/lib/libhakiosgl.dylib" "$OUT/lib/libherosb.dylib" "$OUT/lib/libheroapp.dylib" "$OUT/eagl_ca_test" "$OUT/hero-run"; do
  codesign -s - -f "$f"
  otool -L "$f"
done
# hero-run asks LaunchServices and installd to register the system bundles and the staged apps.
codesign -s - -f --entitlements "$HERE/test/hero-run.entitlements" "$OUT/hero-run"

# hero-oslog (dropped as hero-run's test): iOS's own log, read from logd's store, into the kernel's log.
$CC -O2 -Wall -fobjc-arc -o "$OUT/hero-oslog" "$HERE/test/hero-oslog.m" -framework Foundation
codesign -s - -f --entitlements "$HERE/test/hero-oslog.entitlements" "$OUT/hero-oslog"

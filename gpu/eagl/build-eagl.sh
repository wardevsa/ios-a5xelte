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
$CC -dynamiclib -o "$OUT/lib/libhakiosgl.dylib" "$OBJ"/{hg_eagl,hg_gl_hero,hg_ca_hooks,hero_log,hero_backboardd,hero_prof}.o \
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

for f in "$OUT/lib/libheroeagl.dylib" "$OUT/lib/libhakiosgl.dylib" "$OUT/eagl_ca_test" "$OUT/hero-run"; do
  codesign -s - -f "$f"
  otool -L "$f"
done

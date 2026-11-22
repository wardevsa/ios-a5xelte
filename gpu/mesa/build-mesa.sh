#!/bin/bash
# Cross-build Mesa's Panfrost (Gallium + Midgard compiler) for the Galaxy
# S7's iOS 16 userland (plain arm64), inside OSMesa, over the HeroGPU
# libdrm stand-in. Runs on a macOS runner with Xcode (iphoneos SDK).
#
#   build-mesa.sh WORK OUT
#
# OUT gets lib/{libOSMesa.8,libglapi.0,libdrm.2}.dylib (install names
# @rpath/...) and osmesa-test (rpath /private/var/herolte/lib), all ad-hoc
# signed. Nothing of Apple's is in OUT.
set -euo pipefail

WORK=$(mkdir -p "$1" && cd "$1" && pwd)
OUT=$(mkdir -p "$2" && cd "$2" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
MESA_TAG=${MESA_TAG:-mesa-25.0.7}
LIBDRM_TAG=${LIBDRM_TAG:-libdrm-2.4.124}
MIN_IOS=16.0
SDK=$(xcrun --sdk iphoneos --show-sdk-path)
CC_IOS="xcrun --sdk iphoneos clang -arch arm64 -miphoneos-version-min=$MIN_IOS -isysroot $SDK"

cd "$WORK"
[ -d mesa ] || git clone -q --depth 1 --branch "$MESA_TAG" https://gitlab.freedesktop.org/mesa/mesa.git mesa
[ -d libdrm ] || git clone -q --depth 1 --branch "$LIBDRM_TAG" https://gitlab.freedesktop.org/mesa/drm.git libdrm
python3 "$HERE/patch-mesa.py" mesa

# Metal step M1 (docs/herolte-metal.md): the AIR frontend -- Apple's shader bitcode (.metallib) to NIR -- and
# libhakiosair, the compiler and dispatch library a Metal driver drives (src/compiler/air/air_metal.h), from
# Scion-Project/hackios-xnu-kernel (MIT, tools/mesa), with ios-b1lte's Panfrost fixes on top (BSD-2-Clause,
# userspace/mesa/air-b2l/apply.py). Both pinned: b1lte's apply.py checks the exact text of Scion's files at its pin.
# libhakiosair opens the GPU through drmOpenWithType("panfrost"), which herodrm.c answers with the T880. AIR=0: none.
AIR=${AIR:-1}
SCION_REF=${SCION_REF:-a6f4bc38aa244359cd365c976244a88c9d6b3304}
B2L_REF=${B2L_REF:-046d01e232af686cd68b65d08487e7e9d1a1028b}
fetch_at() {    # fetch_at DIR URL SHA SPARSE...: one commit, only the directories named
  local dir=$1 url=$2 sha=$3; shift 3
  [ -d "$dir/.git" ] && return 0
  git init -q "$dir"
  git -C "$dir" sparse-checkout set "$@"
  git -C "$dir" fetch -q --depth 1 --filter=blob:none "$url" "$sha"
  git -C "$dir" checkout -q FETCH_HEAD
}
if [ "$AIR" = 1 ] && [ ! -f mesa/.herolte-air ]; then
  fetch_at scion https://github.com/Scion-Project/hackios-xnu-kernel "$SCION_REF" tools/mesa
  fetch_at b2l https://github.com/malthiscode/ios-b1lte "$B2L_REF" userspace/mesa/air-b2l userspace/metal
  rm -rf mesa/src/compiler/air
  cp -R scion/tools/mesa/air mesa/src/compiler/air
  patch -s -d mesa -p1 < scion/tools/mesa/air-frontend.patch
  patch -s -d mesa -p1 < scion/tools/mesa/air-metal.patch
  python3 b2l/userspace/mesa/air-b2l/apply.py mesa/src/compiler/air
  # ours, on top: what iOS 18's shaders need (sincos, aggregates through calls and phis, function tables, packed
  # varyings), found against the root's own .metallib corpus on a host build
  python3 "$HERE/air-herolte.py" mesa/src/compiler/air
  m=mesa/src/gallium/targets/hakiosair/meson.build
  # driconf, which the target leaves out (b1lte B1L-0051); our install name, the drop zone's lib directory
  sed -i '' 's/dependencies : \[dep_m, idep_air, idep_mesautil,/dependencies : [dep_m, idep_air, idep_mesautil, idep_xmlconfig,/' "$m"
  sed -i '' 's#/redwood/lib/libhakiosair.dylib#@rpath/libhakiosair.dylib#' "$m"
  grep -q idep_xmlconfig "$m" && grep -q '@rpath/libhakiosair.dylib' "$m"
  touch mesa/.herolte-air
fi

# The libdrm stand-in, and a pkg-config file pointing Mesa at it.
mkdir -p drm-standin pc
$CC_IOS -O2 -Wall -fvisibility=hidden -dynamiclib \
  -install_name @rpath/libdrm.2.dylib \
  -I libdrm -I libdrm/include/drm -I mesa/include \
  -o drm-standin/libdrm.2.dylib "$HERE/herodrm.c" \
  -framework IOKit -framework CoreFoundation
ln -sf libdrm.2.dylib drm-standin/libdrm.dylib
cat > pc/libdrm.pc <<EOF
Name: libdrm
Description: HeroGPU libdrm stand-in
Version: ${LIBDRM_TAG#libdrm-}
Cflags: -I$WORK/libdrm -I$WORK/libdrm/include/drm
Libs: -L$WORK/drm-standin -ldrm
EOF

cat > ios-cross.txt <<EOF
[binaries]
c = ['xcrun', '--sdk', 'iphoneos', 'clang', '-arch', 'arm64']
cpp = ['xcrun', '--sdk', 'iphoneos', 'clang++', '-arch', 'arm64']
objc = ['xcrun', '--sdk', 'iphoneos', 'clang', '-arch', 'arm64']
ar = ['xcrun', '--sdk', 'iphoneos', 'ar']
strip = ['xcrun', '--sdk', 'iphoneos', 'strip']
ranlib = ['xcrun', '--sdk', 'iphoneos', 'ranlib']
pkg-config = 'pkg-config'

[built-in options]
c_args = ['-miphoneos-version-min=$MIN_IOS', '-isysroot', '$SDK']
cpp_args = ['-miphoneos-version-min=$MIN_IOS', '-isysroot', '$SDK']
objc_args = ['-miphoneos-version-min=$MIN_IOS', '-isysroot', '$SDK']
c_link_args = ['-miphoneos-version-min=$MIN_IOS', '-isysroot', '$SDK']
cpp_link_args = ['-miphoneos-version-min=$MIN_IOS', '-isysroot', '$SDK']
objc_link_args = ['-miphoneos-version-min=$MIN_IOS', '-isysroot', '$SDK']

[properties]
needs_exe_wrapper = true
pkg_config_libdir = '$WORK/pc'

[host_machine]
system = 'darwin'
subsystem = 'ios'
kernel = 'xnu'
cpu_family = 'aarch64'
cpu = 'arm64'
endian = 'little'
EOF

cd mesa
[ -d build ] || meson setup build --cross-file ../ios-cross.txt \
  --buildtype=release -Db_ndebug=true -Dprefix=/ \
  -Dgallium-drivers=softpipe,panfrost -Dvulkan-drivers= \
  -Dllvm=disabled -Dglx=disabled -Degl=disabled -Dgbm=disabled -Dplatforms= \
  -Dosmesa=true -Dopengl=true -Dgles1=disabled -Dgles2=enabled -Dshared-glapi=enabled \
  -Dshader-cache=disabled -Dvalgrind=disabled -Dlibunwind=disabled -Dzstd=disabled \
  -Dxmlconfig=disabled -Dbuild-tests=false -Dglvnd=disabled -Dlmsensors=disabled \
  -Dgallium-opencl=disabled -Dgallium-rusticl=false -Dgallium-xa=disabled \
  -Dgallium-vdpau=disabled -Dgallium-va=disabled -Dtools= -Dperfetto=false
ninja -C build -k 0
# not default targets (air-metal.patch: build_by_default false)
[ "$AIR" = 1 ] && ninja -C build src/gallium/targets/hakiosair/libhakiosair.dylib \
  src/gallium/targets/hakiosair/air_metal_test
cd ..

mkdir -p "$OUT/lib"
osmesa=$(ls mesa/build/src/gallium/targets/osmesa/libOSMesa.8*.dylib | head -1)
glapi=$(ls mesa/build/src/mapi/shared-glapi/libglapi.0*.dylib 2>/dev/null | head -1 || true)
cp "$osmesa" "$OUT/lib/libOSMesa.8.dylib"
[ -n "$glapi" ] && cp "$glapi" "$OUT/lib/libglapi.0.dylib"
cp drm-standin/libdrm.2.dylib "$OUT/lib/"
if [ "$AIR" = 1 ]; then
  cp mesa/build/src/gallium/targets/hakiosair/libhakiosair.dylib "$OUT/lib/"
  cp mesa/build/src/gallium/targets/hakiosair/air_metal_test "$OUT/air_metal_test"
  install_name_tool -add_rpath /private/var/herolte/lib "$OUT/air_metal_test"
fi

# @rpath install names, so the dylibs load from wherever they are installed.
for lib in "$OUT"/lib/*.dylib; do
  name=$(basename "$lib")
  install_name_tool -id "@rpath/$name" "$lib"
  for dep in $(otool -L "$lib" | awk 'NR > 1 { print $1 }'); do
    case "$dep" in
      /usr/lib/*|/System/*|@rpath/*) ;;
      *) install_name_tool -change "$dep" "@rpath/$(basename "$dep")" "$lib" ;;
    esac
  done
done

$CC_IOS -O2 -Wall -I mesa/include -o "$OUT/osmesa-test" "$HERE/osmesa-test.c" \
  -L "$OUT/lib" -lOSMesa.8 -ldrm.2 -Wl,-rpath,/private/var/herolte/lib
# hero_metal_test (docs/herolte-metal.md, M2): a pipeline given what its shaders declare, through rwa_*.
[ "$AIR" = 1 ] && $CC_IOS -O2 -Wall -I mesa/src/compiler/air -o "$OUT/hero_metal_test" "$HERE/hero-metal-test.c" \
  -L "$OUT/lib" -lhakiosair -Wl,-rpath,/private/var/herolte/lib

for f in "$OUT"/lib/*.dylib "$OUT/osmesa-test" $( [ "$AIR" = 1 ] && echo "$OUT/air_metal_test $OUT/hero_metal_test" ); do
  codesign -s - -f "$f"
  otool -L "$f"
done
# Metal M3: the device, the plug-in bundle and hero_mtl_test (gpu/metal), over the libhakiosair just built
[ "$AIR" = 1 ] && bash "$HERE/../metal/build-metal.sh" "$WORK" "$OUT"
ls -la "$OUT" "$OUT/lib"

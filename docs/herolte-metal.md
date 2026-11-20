# Metal on the Galaxy S7's Mali-T880 (Midgard)

Why: iOS 18's Core Animation still has the OpenGL path this port uses (gpu/hakios-gl, ca_server_hook.c), but more and
more of iOS draws only through Metal. The iOS 18 wallpaper (MercuryPoster: `default.metallib`, a 3D model `tori.obj`,
Metal shaders) stays black without it, and iOS 26's Core Animation has no OpenGL path at all.

## The base: Scion's Metal driver over Gallium

Two ports already run Metal on phone GPUs through Mesa:

- Scion-Project/hackios-xnu-kernel (MIT): `tools/mesa/air` reads Apple's shader bitcode (AIR, the LLVM modules of a
  `.metallib`) into NIR, and `air_metal.c` (`libhakiosair`) turns a Metal function into a Gallium compute or render
  state and runs it. Its contract with the Metal side is `air_metal.h` (`rwa_*`), which mentions nothing of the GPU:
  it opens whichever Gallium driver the kernel serves, by `drmOpenWithType("msm" | "panfrost")`.
  `userland/src/hakiosmetal_air.m` is the Metal device object (a Metal plug-in: `MTLAddDevice` wants
  `-initWithAcceleratorPort:`, MTLDevice and MTLDeviceSPI conformance, `-featureProfile`, `-maxBufferLength`,
  `-supportsVertexAmplificationCount:`; docs/metal.md section 10 there).
- malthiscode/ios-b1lte (Galaxy S10, Mali-G76 Bifrost, iOS 26; BSD-2-Clause): the same driver on Panfrost, with the
  fixes Panfrost needed in `userspace/mesa/air-b2l/apply.py` (shader info gathering, constant buffers as user buffers,
  pushable UBOs, ...), and the Metal plug-in loaded from `/System/Library/Extensions` through an `IOAcceleratorES`
  service announcing it.

Panfrost's Gallium driver covers Midgard (T860/T880) as well as Bifrost, and this port already runs Mesa 25.0.7's
Panfrost on the T880 for OpenGL, over `gpu/mesa/herodrm.c`. PanVK (Scion's other route) does not cover Midgard.

## Steps

1. **M1: Apple's shaders compiled for the T880.** `gpu/mesa/build-mesa.sh` adds the AIR frontend and builds
   `libhakiosair.dylib` and `air_metal_test` (`AIR=1`, the default). On the phone, through `hero-run`,
   `air_metal_test` reads MercuryPoster's own `default.metallib` (already in the root; no Apple file leaves the
   phone) with `RWA_SOFTWARE=0`: which functions compile for Midgard, which do not and why.
2. **M2: compute and draws on the T880** from `air_metal_test --draw...`, the results read back.
3. **M3: the Metal device.** Scion's `hakiosmetal_air.m` as a Metal plug-in for iOS 18's Metal.framework, and the
   kernel service that makes `MTLCreateSystemDefaultDevice` find it.
4. **M4: MercuryPoster** draws.

Core Animation stays on OpenGL until Metal is proven faster on this GPU.

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
   First run on the phone (boot-18k39, 2026-11-20): libhakiosair opened the GPU as "Mali-T880 (Panfrost)" and built
   MercuryPoster's `post` pipeline for Midgard; the other functions stopped in the AIR reader, which was written
   against iOS 16.5's and 26's shaders.

   **The host bench.** The same frontend on WSL (Mesa 25.0.7, softpipe), against all 196 `.metallib` files of the
   iOS 18 root (20335 modules; they stay on the PC, out of git): `air2nir --report` over the corpus, `--ll` to
   disassemble a function. softpipe goes through TGSI, which lacks scratch memory, some 64-bit and 8-bit opcodes and
   some texture types, so the bench's measure is "translates to NIR"; the Mali's compiler is the phone's to test.

   **gpu/mesa/air-herolte.py**, our changes on top of Scion's and ios-b1lte's, each found on a MercuryPoster shader
   and measured on the corpus (6936 modules translated before, 7083 after; crashes 7 -> 4, none of them ours):
   - `air.fast_sincos(x, ptr)`: the cosine written through a pointer (fluidity, pro24Main).
   - struct returns with array members flattened, one out-parameter per number (tori: a `float3x3` returned).
   - a table of functions: a function's address is its number, a call through one calls every pure candidate and
     selects (shippou's four materials).
   - phis of structs and arrays, one register per number (shippou's ray-hit struct around a loop).
   - booleans: 1-bit through calls, 32-bit words in and out of the stage interface.
   - packed varyings, first fit: torusVertex's 40-55 varyings in 12-16 slots instead of 40-55 (the T880 has 16).
   All 22 MercuryPoster functions translate.

   Second run on the phone (boot-18k40, with air-herolte.py): Midgard compiled `fluidity::sdfVertexShader` +
   `sdfFragmentShader` and the draw completed (exit 0), the first MercuryPoster pipeline to run on the T880. The
   others stopped inside `air_metal_test`, which feeds Apple's test shaders fixed shapes: `postFragment` declares a
   `texture3d` at slot 1, `fluidity::fragmentShader` a 256-byte buffer, `torusVertex` three stage-in attributes.
   `shippou::one::compute` (about 73K NIR instructions) kept the compiler at 199% CPU for minutes without finishing.
2. **M2: compute and draws on the T880.** `gpu/mesa/hero-metal-test.c` (`hero_metal_test`) builds a pipeline from
   what its functions declare, through `rwa_*` alone: textures of each declared kind and element type, 64 KB
   buffers, samplers, vertex attributes as `Float4` (switched to `Int4`/`UInt4` when the library says the shader
   wants integers). It times the compile and two draws, counts pixels against the clear colour and NaNs, and on a
   timeout prints a backtrace of where it was.

   On the T880 (boot-18k41..45), in order:
   - every render pipeline of MercuryPoster compiled (0.01-2.7 s) and drew (1-6 ms), and no pixel changed. Midgard's
     disassembly (`MIDGARD_MESA_DEBUG=shaders`) showed why: `postVertex` reads its corners from `quadVertices[6]`, an
     `addrspace(2)` constant with an initializer, which the frontend put in scratch and never wrote -- every vertex
     one point. air-herolte.py 8 writes a scratch global's initializer at the top of the entry point.
   - then the colours were wrong: Midgard's writeout takes 32-bit registers and the shaders' `half4` came back as
     two halves per float (`0.0078` = `0x3c00`, 1.0 as a half, in the high bits). air-herolte.py 10 widens a
     fragment shader's 16-bit `store_output`.
   - boot-18k45: **`postVertex` + `postFragment` draw the whole attachment with plausible colours** (a gradient,
     `0.04 0.04 0.50 1` at a corner, `0.47 0.53 0.50 1` at the centre; RGBA32Float and RGBA8Unorm agree).
     `fluidity` and `pro24` draw too; `fluidity::sdf` and `torus` with Apple's vertex stages draw nothing over the
     harness's made-up buffers (their positions come from matrices in those buffers), and `torusFragment` costs
     0.66 s for 32x32 pixels over them. Their real inputs come with M3.
   - `pro24MainFragment`'s own `filter::bicubic` sampler is sampled as linear (air-herolte.py 6); Midgard has no
     `b2i8` (Panfrost's algebraic pass makes it again from the frontend's `u2u8(b2i32)`, so Midgard lowers it after
     its boolean lowering: 9). `shippou::one::compute` then compiles further but stays more than 90 s in Midgard's
     register allocator (`mir_ra`): its NIR is about 73K instructions, its four materials inlined and selected.
3. **M3: the Metal device.** Done on boot-18k47 (2026-11-21).
   - Kernel (xnu 9198): the `IOAcceleratorES` HeroGPU already published (9100) names `MetalPluginName HeroMetal`,
     `MetalPluginClassName HeroMetalDevice`; `herometal=0` empties it again.
   - `gpu/metal/hero-metal-plugin.m`: `/System/Library/Extensions/HeroMetal.bundle`, installed by hero-run from the
     drop zone. Metal checks the class with `isSubclassOfClass:` (boot-18k46: an NSObject subclass got no call), so
     it is a `_MTLDevice`; it gives a device only to the processes named in `/private/var/herolte/metal.allow`, loads
     the driver only for them, and is never released when it declines (ios-b1lte B1L-0085..0087).
   - `gpu/metal/build-metal.sh`: the driver, `libhakiosmetal.dylib`, is ios-b1lte's Panfrost version of Scion's
     device (userspace/metal/scion at B2L_REF), its paths in the drop zone and its log in ours (`herodrm_log`).
   - boot-18k47, `hero_mtl_test`: `MTLCreateSystemDefaultDevice()` = "Mali-T880 (Panfrost) (Hakios)" in 0.16 s, a
     buffer written and read back, MercuryPoster's library (22 functions), the post pipeline in 0.04 s, two command
     buffers at status 4 (completed) in 3 and 1 ms, and **the four pixels identical to hero_metal_test's**.
4. **M4: MercuryPoster** draws.

Core Animation stays on OpenGL until Metal is proven faster on this GPU.

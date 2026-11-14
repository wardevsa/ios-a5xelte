# HakiOS EAGL bridge (Galaxy S7 port)

`src/eagl.c`, `src/eagl_slots.txt`, `src/hakios.gl.h` and `mkeagl.py` are HakiOS's user-space
OpenGL ES bridge for CoreAnimation's render server, unchanged:
https://github.com/oosexgang/hackios-xnu-kernel (`userland/`), MIT License,
Copyright (c) 2025-2026 the HakiOS authors (full text in `LICENSE.hakios`). The same file
drives Topaz's port (MakrSas/ios-topaz, `userland/gpu/eagl.c`).

Ours (MIT):

- `src/gl_hero.c`: `hakios.gl.h` over this port's libOSMesa (Panfrost on the Mali-T880 over
  HeroGPU, `gpu/mesa`), in place of HakiOS's `gl_osmesa.c`.
- `include/IOKit/IOKitLib.h`: the IOKit declarations `eagl.c` uses (the iOS SDK has no IOKit headers).

`gpu/eagl/build-eagl.sh` builds it as `lib/libhakiosgl.dylib`, together with `gpu/eagl/src/hero_log.c`,
`hero_backboardd.c` and `hero_prof.c`. The kernel inserts `lib/libheroeagl.dylib` into backboardd
(`bsd/dev/herolte_gl.c`): to run this bridge instead of Bergamota's, drop it under that name
(`tools/herolte-drop.py ... lib/libheroeagl.dylib=out/lib/libhakiosgl.dylib`). Its switches are
kernel boot-args (`gltrace=`, `glcensus=1`, `glplain=0`, `glcopy=1`, ...; see the top of `src/eagl.c`).

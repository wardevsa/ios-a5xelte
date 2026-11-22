xnu-12377.121.6 (iOS 26) series for HEROLTE, built by the xnu workflow on branch herolte-ios26 (MACOS_VERSION 26.5, macos-26, Xcode 26.1, KDK 26.5 25F71).

- `0001`-`1130`: Bergamota's `xnu/patches-12377` (ry-diffusion/Bergamota, its own port of the 11215 series to xnu-12377, see its docs/XNU12377_MIGRATION.md), unchanged except the staging scripts `0019`, `0020`, `0026`, `0027`, widened to A5XELTE and HEROLTE as in `patches-11215`.
- `9001`-`9198`: the herolte series of `patches-11215`, carried over by 3-way merge: the 11215 tree as CI builds it (xnu-11215.81.4 + dxb 15.0 + patches-11215, one commit per 9NNN patch) cherry-picked onto xnu-12377.121.6 + dxb 26.0 + the Bergamota series. 179 of 197 picked cleanly; resolved by hand:
  - 9001, 9165 `arm_vm_init.c`: `mt_early_init`/`arm_set_user_tbi` left that spot in 12377; only the A5XELTE condition and the early mark stay.
  - 9003, 9041 `MakeInc.def`: A5XELTE/HEROLTE added to 12377's machine list (T6041, T6050, T8142 are new).
  - 9004 `sleh.c`: `INTERRUPT_MASKED_DEBUG_END()` is `ml_interrupt_masked_debug_end()` in 12377; GICv2 EOI kept.
  - 9015 `zalloc.c`, 9126 `sched_clutch.c`, 9086 `sweet_amfi.c` (next to Bergamota's 1007 LWCR answer): context only.
  - 9025, 9036, 9061, 9063, 9124 `SweetFramebuffer.cpp`: our DECON driver replaces Bergamota's MDP one outright; Bergamota's only 12377 change there (1008, boot-arg sweetbootlog_keep) is SWEET debugging and is not carried.
  - 9030 `kern_core.c`: the coredump default moved up the file in 12377; widened there.
  - 9043 `vm_shared_region.c`: 12377's new config map gets the same code-signing policy as the shared region submap.
  - 9065 `vm_kern.c`: the KMEM log uses 12377's `free_size`; 12377's own hole-lookup panic kept.
  - 9079 `sched_prim.c`: the realtime run-queue code moved to `sched_rt.c`; the fast-core preference for realtime threads now lives in `pset_choose_processor_for_realtime_thread()` (`sweet_fast_map` no longer static).
  - 9150 (io_map 64 MiB) is gone: 12377's `io_map` allocates from `kernel_map` after startup, with no fixed submap.
  - 9157 `machine_routines_asm.s`: v80emu routines after 12377's `_copyout_atomic64` epilog.
- `9199`: Bergamota's 12377-only fixes that iOS 26 needs on the S7 as well (no TPRO, no PAC, no Apple fuses, scan-out buffers outside gDram), widened from `ARM64_BOARD_CONFIG_SWEET` to `ARM64_BOARD_CONFIG_A5XELTE`: 1000 (prod-fused stub, Tightbeam), 1001 (WCOMB), 1003, 1004 (writable shared region), 1005, 1016, 1017/1018 (HID queue). 1002 is not: the S7 has its own persistent log, and 9167 already waits for it before the initproc panic. 1006 and 1019 apply to every config.

Applying the 9NNN files in order onto the base reproduces the merged tree exactly (checked by tree hash).

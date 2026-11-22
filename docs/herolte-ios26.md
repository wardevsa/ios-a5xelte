# iOS 26 on the Galaxy S7 (plan, 2026-11-22)

Decided by the owner after the iOS 18 Metal work (docs/herolte-metal.md): go to iOS 26. Reference port:
malthiscode/ios-b1lte (Galaxy S10, Exynos 9820, Mali-G76 Bifrost), which boots the unmodified iOS 26 userland
(IPSW 23G90) on an XNU built from Apple's source with the iOS 26.5 Kernel Debug Kit.

## What is the same and what is not

| | ios-b1lte (S10) | this port (S7) |
| --- | --- | --- |
| CPU | Exynos 9820, ARMv8.2 (Mongoose M4, A75, A55) | Exynos 8890, **ARMv8.0** (Mongoose M1, A53): no LSE atomics, no RCpc, no FP16 arithmetic, no PAC |
| arm64e beyond the CPU | emulated in the kernel (beyond v8.2) | already done for iOS 18 beyond **v8.0**: `tools/ios18/v80strip*.py` rewrites the dyld cache, `v80emu` traps the rest |
| GPU | Mali-G76, Bifrost (Panfrost's Bifrost compiler) | Mali-T880, **Midgard** (Panfrost's Midgard compiler): every Metal fix of ours so far was Midgard's |
| Boot chain | S-Boot -> UEFI -> XnuLoader | S-Boot -> our BOOT image (`tools/herolte-pack-boot.py`, payload with the ADT) |
| First screen | Core Animation's **CPU renderer** (no GPU needed), GLES then Metal later | the same order |

## Phases

1. **P0, groundwork.** Which IPSW: b1lte's 23G90 (iPhone 16 Pro Max, an A18 dyld cache) or the oldest iPhone iOS 26
   supports (iPhone 11, A13), whose cache needs less beyond ARMv8.0 -- measured by running `tools/dsc-tramp-space.py`
   and `v80strip` over both caches. The XNU tag for iOS 26 and whether CI's macOS runner has a KDK for it.
2. **P1, kernel.** XNU for iOS 26 booting on the S7 to launchd: the herolte series (197 `9NNN` patches on xnu-11215)
   carried over -- most are drivers in their own files (HeroGPU, DECON display, UFS, touch, Wi-Fi, power/TMU, persistent
   log, v80emu); the core ones (pmap, scheduler, platform expert) by hand, with b1lte's `xnu-overlay` and patches as the
   reference for what iOS 26 itself needs (arm64e runtime, AMFI, HFS root).
3. **P2, root.** The iOS 26 root on USERDATA (HFS+, journaled, as iOS 18's), the dyld cache through `v80strip`, the
   same tuning (`tools/herolte-tune-ios-root.sh`: daemons off, wallpapers PNG). Target: SpringBoard on the CPU renderer.
4. **P3, GPU.** First GLES through our bridge (gpu/hakios-gl, as b1lte's `b2l_gl=1` fallback), then Metal for the window
   server: the M1-M4 work of docs/herolte-metal.md carries over (AIR frontend, the device, HeroMetal.bundle, drawables).

## Kept

The iOS 18 root image and BOOT images stay on the PC (`priv/`), so the phone can go back to iOS 18 at any time.

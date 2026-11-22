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

## P0 results (2026-11-22)

**Kernel.** iOS 26.5's XNU is `xnu-12377.121.6` (apple-oss-distributions/xnu; b1lte pins the same commit,
ac9718f). darwin-xnu-build takes it with `MACOS_VERSION=26.5`: it clones that tag and fetches the KDK
"26.5 build 25F71" from the dortania manifest on its own. Xcode: the `macos-26` arm64 runner has 26.0.1-26.6
(26.6 the default); `macos-15(-intel)`, which builds xnu-11215 today, stops at 16.2. b1lte builds with Xcode 27.1
on a Mac and `SDKVERSION=26.5 RC_DARWIN_KERNEL_VERSION=25.5.0 BTI_BUILD=0 PLATFORM=iPhoneOS`.

**IPSW: iPhone 11 (iPhone12,1), 23G90 (iOS 26.6.2), 9.1 GB.** 23G90 exists for every iOS 26 iPhone (16 Pro
Max 10.6 GB, SE 2020 9.1 GB). `ipsw extract --dyld --remote` pulls only the cache (5.9 GB each, no full IPSW).
`tools/dsc-tramp-space.py` over both caches (numbers only):

| | iOS 18.7.8 (22H352, XR) | iOS 26 iPhone 11 (A13) | iOS 26 16 Pro Max (A18) |
| --- | --- | --- | --- |
| images | | 4305 | 4317 |
| LSE sites | 463,816 | 828,714 | 829,081 |
| LDAPR | 93,670 | 133,388 | 134,175 |
| FP16 | 22,574 | 25,530 | 25,534 |
| FCMA | 2,455 | **25,274** | 25,278 |
| SHA3/SHA512, FJCVTZS, dotprod | 848, 474, - | 1,192, 535, 993 | the same |
| free padding between images | 7.8 MiB | 8.7 MiB | 8.7 MiB |
| routines that fit there (64 B) | 117,762 | 138,313 | 138,834 |

The two iOS 26 caches are the same code (one arm64e baseline for every device; within 0.05 %), so a newer model
(14 Pro, 16 Pro Max) gains nothing; the iPhone 11 is the smaller IPSW and the XR's successor (same screen class
as the iOS 18 tuning). Against iOS 18: 1.8x the atomics, and FCMA (FCMLA/FCADD) is new at scale -- 10x, it needs
FP routines like `fp16.py` or v80emu. Most sites are again in WebCore, WebKit, Recon3D, AppleCV3D, JavaScriptCore
and libusd; the padding only holds a sixth, so `v80strip_cache.py`'s priority order (runtime and UI first, the
`__text` of WebGPU as space, the rest to v80emu) carries over.

## P1 progress (2026-11-22)

Branch `herolte-ios26` (worktree `C:\Users\amanc\herolte\ios26`, commit `2b7366f`), `xnu/patches-12377`:
Bergamota's own xnu-12377 series (271 patches; it boots iOS 26.6.2 as iPhone12,1 on its phone) as the base, our 197
patches carried over by 3-way merge from the 11215 tree as CI builds it (179 clean, 17 by hand, 9150 obsolete), and
9199 widening Bergamota's 12377-only fixes to A5XELTE/HEROLTE. Details: `xnu/patches-12377/README.md` there. Bench in
WSL `/root/ios26/k` (`merge/` repo: tags old-base/old-top, new-base/new-top).
Not built yet: the push started no run, and a manual dispatch got "Actions has been disabled for this repository"
(the repository's own setting still says enabled).

Still to do for a boot, from Bergamota's first iOS 26 boots: the ADT needs a 256-byte `/chosen/random-seed` and
`kernel-ctrr-to-be-enabled` = 1 (our `tools/mkpayload.py` ADT), and the root's `TEXT_STUBS` sub-caches have `BRAA x16, x17`
stubs to rewrite (Bergamota's `pacstrip_cache.py --stubs`; our v80emu would trap each one).

## Kept

The iOS 18 root image and BOOT images stay on the PC (`priv/`), so the phone can go back to iOS 18 at any time.

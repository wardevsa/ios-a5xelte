# Trying iOS 16 on the Galaxy S7 (SM-G930F)

Experimental. This **erases USERDATA** (all Android data) and replaces the
BOOT partition. You need a flat **SM-G930F (Exynos 8890)**, an unlocked
bootloader (OEM unlock), **TWRP** and `adb` on a PC. Other S7 variants
(G930FD, G935F edge, Snapdragon models) are untested and have different
hardware.

What works (November 2026): the iPhone X iOS 16.7.16 userland to the home
screen and apps, **GPU acceleration** (Mali-T880 through OpenGL ES, double
buffered display), all 8 cores, touch, buttons, battery, **Wi-Fi (WPA2)**,
**the loudspeaker** (ringtones, keyboard clicks, media) and 2 GiB of RAM
(about 3 GiB with the RAM banks, patches 0326-0329). Not working: modem, Bluetooth,
cameras, sensors, sleep, Metal (the Today view and Control Center blurs are
black), the stock iOS 16 wallpaper (others work).

Nothing of Apple's, Samsung's or Broadcom's is in this repository, and none
of it may be uploaded publicly:

- the iOS root image and the Apple device tree come from Apple's public IPSW,
  built by you in a **private** repository (step 2);
- the Wi-Fi firmware comes from **your own phone's** VENDOR partition (step 5);
- the BOOT image keeps **your own phone's** Samsung header, ramdisk and DTBs.

## 1. Kernel (public, GitHub Actions)

1. Fork this repository and enable Actions.
2. Push to the `herolte` branch, or run the **xnu** workflow by hand
   (`MACHINE_CONFIG` = `HEROLTE`, the default).
3. Download the `xnu-kernel-macos-15-intel` artifact; it contains
   `kernel.development.herolte`.

## 2. iOS root image (private repository)

1. Create a **private** repository and push this branch to it as
   `ios-root-build`. The `ios-root` workflow refuses to run in a public one.
2. It downloads the iPhone X (iPhone10,3) iOS 16.7.16 IPSW members, stages a
   20 GiB HFSX root (`tools/a5xelte-stage-ios-root.sh`, then
   `tools/herolte-tune-ios-root.sh`) and publishes a private release with
   `root.img.gz.part00..02`, `d22ap.adt` and `SHA256SUMS`.
3. Download those files. Put `d22ap.adt` in `research/ipsw-x/` (gitignored).

## 3. GPU userland (public, GitHub Actions)

Run the **mesa-ios** workflow (it runs on every push to `gpu/`) and download
the `mesa-ios` artifact: Mesa's Panfrost for the Mali-T880, the EAGL bridge,
the SpringBoard and app helpers, the audio plug-in and `hero-run`.

## 4. Loader, device tree and BOOT image

```sh
# Loader (any aarch64 GCC; e.g. Arm GNU Toolchain aarch64-none-elf)
cd shim/herolte && CROSS=aarch64-none-elf- sh build.sh && cd ../..

# Apple device tree with the S7 hardware: 2 GiB of the second DRAM bank,
# iOS drawing an iPhone 8 screen (750x1334, scaled to the panel by the GPU).
# Needs research/ipsw-x/d22ap.adt.
python3 tools/mkadt_herolte.py herolte.adt --bank2 --bank2-mb 2048 --iphone8

# Recommended (kernel with patches 0326-0329): about 1 GiB more RAM from the
# first DRAM bank (the pieces Samsung does not reserve).
python3 tools/herolte-adt-ram-banks.py herolte.adt herolte-3g.adt
```

The boot arguments in daily use (they must stay under 608 characters):

```sh
CMDLINE="heroaudio=3 heroquantum=500 debug=0xc keepsyms=1 -noprogress rd=ufsroot0 \
ufsroot=USERDATA ufsrw=1 rootrw=1 cs_enforcement_disable=1 unentitled_ios_sim_launch=1 \
ignition_level=1 launchd_unsecure_cache=1 wdt=-1 -wdt_no_pmu wdt_test=no_user_checkin \
a5fb_keep_on=1 a5fb_noconsole=1 a5fb_perf=1 a5fb_hz=60 sweetfb_native=1 sweetfb_scale=1 \
sweetfb_lw=750 sweetfb_lh=1334 sweetfb_gpu=1 cpus=8 herogl=1 sweettop=1 \
vm_compression_limit=98304 vm_compressor=2 \
heronoexec=vmd,bluetoothd,searchd,ReportCrash,aggregated,analyticsd,cloudd,homed,driverkitd \
glsb3=1 herogpu_mhz=650 herocpu_mhz=2288 herosb=1 sweetsample=-"

python3 tools/mkpayload.py kernel.development.herolte herolte.adt payload.bin --cmdline "$CMDLINE"
```

Keep `-noprogress`: a boot line without it panicked early (not yet understood).

With patch 0330 the Mongoose cores go back to the bootloader's 728 MHz while
the screen is off (Power) and while the battery is at 42 C or more
(`herohot=N` changes it); `heropower=0` turns that off.

In TWRP, save your current BOOT first (keep it: it is your way back to
Android), then build the XNU BOOT image from it (the Samsung header and DTBs
are kept):

```sh
adb shell dd if=/dev/block/sda5 of=/tmp/boot-stock.img
adb pull /tmp/boot-stock.img

python3 tools/herolte-pack-boot.py pack boot-stock.img \
  shim/herolte/out/xnu_boot.Image xnu-boot.img \
  --append payload.bin --partition-size 41943040
```

## 5. Drop zone: GPU libraries, audio, Wi-Fi

The kernel copies a small package from the end of USERDATA into
`/private/var/herolte/` on every boot (`tools/herolte-drop.py`). Gather it in
a folder `drop/` from the `mesa-ios` artifact (`M/` below) and your phone.

Wi-Fi firmware, from **your** phone's VENDOR partition (read only, in TWRP):

```sh
adb shell "mkdir -p /tmp/ven && mount -o ro /dev/block/sda16 /tmp/ven"
adb pull /tmp/ven/etc/wifi/bcmdhd_sta.bin_c0_plus_blob drop/wifi/fw.bin
adb pull /tmp/ven/etc/wifi/bcmdhd_clm.blob            drop/wifi/clm.blob
adb pull /tmp/ven/etc/wifi/nvram.txt_c0_plus          drop/wifi/nvram.txt
adb shell umount /tmp/ven
```

Your network: `drop/wifi/network.txt` with the network's name on the first
line and its WPA2 passphrase on the second (the passphrase is never logged).
**Do not commit this file.**

Small settings files (`printf` them into `drop/`):

| File | Contents | Why |
| --- | --- | --- |
| `gl.env` | `HERO_LOG_MAX=8000` `PAN_MESA_DEBUG=nocrc` `HERO_ASYNC=1` `CA_FORCE_TIMER=1`, one a line | backboardd's OpenGL ES |
| `test.env` | `EAGL_INJECT_LIB=/private/var/herolte/none` | the boot-time test does nothing |
| `disabled.list` | `tools/herolte-disabled.list` | launchd jobs that only cost CPU here |
| `wallpaper.off` | `off` | use iOS's own wallpapers, not the drop zone's picture |
| `gestures.off` | `off` | Home button navigation (gestures bring a red status bar) |

Then write the package (TWRP, `/data` unmounted):

```sh
python3 tools/herolte-drop.py adb \
  autorun=M/hero-run test=M/eagl_ca_test gl.env=drop/gl.env test.env=drop/test.env \
  disabled.list=drop/disabled.list wallpaper.off=drop/wallpaper.off gestures.off=drop/gestures.off \
  lib/libdrm.2.dylib=M/lib/libdrm.2.dylib lib/libOSMesa.8.dylib=M/lib/libOSMesa.8.dylib \
  lib/libheroeagl.dylib=M/lib/libhakiosgl.dylib lib/libherosb.dylib=M/lib/libherosb.dylib \
  lib/libheroapp.dylib=M/lib/libheroapp.dylib \
  audio/HakiosAudio=M/audio/HakiosAudio audio/Info.plist=M/audio/Info.plist \
  wifi/fw.bin=drop/wifi/fw.bin wifi/clm.blob=drop/wifi/clm.blob \
  wifi/nvram.txt=drop/wifi/nvram.txt wifi/network.txt=drop/wifi/network.txt
```

Apps: add `app=Foo.ipa` (or `app=Foo.app`, a folder) to the same command.
On the next boot hero-run moves each app to `/Applications` and registers
it; its icon shows on the home screen. Only apps that are **not
encrypted** run here: open-source apps and your own builds (an `.ipa`
exported from Xcode, the IPAs open-source projects publish). App Store
downloads are encrypted with FairPlay, which needs Apple's hardware keys and
servers; `herolte-drop.py` refuses them, as it refuses binaries without
plain arm64 code (arm64e only). The App Store app itself cannot sign in or
install anything on this port. The package holds 128 MiB in all.

`lib/libheroeagl.dylib` is **`libhakiosgl.dylib`** of the artifact: with
`herogl=1` the kernel puts HakiOS's EAGL bridge into backboardd under that
name.

## 6. Flash (TWRP)

Unmount `/data` in TWRP (Mount menu) first. Check the partitions on your
phone (`ls -l /dev/block/platform/155a0000.ufs/by-name/`): on the tested
phone BOOT is `sda5` and USERDATA is `sda18`.

```sh
# iOS root into USERDATA (64 MiB chunks, each verified by SHA-256;
# resumable with --state; --diff rewrites only changed chunks)
python3 tools/herolte-flash-root.py adb root.img.gz.part00 root.img.gz.part01 \
  root.img.gz.part02 --state flash.state

# BOOT, checked before rebooting
adb push xnu-boot.img /tmp/boot.img
adb shell "dd if=/tmp/boot.img of=/dev/block/sda5 bs=1048576 conv=fsync"
adb shell "head -c $(stat -c %s xnu-boot.img) /dev/block/sda5 | sha256sum"; sha256sum xnu-boot.img
adb reboot
```

The first boot takes several minutes. Wi-Fi joins `network.txt` by itself
about a minute after the home screen; the Wi-Fi icon shows in the status bar.

## 7. Logs

The kernel keeps its console in the last 4 MiB of USERDATA. Back in TWRP
(Power + Volume Down, then Power + Volume Up + Home):

```sh
python3 tools/herolte-log-pull.py adb boot.txt
```

Please attach this log to an issue with a photo of the screen. Read it
first: the passphrase is never logged, but app and daemon messages and the
names of nearby networks can be in it.

## Back to Android

Write your saved `boot-stock.img` back to BOOT and format Data in TWRP.

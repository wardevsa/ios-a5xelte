#!/usr/bin/env python3
"""Add /chosen/hakios-ram-banks to a herolte ADT (patch 0326: XNU's RAM in several banks).

  herolte-adt-ram-banks.py IN.adt OUT.adt [--only N]

The first bank must be the boot bank exactly (dram-base/dram-size, as boot_args gets them). The others are the
pieces of the first DRAM bank (0x80000000 + 0x7e400000, the stock DTB's /memory) that neither Samsung's
/reserved-memory (TIMA, gpu_crc, camera, modem, secure camera; its 'reusable' crypto, video and gpu_buffer areas are
used, as Linux does when no protected video plays) nor this port use: S-Boot's load area and the kernel's private blocks up to 0x92000000
(Wi-Fi rings 0x8f000000, GPU 0x8fc00000-0x90000000, second panel buffer 0x91000000), the ECT that S-Boot leaves at
0xa0000000 and the scaled default surface there, and the panel at 0xe2a00000. Linux (and TWRP) use all of them as
ordinary RAM, so none is TrustZone's. Also left out: the areas S-Boot names on Linux's command line rather than in
the DTB (ess_setup, sec_tima_log, sec_avc_log, auto_summary_log; see EXTRA); check TWRP's /proc/cmdline on your phone.
"""
import argparse, os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adt  # noqa: E402

EXTRA = [
    # Not from 0x92000000: S-Boot's own command line (TWRP's /proc/cmdline, not the DTB) has ess_setup=0x91200000
    # (Exynos snapshot), sec_tima_log=0x200000@0x92e02000 (written by TIMA/RKP above the kernel), sec_avc_log at
    # 0x93004000 and auto_summary_log at 0x93088000. With them inside a bank, iOS reached its UI and then
    # pmap_destroy's tt_entry_free assertion failed: page tables written behind the kernel's back.
    (0x94000000, 0xa0000000),   # 192 MiB
    (0xa0800000, 0xb1000000),   # 264 MiB  (ECT + default surface below, TIMA above)
    # Up to gpu_crc (no-map): crypto and video_* from 0xc0000000 are 'reusable' (CMA), ordinary RAM for Linux unless
    # Android makes them secure for protected video, which nothing does here.
    (0xb1200000, 0xcd000000),   # 446 MiB  (gpu_crc above)
    (0xcd800000, 0xd0800000),   #  48 MiB  (gpu_buffer, 'reusable'; camera above)
    (0xdec00000, 0xe2a00000),   #  62 MiB  (camera below, panel above)
    (0xe3a00000, 0xf0000000),   # 198 MiB  (modem above)
    (0xf8800000, 0xfc000000),   #  56 MiB  (secure camera above)
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('inp'); ap.add_argument('out')
    ap.add_argument('--only', type=int, default=len(EXTRA), help='use only the first N extra pieces')
    a = ap.parse_args()
    root, _ = adt.parse(open(a.inp, 'rb').read())
    chosen = next(c for c in root.children if c.name == 'chosen')
    base, = struct.unpack('<Q', chosen.prop('dram-base'))
    size, = struct.unpack('<Q', chosen.prop('dram-size'))
    banks = [(base, size)] + [(s, e - s) for s, e in EXTRA[:a.only]]
    for b, n in banks:
        assert b % 0x4000 == 0 and n % 0x4000 == 0, hex(b)
    value = b''.join(struct.pack('<QQ', b, n) for b, n in banks)
    chosen.props = [p for p in chosen.props if p[0] != 'hakios-ram-banks']
    chosen.props.append(('hakios-ram-banks', 0, value))
    open(a.out, 'wb').write(adt.serialize(root))
    extra = sum(n for _, n in banks[1:])
    print(f'{len(banks)} banks: boot {base:#x}+{size >> 20} MiB, extra {extra >> 20} MiB, total {(size + extra) >> 20} MiB')


if __name__ == '__main__':
    main()

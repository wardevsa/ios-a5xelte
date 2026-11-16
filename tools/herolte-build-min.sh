#!/bin/bash
# Builds and verifies one BOOT candidate from a kernel and a boot line; optionally writes it (the usual flasher checks).
#   herolte-build-min.sh KERNEL CMDLINE_FILE OUTDIR NAME [--flash]
# CMDLINE_FILE holds the boot line (one line). Inputs ADT, loader and stock BOOT default to the device-day paths and can
# be overridden with HEROLTE_ADT, HEROLTE_LOADER, HEROLTE_STOCK_BOOT. OUTDIR/NAME.* must not exist. Without --flash
# nothing touches a phone. Prints the image SHA-256 and the verifier count; exits 1 on any FAIL.
set -euo pipefail
[[ $# -ge 4 ]] || { echo "usage: $0 KERNEL CMDLINE_FILE OUTDIR NAME [--flash]" >&2; exit 2; }
K=$1 C=$2 O=$3 N=$4 FLASH=${5:-}
T=$(cd "$(dirname "$0")" && pwd)
B=${HEROLTE_DEVICE_DAY:-$HOME/HackiOS/builds/device-day}
A=${HEROLTE_ADT:-$B/boot-candidates-n2/embedded.adt}
L=${HEROLTE_LOADER:-$B/loader-clang/xnu_boot.Image}
S=${HEROLTE_STOCK_BOOT:-$HOME/HackiOS/backups/device-herolte/2026-11-12/BOOT.img}
for f in "$K" "$C" "$A" "$L" "$S"; do [[ -f $f ]] || { echo "missing $f" >&2; exit 2; }; done
[[ -z $FLASH || $FLASH == --flash ]] || { echo "unknown option $FLASH" >&2; exit 2; }
mkdir -p "$O"
for ext in img payload.bin cmdline.txt verify.txt; do [[ ! -e $O/$N.$ext ]] || { echo "refusing to overwrite $O/$N.$ext" >&2; exit 3; }; done
CMD=$(tr -d '\n' < "$C")
(( ${#CMD} <= 606 )) || { echo "boot line has ${#CMD} characters (limit 606: the verifier wants room for the NUL)" >&2; exit 4; }
printf '%s\n' "$CMD" > "$O/$N.cmdline.txt"
python3 -I "$T/mkpayload.py" "$K" "$A" "$O/$N.payload.bin" --cmdline "$CMD" > "$O/$N.mkpayload.out"
python3 -I "$T/herolte-pack-boot.py" pack "$S" "$L" "$O/$N.img" --append "$O/$N.payload.bin" --partition-size 41943040 > "$O/$N.pack.out"
# expect every key=value of the line that matters for the phone's state
EXPECT=()
for a in ufsrw=1 rootrw=1 herolog=1 sweetfb_lw=750; do [[ " $CMD " == *" $a "* ]] && EXPECT+=("--expect-arg=$a"); done
rc=0
python3 -I "$T/herolte-verify-boot.py" "$O/$N.img" --kernel "$K" --loader "$L" --stock "$S" "${EXPECT[@]}" > "$O/$N.verify.txt" || rc=$?
SHA=$(sha256sum "$O/$N.img" | cut -d' ' -f1)
echo "image $O/$N.img sha256 $SHA  verifier: $(grep -c '^PASS' "$O/$N.verify.txt") PASS, $(grep -c '^FAIL' "$O/$N.verify.txt") FAIL, line ${#CMD} chars"
(( rc == 0 )) || { grep '^FAIL' "$O/$N.verify.txt" >&2; exit 1; }
if [[ $FLASH == --flash ]]; then
  "$T/herolte-flash-boot.sh" "$O/$N.img" "$SHA" --execute | tee "$O/$N.flash.out"
fi

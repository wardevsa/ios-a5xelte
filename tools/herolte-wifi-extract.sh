#!/bin/bash
# Copies the Wi-Fi firmware files of THIS phone out of its VENDOR partition, read-only, from TWRP.
#   herolte-wifi-extract.sh ADB OUTDIR            # dry run: prints what it would do, touches nothing
#   herolte-wifi-extract.sh ADB OUTDIR --execute  # mounts VENDOR read-only, pulls three files, unmounts
# Files (docs/herolte-howto.md section 5): bcmdhd_sta.bin_c0_plus_blob -> fw.bin, bcmdhd_clm.blob -> clm.blob,
# nvram.txt_c0_plus -> nvram.txt. They are the phone's own and may carry its identity: OUTDIR gets mode 700, files 600,
# and they must stay out of git. Nothing is ever written to the phone except the temporary mount point /tmp/ven.
set -euo pipefail
[[ $# == 2 || $# == 3 ]] || { echo "usage: $0 ADB OUTDIR [--execute]" >&2; exit 2; }
ADB=$1 OUT=$2 EXEC=${3:-}
[[ -z $EXEC || $EXEC == --execute ]] || { echo "unknown option $EXEC" >&2; exit 2; }
DEV=/dev/block/platform/155a0000.ufs/by-name/VENDOR
declare -A MAP=([bcmdhd_sta.bin_c0_plus_blob]=fw.bin [bcmdhd_clm.blob]=clm.blob [nvram.txt_c0_plus]=nvram.txt)
run() { if [[ $EXEC == --execute ]]; then "$@"; else echo "DRY: $*"; fi; }
if [[ $EXEC == --execute ]]; then
  "$ADB" devices | grep -q recovery || { echo "no phone in recovery" >&2; exit 1; }
  "$ADB" shell "test -e $DEV" || { echo "$DEV not found: refusing to guess a partition" >&2; exit 1; }
  if "$ADB" shell "mount" | grep -q "$("$ADB" shell "readlink -f $DEV" | tr -d '\r')"; then echo "VENDOR already mounted: refusing" >&2; exit 1; fi
fi
run mkdir -p "$OUT"; run chmod 700 "$OUT"
run "$ADB" shell "mkdir -p /tmp/ven && mount -o ro $DEV /tmp/ven"
if [[ $EXEC == --execute ]]; then
  "$ADB" shell "grep ' /tmp/ven ' /proc/mounts" | grep -q '[ ,(]ro[ ,)]' || { "$ADB" shell "umount /tmp/ven" || true; echo "mount is not read-only: aborted" >&2; exit 1; }
fi
for src in "${!MAP[@]}"; do run "$ADB" pull "/tmp/ven/etc/wifi/$src" "$OUT/${MAP[$src]}"; done
run "$ADB" shell "umount /tmp/ven"
if [[ $EXEC == --execute ]]; then chmod 600 "$OUT"/*; (cd "$OUT" && sha256sum fw.bin clm.blob nvram.txt | tee SHA256SUMS); fi

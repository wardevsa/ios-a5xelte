#!/bin/bash
# Build a READ-ONLY N2 BOOT candidate on the PC and verify it with herolte-verify-boot.py. Never touches a phone or a block device.
#   herolte-build-n2.sh KERNEL ADT LOADER STOCK_BOOT OUTDIR NAME
# OUTDIR must not contain NAME.img (nothing is overwritten). Writes NAME.img, NAME.payload.bin, NAME.cmdline.txt,
# NAME.verify.txt (full PASS/FAIL output) and NAME.PROVENANCE.txt (inputs, SHA-256, tool commit, commands).
set -euo pipefail
[[ $# == 6 ]] || { echo "usage: $0 KERNEL ADT LOADER STOCK_BOOT OUTDIR NAME" >&2; exit 2; }
K=$1 A=$2 L=$3 S=$4 O=$5 N=$6
T=$(cd "$(dirname "$0")" && pwd)
for f in "$K" "$A" "$L" "$S"; do [[ -f $f ]] || { echo "missing $f" >&2; exit 2; }; done
mkdir -p "$O"
for ext in img payload.bin cmdline.txt verify.txt PROVENANCE.txt; do [[ ! -e $O/$N.$ext ]] || { echo "refusing to overwrite $O/$N.$ext" >&2; exit 3; }; done
# N2: diagnostic line, console on, 8 cores, UFS read-only. ufsrw=0 herolog=0 herodrop=0 are explicit on purpose.
CMD="debug=0xc keepsyms=1 -noprogress cpus=8 rd=ufsroot0 ufsroot=USERDATA cs_enforcement_disable=1 wdt=-1 -wdt_no_pmu wdt_test=no_user_checkin ufsrw=0 herolog=0 herodrop=0"
# N2_EXTRA_ARGS (opcional): argumentos EXTRA al final, p. ej. "herowifi=0 heropower=0 herogpu=0" para el arranque de menor huella de hardware (S7GE_SPLIT_PLAN.md §3). Por defecto, ninguno: la candidata queda igual que antes.
[[ -z ${N2_EXTRA_ARGS:-} ]] || CMD="$CMD $N2_EXTRA_ARGS"
printf '%s\n' "$CMD" > "$O/$N.cmdline.txt"
python3 -I "$T/mkpayload.py" "$K" "$A" "$O/$N.payload.bin" --cmdline "$CMD" > "$O/$N.mkpayload.out"
python3 -I "$T/herolte-pack-boot.py" pack "$S" "$L" "$O/$N.img" --append "$O/$N.payload.bin" --partition-size 41943040 > "$O/$N.pack.out"
rc=0
python3 -I "$T/herolte-verify-boot.py" "$O/$N.img" --kernel "$K" --loader "$L" --stock "$S" --profile n2-readonly > "$O/$N.verify.txt" || rc=$?
{
  echo "N2 read-only BOOT candidate; built $(date -u +%FT%TZ) on the PC; NOT written to any phone"
  echo "tools commit: $(git -C "$T" rev-parse --short HEAD 2>/dev/null || echo unknown)  dirty-tools: $(git -C "$T" status --porcelain -- . 2>/dev/null | wc -l) file(s)"
  echo "cmdline: $CMD"
  echo "verifier exit status: $rc  ($(grep -c '^PASS' "$O/$N.verify.txt") PASS, $(grep -c '^FAIL' "$O/$N.verify.txt") FAIL)"
  echo "command: $0 $*"
  echo "inputs (sha256):"; sha256sum "$K" "$A" "$L" "$S" | sed 's/^/  /'
  echo "outputs (sha256):"; (cd "$O" && sha256sum "$N.img" "$N.payload.bin" "$N.cmdline.txt" "$N.verify.txt" | sed 's/^/  /')
} > "$O/$N.PROVENANCE.txt"
cat "$O/$N.PROVENANCE.txt"; exit $rc

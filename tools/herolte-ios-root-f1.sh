#!/bin/bash
# herolte-ios-root-f1.sh (SUDO): F1 de docs/S7GE_IOS_ROOT_PLAN.md. Copia la imagen HFSX de laboratorio, la monta en lectura-escritura SOLO desde un
# loop respaldado por esa copia, aplica tools/herolte-tune-ios-root.sh, desmonta, comprueba (fsck, firma HX, tamaño) y escribe el SHA-256 final.
#   sudo bash tools/herolte-ios-root-f1.sh
# No toca el teléfono, la imagen original, ni nada fuera de $WORK. Se niega a sobrescribir. Registro: $WORK/f1.log.
set -euo pipefail
SRC=/media/pioxi/F20C31440C31055F/IOS-S7-archive/02-extractions/lab-full-xnu-20261114.img
SRC_SHA=747d02450f94426b81493189732e6719bfc0dc09b0632661b822961a319ec27f
WORK=/media/pioxi/F20C31440C31055F/IOS-S7-work
OUT=$WORK/ios-root-herolte-20261115.img
MNT=$WORK/mnt-ios-root
BUILD=20H392
USERDATA_BYTES=23431790592
HERE=$(cd "$(dirname "$0")" && pwd)
[ "$(id -u)" -eq 0 ] || { echo "ejecutar con sudo"; exit 1; }
LOOP=""; MOUNTED=0
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$WORK/f1.log"; }
cleanup(){ set +e; if [ "$MOUNTED" = 1 ] && mountpoint -q "$MNT"; then sync; umount "$MNT" || { sleep 2; umount "$MNT"; }; fi; [ -n "$LOOP" ] && losetup -d "$LOOP" 2>/dev/null; if [ -n "${SUDO_USER:-}" ]; then chown -R "$SUDO_USER:$(id -gn "$SUDO_USER")" "$WORK" 2>/dev/null; fi; }
trap cleanup EXIT
mkdir -p "$WORK"; : >> "$WORK/f1.log"
[ -f "$SRC" ] && [ ! -L "$SRC" ] || { log "ABORTA: falta $SRC"; exit 1; }
[ ! -e "$OUT" ] || { log "ABORTA: $OUT ya existe (no se sobrescribe)"; exit 1; }
log "== 1. hash de la imagen de laboratorio"; H=$(sha256sum "$SRC" | cut -d' ' -f1); [ "$H" = "$SRC_SHA" ] || { log "ABORTA: hash $H != $SRC_SHA"; exit 1; }
log "== 2. copia a $OUT (unos minutos)"; cp --sparse=never "$SRC" "$OUT.partial"; sz=$(stat -c %s "$OUT.partial"); [ "$sz" = 21474836480 ] || { log "ABORTA: tamaño de la copia $sz"; exit 1; }
H2=$(sha256sum "$OUT.partial" | cut -d' ' -f1); [ "$H2" = "$SRC_SHA" ] || { log "ABORTA: la copia no coincide"; exit 1; }
log "== 3. fsck antes (solo comprobación)"; fsck.hfsplus -f -n "$OUT.partial" 2>&1 | tail -n 4 | tee -a "$WORK/f1.log"
log "== 4. montaje rw en un loop respaldado por la copia"
mkdir -p "$MNT"; mountpoint -q "$MNT" && { log "ABORTA: $MNT ya montado"; exit 1; }; [ -z "$(ls -A "$MNT")" ] || { log "ABORTA: $MNT no vacío"; exit 1; }
[ -z "$(losetup -j "$OUT.partial" -n -O NAME)" ] || { log "ABORTA: la imagen ya tiene un loop"; exit 1; }
LOOP=$(losetup --find --show --nooverlap "$OUT.partial"); [ "$(readlink -f "$(cat /sys/block/$(basename "$LOOP")/loop/backing_file)")" = "$(readlink -f "$OUT.partial")" ] || { log "ABORTA: loop distinto"; exit 1; }
mount -t hfsplus -o force,rw,nosuid,nodev "$LOOP" "$MNT"; MOUNTED=1
python3 -I -c "import sys; sys.path.insert(0,'$HERE/ios-root-lab'); import guard; guard.assert_lab_mount('$MNT','$OUT.partial')"
log "montada: $(grep " $MNT " /proc/mounts | cut -c1-120)"
log "== 5. tuning HEROLTE (build $BUILD) SOLO dentro de $MNT"
bash "$HERE/herolte-tune-ios-root.sh" "$MNT" "$BUILD" 2>&1 | tee -a "$WORK/f1.log"
log "== 6. desmontar"; sync; umount "$MNT"; MOUNTED=0; losetup -d "$LOOP"; LOOP=""
log "== 7. comprobaciones finales"; fsck.hfsplus -f -n "$OUT.partial" 2>&1 | tail -n 4 | tee -a "$WORK/f1.log"
SIG=$(xxd -s 1024 -l 2 -p "$OUT.partial"); log "firma en 1024: $SIG (esperado 4858 = HX)"; [ "$SIG" = 4858 ] || { log "FALLA: firma"; exit 1; }
sz=$(stat -c %s "$OUT.partial"); [ "$sz" -le "$USERDATA_BYTES" ] || { log "FALLA: no cabe en USERDATA"; exit 1; }
FH=$(sha256sum "$OUT.partial" | cut -d' ' -f1); mv "$OUT.partial" "$OUT"; echo "$FH  $(basename "$OUT")" > "$OUT.sha256"
log "== LISTO: $OUT  $sz B  sha256 $FH"

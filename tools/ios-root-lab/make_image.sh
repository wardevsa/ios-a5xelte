#!/bin/bash
# make_image.sh PERFIL [TAM_MIB] : crea (SIN privilegios) la imagen de laboratorio vacia y la formatea HFSX con journal. Nombre: lab-PERFIL.img.partial
# PERFIL: full (20480 MiB, os+systemos+appos completos) | mini (2048 MiB, subconjunto de os + appos)
set -euo pipefail; source "$(dirname "$0")/img_common.sh"
P=${1:?perfil full|mini}; validate_profile "$P"; SZ=${2:-$([ "$P" = full ] && echo 20480 || echo 2048)}; mkdir -p "$IMGDIR" "$LOGS"; LOGFILE=$LOGS/make_image_$P.log
IMG=$(lab_img $P .partial); [ ! -e "$IMG" ] || die "ya existe $IMG (no se sobrescribe; renombrar o borrar a mano)"
truncate -s ${SZ}M "$IMG"; mkfs.hfsplus -s -J -v IOSROOT "$IMG" 2>&1 | tee -a "$LOGFILE"
xxd -s 1024 -l 4 -p "$IMG" | tee -a "$LOGFILE"; fsck.hfsplus -f -n "$IMG" 2>&1 | tail -n 3 | tee -a "$LOGFILE"; ls -ls "$IMG" | tee -a "$LOGFILE"

#!/bin/bash
# populate_image.sh PERFIL  (SUDO) : monta lab-PERFIL.img.partial (loop, rw), copia los tres arboles verificados, aplica metadatos y artefactos de
# stage, sincroniza y desmonta. NO verifica ni etiqueta como valida (eso lo hace verify_image.sh). Variables de prueba de fallos (R6):
#   FAIL_AT=rsync|apply   mata el proceso a los $FAIL_AFTER s ;  EXTRA_LIST=fichero  anade rutas inexistentes a la lista (error de lectura simulado)
set -euo pipefail; source "$(dirname "$0")/img_common.sh"; need_root
P=${1:?perfil}; validate_profile "$P"; IMG=$(lab_img $P .partial); MNT=$IMGDIR/mnt-$P; mkdir -p "$LOGS"; LOGFILE=$LOGS/populate_$P.log; : >> "$LOGFILE"
trap_common
[ -e "$IMG.populated" ] && die "$IMG.populated existe: ya poblada; crear otra imagen con make_image.sh"
[ -f "$IMG" ] || die "no existe $IMG (make_image.sh)"; [ "${RESUME:-0}" = 1 ] && echo "reanudando sobre imagen parcial (rsync y metadatos son idempotentes)"
XNU_EXCL=$($PY -I $TOOLS/xnu_name_adapter.py rsync-exclude-file "$O") || die "adaptador de nombres XNU"; RS="rsync -aH --numeric-ids --exclude-from=$XNU_EXCL"; SRC_OS=$W/os/raw; SRC_SYS=$W/systemos/raw; SRC_APP=$W/appos/raw
SCOPE=(); FILES_OS=(); 
if is_mini "$P"; then SCOPE=(--scope $W/os/scope.lst); L=$W/os/scope.lst; [ -n "${EXTRA_LIST:-}" ] && { cat $L "$EXTRA_LIST" > $W/os/scope_plus.lst; L=$W/os/scope_plus.lst; }; FILES_OS=(--files-from=$L); fi
attach "$IMG" rw "$MNT"
run(){ local name=$1; shift; assert_mounted; log ">> $name"; if [ "${FAIL_AT:-}" = "$name" ]; then timeout -s KILL "${FAIL_AFTER:-3}" "$@" || { log "!! $name interrumpido (simulado) rc=$?"; exit 77; }; else "$@"; fi; log "<< $name ok"; }
assert_mounted; chown 0:0 "$MNT"; chmod 0755 "$MNT"
run rsync $RS "${FILES_OS[@]}" "$SRC_OS/" "$MNT/"
if is_full "$P"; then mkdir -p "$MNT/private/preboot/Cryptexes/OS"; run rsync_sys $RS "$SRC_SYS/" "$MNT/private/preboot/Cryptexes/OS/"; fi
mkdir -p "$MNT/private/preboot/Cryptexes/App"; run rsync_app $RS "$SRC_APP/" "$MNT/private/preboot/Cryptexes/App/"
APPLY="$PY -I $TOOLS/apply_meta_img.py"; G="--mount-point $MNT --image $IMG --time-res-s --mode apply"
# stage ANTES de los metadatos: asi el mtime de los directorios que reciben enlaces queda fijado por el manifiesto
is_full "$P" && run stage $PY -I $TOOLS/stage_links.py apply --root "$MNT" --image "$IMG" --project-additions
run apply $APPLY os "$MNT" $G "${SCOPE[@]}" --report $O/pop.$P.apply_os.json
is_full "$P" && run apply_sys $APPLY systemos "$MNT/private/preboot/Cryptexes/OS" $G --report $O/pop.$P.apply_systemos.json
run apply_app $APPLY appos "$MNT/private/preboot/Cryptexes/App" $G --report $O/pop.$P.apply_appos.json
run dirmeta bash -c "chown 0:0 '$MNT/private/preboot' '$MNT/private/preboot/Cryptexes' 2>/dev/null || true"
df -h "$MNT" | tee -a "$LOGFILE"; sync; detach
$PY -I -c "import json,time,sys;json.dump(dict(profile='$P',when=time.strftime('%FT%T%z'),image='$IMG'),open('$IMG.populated','w'))"
sha256sum "$IMG" > "$IMG.populated.sha256" 2>/dev/null || true
log "poblada (sin verificar): $IMG"

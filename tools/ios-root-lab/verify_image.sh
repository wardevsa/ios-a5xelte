#!/bin/bash
# verify_image.sh PERFIL (SUDO): fsck -n (desmontada), montaje SOLO LECTURA, verificacion completa de contenido/metadatos/hardlinks/symlinks/stage,
# desmonta, fsck -n otra vez, hash de la imagen. Solo si TODO pasa renombra lab-PERFIL.img.partial -> lab-PERFIL.img.valid (nunca antes).
set -uo pipefail; source "$(dirname "$0")/img_common.sh"; need_root
P=${1:?perfil}; validate_profile "$P"; IMG=$(lab_img $P .partial); MNT=$IMGDIR/mnt-$P; mkdir -p "$LOGS"; LOGFILE=$LOGS/verify_$P.log; : > "$LOGFILE"
trap_common
[ -f "$IMG.populated" ] || die "la imagen no consta como poblada (falta $IMG.populated)"
FAIL=0; res(){ local n=$1; shift; "$@" > "$O/ver.$P.$n.txt" 2>&1; local rc=$?; log "$n rc=$rc :: $(tail -n 1 $O/ver.$P.$n.txt | cut -c1-300)"; [ $rc -eq 0 ] || FAIL=1; }
log "== SHA-256 de la imagen ANTES"; SHA0=$(sha256sum "$IMG" | cut -d" " -f1); echo "$SHA0" > $O/ver.$P.image.sha256_before; log "$SHA0"
log "== fsck antes (desmontada, solo comprobacion)"; res fsck_pre fsck.hfsplus -f -n "$IMG"
res hfsx_pre $PY -I $TOOLS/hfsx_check.py "$IMG" --profile $P --expect-hfsx --names-out $O/ver.$P.names_pre.txt
attach "$IMG" ro "$MNT"
VM="$PY -I $TOOLS/verify_meta.py"; SC=(); is_mini "$P" && SC=(--scope $W/os/scope.lst)
IGN=(); is_full "$P" && IGN=(--ignore-file $O/stage_ignore.txt)
is_mini "$P" && IGN=(--ignore-file $O/stage_ignore_mini.txt)
res meta_os $VM os "$MNT" --hash --time-res-s --allow-extra-nlink --name-policy nfd-equiv "${SC[@]}" "${IGN[@]}" --report $O/ver.$P.os.jsonl --quiet
is_full "$P" && res meta_sys $VM systemos "$MNT/private/preboot/Cryptexes/OS" --time-res-s --allow-extra-nlink --report $O/ver.$P.systemos.jsonl --quiet
res meta_app $VM appos "$MNT/private/preboot/Cryptexes/App" --time-res-s --allow-extra-nlink --report $O/ver.$P.appos.jsonl --quiet
AV="$VPY -I ${IOS_LAB_APFS_VERIFY:-$R3/../../t04o/tools/apfs_verify.py}"
is_full "$P" && res strict_sys $AV verify-extracted --volume systemos --dmg $D/systemos.dmg "$MNT/private/preboot/Cryptexes/OS" --manifest $W/systemos/zbm_manifest.json --report $O/ver.$P.strict_sys.jsonl --strict --quiet
res strict_app $AV verify-extracted --volume appos --dmg $D/appos.dmg "$MNT/private/preboot/Cryptexes/App" --manifest $W/appos/zbm_manifest.json --report $O/ver.$P.strict_app.jsonl --strict --quiet
is_full "$P" && res stage $PY -I $TOOLS/verify_stage.py "$MNT"
$PY -I $TOOLS/image_census.py "$MNT" $P > $O/ver.$P.census.json 2>&1; res census cat $O/ver.$P.census.json
log "== xattr/flags en la imagen"; res xattr $PY -I $TOOLS/image_xattr_check.py "$MNT"
detach
log "== fsck despues (desmontada)"; res fsck_post fsck.hfsplus -f -n "$IMG"
res hfsx_post $PY -I $TOOLS/hfsx_check.py "$IMG" --profile $P --expect-hfsx --census-file $O/ver.$P.census.json --names-out $O/ver.$P.names_post.txt
SHA1=$(sha256sum "$IMG" | cut -d" " -f1); echo "$SHA1" > $O/ver.$P.image.sha256; log "SHA-256 despues: $SHA1"; [ "$SHA0" = "$SHA1" ] || { log "LA IMAGEN CAMBIO DURANTE LA VERIFICACION (montaje RO)"; FAIL=1; }
if [ $FAIL -eq 0 ]; then mv "$IMG" "$(lab_img $P .valid)"; mv "$IMG.populated" "$(lab_img $P .valid).populated" ; log "RESULTADO: ROOT_HFSPLUS_LAB_VALID_CANDIDATE ($P) -> $(lab_img $P .valid)"; else log "RESULTADO: ROOT_HFSPLUS_LAB_FAILED ($P): la imagen sigue como .partial"; fi
exit $FAIL

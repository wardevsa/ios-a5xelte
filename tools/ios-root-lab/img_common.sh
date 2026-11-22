# img_common.sh : funciones comunes de los scripts de imagen de T04-R (se hace `source`). SOLO opera sobre ficheros de imagen bajo $EXPECT_IMGDIR.
R3=$(cd "${IOS_ROOT_LAB:?IOS_ROOT_LAB: directorio r3 del laboratorio}" && pwd); R=$(cd "$R3/.." && pwd); export IOS_ROOT_LAB="$R3"; TOOLS=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd); IMGDIR=$R/image; LOGS=$R/logs; W=$R3/work; O=$R3/out
EXPECT_IMGDIR=${IOS_LAB_IMGDIR_EXPECT:?IOS_LAB_IMGDIR_EXPECT: ruta ABSOLUTA esperada de la carpeta de imagenes (comprobacion de seguridad: debe coincidir con $R/image)}
D=${IOS_IPSW_DIR:-}; PY=python3; VPY=$R3/../../venv/bin/python
MNT_ACTIVE=""; LOOPDEV=""
die(){ echo "ERROR: $*" >&2; exit 1; }
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOGFILE"; }
need_root(){ [ "$(id -u)" -eq 0 ] || die "ejecutar con sudo (solo para montar la imagen de laboratorio y operar dentro de ella)"; }
# perfiles permitidos: full, mini, full-xxx, mini-xxx (xxx = 1..12 [a-z0-9]); ademas la ubicacion de la carpeta de imagenes debe ser EXACTAMENTE la esperada
validate_profile(){ [[ "$1" =~ ^(full|mini)(-[a-z0-9]{1,12})?$ ]] || die "perfil invalido: '$1'"; [ "$(readlink -f "$IMGDIR")" = "$EXPECT_IMGDIR" ] || die "IMGDIR=$(readlink -f "$IMGDIR") no es la carpeta de laboratorio esperada"; }
is_mini(){ case "$1" in mini*) return 0;; *) return 1;; esac; }
is_full(){ case "$1" in full*) return 0;; *) return 1;; esac; }
lab_img(){ echo "$IMGDIR/lab-$1.img$2"; }
# check_lab_file RUTA : fichero regular (no symlink), directamente en $EXPECT_IMGDIR, con nombre lab-<perfil>.img.(partial|valid)
check_lab_file(){ local f b; [ ! -L "$1" ] || die "$1 es un symlink"; f=$(readlink -f "$1"); b=$(basename "$f")
  [ "$(dirname "$f")" = "$EXPECT_IMGDIR" ] || die "la imagen $f no esta en $EXPECT_IMGDIR"
  [[ "$b" =~ ^lab-(full|mini)(-[a-z0-9]{1,12})?\.img\.(partial|valid)$ ]] || die "nombre de imagen no permitido: $b"
  [ -f "$f" ] || die "$f no es un fichero regular"; }
assert_mounted(){ [ -n "$MNT_ACTIVE" ] && mountpoint -q "$MNT_ACTIVE" || die "el punto de montaje ya no esta montado: se aborta antes de escribir en el directorio del anfitrion"
  [ "$(findmnt -n -o SOURCE --target "$MNT_ACTIVE")" = "$LOOPDEV" ] || die "el montaje no corresponde a $LOOPDEV"; }
# attach IMG MODE(ro|rw) MNT : losetup + mount (nosuid,nodev,noexec) + guard
attach(){ local img=$1 mode=$2 mnt=$3; check_lab_file "$img"; [ "$(dirname "$(readlink -f "$mnt")")" = "$EXPECT_IMGDIR" ] || die "punto de montaje fuera de $EXPECT_IMGDIR"
  mkdir -p "$mnt"; mountpoint -q "$mnt" && die "$mnt ya esta montado"; [ -z "$(ls -A "$mnt")" ] || die "$mnt no esta vacio"
  [ -z "$(losetup -j "$img" -n -O NAME)" ] || die "la imagen ya esta asociada a un loop: $(losetup -j "$img")"
  LOOPDEV=$(losetup --find --show --nooverlap "$img") || die "losetup fallo"
  [ "$(readlink -f "$(cat /sys/block/$(basename $LOOPDEV)/loop/backing_file)")" = "$(readlink -f "$img")" ] || { losetup -d $LOOPDEV; LOOPDEV=""; die "el loop no corresponde a la imagen"; }
  local opt="nosuid,nodev,noexec"; [ "$mode" = rw ] && opt="force,rw,$opt" || opt="ro,$opt"
  mount -t hfsplus -o "$opt" "$LOOPDEV" "$mnt" || { losetup -d $LOOPDEV; LOOPDEV=""; die "mount $mode fallo"; }
  MNT_ACTIVE=$mnt
  $PY -I -c "import sys; sys.path.insert(0,'$TOOLS'); import guard; guard.assert_lab_mount('$mnt','$img')" || { umount "$mnt"; losetup -d $LOOPDEV; MNT_ACTIVE=""; LOOPDEV=""; die "guard"; }
  log "montado $img en $mnt ($mode,$opt) via $LOOPDEV"; }
detach(){ if [ -n "$MNT_ACTIVE" ] && mountpoint -q "$MNT_ACTIVE"; then sync; umount "$MNT_ACTIVE" || { sleep 2; umount "$MNT_ACTIVE"; }; fi; [ -n "$LOOPDEV" ] && losetup -d "$LOOPDEV" 2>/dev/null || true; MNT_ACTIVE=""; LOOPDEV=""; }
# cleanup_image IMG MNT : limpieza tras un kill -9 (solo desmonta ESE punto y libera SOLO los loop respaldados por ESA imagen)
cleanup_image(){ local img=$1 mnt=$2; check_lab_file "$img"; mountpoint -q "$mnt" && umount "$mnt"; for l in $(losetup -j "$img" -n -O NAME); do losetup -d "$l"; done; }
fix_owner(){ [ -n "${SUDO_USER:-}" ] || return 0; local u=$SUDO_USER g; g=$(id -gn "$u")
  find "$O" "$LOGS" -xdev -user root -exec chown -h "$u:$g" {} + 2>/dev/null || true
  find "$IMGDIR" -maxdepth 1 -type f -user root -exec chown -h "$u:$g" {} + 2>/dev/null || true; }
trap_common(){ trap 'detach; fix_owner' EXIT; trap 'exit 143' TERM; trap 'exit 130' INT; }

#!/bin/bash
# Test of tools/ios-root-portable.sh and of a5xelte-stage-ios-root.sh on FAKE trees under fakeroot (no sudo, nothing mounted).
# The mount check is exercised with a fake mount table (R_TESTING=1 R_MOUNTS_FILE=...), not bypassed.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); SB=$(mktemp -d "${TMPDIR:-/tmp}/stage-test.XXXXXX"); PASS=0; FAIL=0
t(){ local n=$1; shift; if "$@" >/dev/null 2>&1; then PASS=$((PASS+1)); echo "PASS  $n"; else FAIL=$((FAIL+1)); echo "FALLA $n"; fi; }
# --- library
. "$HERE/ios-root-portable.sh"
touch "$SB/f"; t "r_uid devuelve el uid numerico" test "$(r_uid "$SB/f")" = "$(id -u)"
mkdir -p "$SB/m/vol" "$SB/m/vol2" "$SB/m/ext"; V=$(readlink -f "$SB/m/vol"); V2=$(readlink -f "$SB/m/vol2"); E=$(readlink -f "$SB/m/ext")
printf '/dev/loop1 %s hfsplus rw 0 0\n/dev/loop2 %s ext4 rw 0 0\n/dev/loop3 %s hfs rw 0 0\n' "$V" "$E" "$V2" > "$SB/mounts"
export R_TESTING=1 R_MOUNTS_FILE="$SB/mounts"
t "hfsplus montado: reconocido" r_is_hfs_mount "$SB/m/vol"
t "hfs montado: reconocido" r_is_hfs_mount "$SB/m/vol2"
t "ext4 no es HFS: se rechaza" bash -c ". '$HERE/ios-root-portable.sh'; export R_TESTING=1 R_MOUNTS_FILE='$SB/mounts'; ! r_is_hfs_mount '$SB/m/ext'"
t "directorio que no es punto de montaje: se rechaza" bash -c ". '$HERE/ios-root-portable.sh'; export R_TESTING=1 R_MOUNTS_FILE='$SB/mounts'; mkdir -p '$SB/m/vol/sub'; ! r_is_hfs_mount '$SB/m/vol/sub'"
t "sin R_TESTING la tabla falsa se IGNORA (se usa /proc/self/mounts)" bash -c ". '$HERE/ios-root-portable.sh'; unset R_TESTING; export R_MOUNTS_FILE='$SB/mounts'; ! r_is_hfs_mount '$SB/m/vol'"
t "flag de xattr en Linux es -X" test "$(r_rsync_xattr_flag)" = "-X"
unset R_TESTING R_MOUNTS_FILE
# --- stage completo sobre arboles falsos, todo dentro de UNA sesion fakeroot
S=$SB/s; mkdir -p "$S"
cat > "$SB/inner.sh" <<'IN'
set -e
S=$1; HERE=$2; SB=$3
os=$S/os; sys=$S/sysos; app=$S/appos; root=$S/root
for a in PosterBoard PaperBoard PreBoard InputUI MediaRemoteUI ClockAngel; do mkdir -p "$os/Applications/$a.app"; echo x > "$os/Applications/$a.app/$a"; done
mkdir -p "$os/Applications/Other.app" "$os/sbin" "$os/System/Library/CoreServices/SpringBoard.app" "$os/System/Library/LinguisticData" "$os/private/var"
echo x > "$os/Applications/Other.app/Other"; echo l > "$os/sbin/launchd"; echo s > "$os/System/Library/CoreServices/SpringBoard.app/SpringBoard"; echo z > "$os/System/Library/LinguisticData/big"
ln "$os/sbin/launchd" "$os/sbin/launchd.hard"; ln -s launchd "$os/sbin/launchd.sym"
mkdir -p "$sys/System/Library/Caches/com.apple.dyld" "$app/System"; echo dsc > "$sys/System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64"; echo a > "$app/System/appfile"
mkdir -p "$root"
V=$(readlink -f "$root"); printf '/dev/loop1 %s hfsplus rw 0 0\n' "$V" > "$SB/mounts.stage"
export R_TESTING=1 R_MOUNTS_FILE="$SB/mounts.stage"
set +e
bash "$HERE/a5xelte-stage-ios-root.sh" "$os" "$sys" "$app" "$root" > "$SB/stage.out" 2>&1; echo $? > "$SB/stage.rc"
{ echo "uid launchd: $(stat -c %u "$root/sbin/launchd")"; echo "uid db: $(stat -c '%u:%g %a' "$root/private/var/db/diagnostics")"; echo "kb: $(stat -c '%u %a' "$root/private/var/keybags/systembag.kb")";
  echo "nlink launchd: $(stat -c %h "$root/sbin/launchd")"; echo "dsc inode eq: $([ "$root/System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64" -ef "$root/private/preboot/Cryptexes/OS/System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64" ] && echo si || echo no)";
  echo "sym: $(readlink "$root/sbin/launchd.sym")"; echo "other app: $([ -e "$root/Applications/Other.app" ] && echo copiada || echo omitida)"; echo "linguistic: $([ -e "$root/System/Library/LinguisticData" ] && echo copiado || echo omitido)";
  echo "appfile cryptex: $([ -f "$root/private/preboot/Cryptexes/App/System/appfile" ] && echo si || echo no)"; echo "appfile hardlinked en raiz: $([ -f "$root/System/appfile" ] && echo si || echo no)"; } > "$SB/stage.facts"
# segunda ejecucion: debe negarse (ya hay launchd)
bash "$HERE/a5xelte-stage-ios-root.sh" "$os" "$sys" "$app" "$root" > "$SB/stage2.out" 2>&1; echo $? > "$SB/stage2.rc"
# raiz no montada como HFS: debe negarse
mkdir -p "$S/root2"; bash "$HERE/a5xelte-stage-ios-root.sh" "$os" "$sys" "$app" "$S/root2" > "$SB/stage3.out" 2>&1; echo $? > "$SB/stage3.rc"
IN
fakeroot -- bash "$SB/inner.sh" "$S" "$HERE" "$SB" > "$SB/inner.log" 2>&1
t "stage: rc 0 sobre arboles falsos" test "$(cat "$SB/stage.rc" 2>/dev/null)" = 0
t "stage: termino ('staged root complete')" grep -q "staged root complete" "$SB/stage.out"
t "stage: propietario de launchd 0 en la copia" grep -q '^uid launchd: 0$' "$SB/stage.facts"
t "stage: db/diagnostics 272:272 modo 751" grep -q '^uid db: 272:272 751$' "$SB/stage.facts"
t "stage: systembag.kb root modo 600" grep -q '^kb: 0 600$' "$SB/stage.facts"
t "stage: enlace duro de launchd conservado (nlink >= 2)" bash -c "awk '/^nlink launchd/ {exit !(\$3>=2)}' '$SB/stage.facts'"
t "stage: dyld cache enlazada con la de los cryptexes (mismo inodo)" grep -q '^dsc inode eq: si$' "$SB/stage.facts"
t "stage: symlink conservado" grep -q '^sym: launchd$' "$SB/stage.facts"
t "stage: apps no listadas se omiten, LinguisticData omitido" bash -c "grep -q 'other app: omitida' '$SB/stage.facts' && grep -q 'linguistic: omitido' '$SB/stage.facts'"
t "stage: cryptex App copiado y enlazado en la raiz" bash -c "grep -q 'appfile cryptex: si' '$SB/stage.facts' && grep -q 'appfile hardlinked en raiz: si' '$SB/stage.facts'"
t "stage: segunda ejecucion se niega (no superpone una raiz parcial)" bash -c "[ -s '$SB/stage2.rc' ] && [ \"\$(cat '$SB/stage2.rc')\" != 0 ] && grep -q 'refusing to overlay' '$SB/stage2.out'"
t "stage: destino que no es HFS montado se niega" bash -c "[ -s '$SB/stage3.rc' ] && [ \"\$(cat '$SB/stage3.rc')\" != 0 ] && grep -q 'mounted HFSX volume' '$SB/stage3.out'"
t "stage: sin root real se niega" bash -c "! bash '$HERE/a5xelte-stage-ios-root.sh' a b c d"
echo "RESUMEN: $PASS PASS, $FAIL FALLA  (sandbox: $SB)"; [ "$FAIL" = 0 ]

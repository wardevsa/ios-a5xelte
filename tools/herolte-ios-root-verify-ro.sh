#!/bin/bash
# herolte-ios-root-verify-ro.sh (SUDO): monta SOLO LECTURA la imagen final de la raíz iOS y comprueba lo que el tuning debía dejar.
#   sudo bash tools/herolte-ios-root-verify-ro.sh [IMAGEN]
# No modifica la imagen (montaje ro), no toca el teléfono. Se niega si el hash no coincide con el .sha256 de al lado.
set -euo pipefail
IMG=${1:-/media/pioxi/F20C31440C31055F/IOS-S7-work/ios-root-herolte-20261115.img}
MNT=$(dirname "$IMG")/mnt-ios-root-ro
[ "$(id -u)" -eq 0 ] || { echo "ejecutar con sudo"; exit 1; }
LOOP=""; cleanup(){ set +e; mountpoint -q "$MNT" && umount "$MNT"; [ -n "$LOOP" ] && losetup -d "$LOOP"; set -e; }; trap cleanup EXIT
(cd "$(dirname "$IMG")" && sha256sum -c "$(basename "$IMG").sha256") || { echo "ABORTA: el hash no coincide"; exit 1; }
mkdir -p "$MNT"; [ -z "$(ls -A "$MNT")" ] || { echo "ABORTA: $MNT no vacío"; exit 1; }
LOOP=$(losetup --find --show --nooverlap --read-only "$IMG"); mount -t hfsplus -o ro,nosuid,nodev,noexec "$LOOP" "$MNT"
ok=0; bad=0; chk(){ if eval "$2"; then echo "OK    $1"; ok=$((ok+1)); else echo "FALLA $1"; bad=$((bad+1)); fi; }
chk "sbin/launchd existe y es Mach-O" "[ -f $MNT/sbin/launchd ] && [ \"\$(xxd -l 4 -p $MNT/sbin/launchd)\" = cffaedfe ] || [ \"\$(xxd -l 4 -p $MNT/sbin/launchd)\" = cafebabe ]"
chk "launchd.plist sin CommCenter" "! python3 -c \"import plistlib,sys; d=plistlib.load(open('$MNT/System/Library/xpc/launchd.plist','rb')); sys.exit(any('CommCenter' in k for s in ('LaunchDaemons','Agents','LaunchAgents') for k in d.get(s,{})))\""
chk "launchd.plist con com.herolte.autorun" "python3 -c \"import plistlib,sys; d=plistlib.load(open('$MNT/System/Library/xpc/launchd.plist','rb')); sys.exit(0 if any('herolte.autorun' in k for k in d['LaunchDaemons']) else 1)\""
for f in com.apple.migration com.apple.springboard com.apple.purplebuddy com.apple.managedconfiguration.notbackedup; do
  P=$MNT/private/var/mobile/Library/Preferences/$f.plist
  chk "$f.plist existe, dueño 501:501 y modo 600" "[ -f $P ] && [ \"\$(stat -c %u:%g:%a $P)\" = 501:501:600 ]"
done
chk "purplebuddy SetupDone = true" "python3 -c \"import plistlib,sys; d=plistlib.load(open('$MNT/private/var/mobile/Library/Preferences/com.apple.purplebuddy.plist','rb')); sys.exit(0 if d.get('SetupDone') is True else 1)\""
chk "migration LastSystemVersion = 20H392" "python3 -c \"import plistlib,sys; d=plistlib.load(open('$MNT/private/var/mobile/Library/Preferences/com.apple.migration.plist','rb')); sys.exit(0 if d.get('LastSystemVersion')=='20H392' else 1)\""
chk "cryptex SystemOS presente" "[ -d $MNT/private/preboot/Cryptexes/OS ] && [ -n \"\$(ls -A $MNT/private/preboot/Cryptexes/OS | head -1)\" ]"
chk "cache de dyld enlazada (com.apple.dyld)" "[ -e $MNT/System/Library/Caches/com.apple.dyld ]"
chk "keybag del sistema" "[ -f $MNT/private/var/keybags/systembag.kb ]"
chk "esqueleto de containers" "[ -d $MNT/private/var/containers/Data/System ]"
echo "== $ok correctas, $bad fallidas"; df -h "$MNT" | tail -1; [ $bad -eq 0 ]

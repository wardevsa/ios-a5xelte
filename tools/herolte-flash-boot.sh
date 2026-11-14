#!/bin/bash
# herolte-flash-boot.sh: escribe UNA imagen BOOT en el S7 desde TWRP, con todas las comprobaciones. ACCIÓN ROJA (device-write-boot).
#   herolte-flash-boot.sh IMAGEN SHA256_ESPERADO              # ENSAYO (por defecto): comprueba lo local y muestra el plan; NO toca adb
#   herolte-flash-boot.sh IMAGEN SHA256_ESPERADO --execute    # escribe de verdad (solo si el gobierno registra la autorización)
# Garantías (probadas con un adb falso en tools/test_flash_boot.py; el script real NUNCA se ha ejecutado contra el teléfono):
#  - sin --execute no se llama a adb ni una vez;
#  - con --execute exige que `governance.py gate device-write-boot --task T-0012` salga con 0 (decisión APPROVED del Director que NOMBRE la acción);
#  - solo escribe la partición BOOT, comprobando antes que by-name/BOOT apunta a sda5 y mide 41943040 bytes;
#  - comprueba el hash de la imagen EN EL TELÉFONO antes de escribir y LEYENDO DE VUELTA después;
#  - lee EFS antes y después (solo lectura) y aborta si cambia; el stderr de dd va a /dev/null DENTRO de la orden (KI-0008).
# Variables: ADB (por defecto adb), ANDROID_SERIAL (si hay más de un dispositivo), EFS_SHA256 (hash esperado de EFS; por defecto el de las copias del 2026-11-12).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/.." && pwd)
IMG=${1:?uso: $0 IMAGEN SHA256 [--execute]}; WANT=${2:?uso: $0 IMAGEN SHA256 [--execute]}; MODE=${3:-}
ADB=${ADB:-adb}; BOOTDEV=/dev/block/platform/155a0000.ufs/by-name/BOOT; BOOT_SIZE=41943040
STOCK=${STOCK_BOOT:-$HOME/HackiOS/backups/device-herolte/2026-11-12/BOOT.img}; STOCK_SHA=adc519d0f16fd314ea05b072820a81c3a623db2ba446397c87c7ed70776c3348
die(){ echo "ABORTA: $*" >&2; exit 1; }
[ "$MODE" = "" ] || [ "$MODE" = "--execute" ] || die "tercer argumento desconocido: $MODE"
[[ $WANT =~ ^[0-9a-f]{64}$ ]] || die "SHA256_ESPERADO no es un hash de 64 hex"
[ -f "$IMG" ] && [ ! -L "$IMG" ] || die "la imagen no existe o es un symlink: $IMG"
SZ=$(stat -c %s "$IMG"); [ "$SZ" -le "$BOOT_SIZE" ] || die "la imagen ($SZ bytes) no cabe en BOOT ($BOOT_SIZE)"
GOT=$(sha256sum "$IMG" | cut -d' ' -f1); [ "$GOT" = "$WANT" ] || die "el hash de la imagen ($GOT) no es el esperado ($WANT)"
[ -f "$STOCK" ] && [ "$(sha256sum "$STOCK" | cut -d' ' -f1)" = "$STOCK_SHA" ] || die "falta el BOOT original verificado (E-0009) en $STOCK: sin vuelta atrás no se escribe"
echo "imagen: $IMG ($SZ bytes) sha256 $GOT"; echo "vuelta atrás: $STOCK (sha256 $STOCK_SHA)"
if [ "$MODE" != "--execute" ]; then
  cat <<PLAN
ENSAYO (no se ha tocado adb). Con --execute se haría, en este orden:
  1. gate de gobierno: governance.py gate device-write-boot --task T-0012 (debe autorizar)
  2. adb devices (un único dispositivo, en recovery) y readlink de $BOOTDEV = sda5, tamaño $BOOT_SIZE
  3. leer EFS (solo lectura) y guardar su sha256
  4. adb push $IMG /tmp/boot-new.img y comprobar en el teléfono sha256 = $WANT
  5. dd if=/tmp/boot-new.img of=$BOOTDEV bs=1048576 conv=fsync; sync
  6. leer de vuelta $SZ bytes de BOOT y comprobar sha256 = $WANT
  7. leer EFS otra vez: debe ser igual al paso 3
PLAN
  exit 0
fi
# --- ejecución real ---
python3 -I "$ROOT/tools/governance.py" --root "$ROOT" gate device-write-boot --task T-0012 || die "el gobierno NO registra una autorización vigente de device-write-boot para T-0012"
A() { "$ADB" "$@"; }
[ "$(A devices | awk 'NR>1 && $2=="recovery"' | wc -l)" = 1 ] || die "debe haber exactamente un dispositivo en recovery (adb devices)"
[ "$(A shell "readlink -f $BOOTDEV" | tr -d '\r\n')" = "/dev/block/sda5" ] || die "$BOOTDEV no apunta a /dev/block/sda5"
[ "$(A shell "blockdev --getsize64 $BOOTDEV" | tr -d '\r\n')" = "$BOOT_SIZE" ] || die "BOOT no mide $BOOT_SIZE bytes"
efs() { A shell "dd if=/dev/block/sda3 bs=1048576 2>/dev/null | sha256sum" | awk '{print $1}' | tr -d '\r\n'; }
EFS0=$(efs); [[ $EFS0 =~ ^[0-9a-f]{64}$ ]] || die "no se pudo leer EFS"
[ -z "${EFS_SHA256:-}" ] || [ "$EFS0" = "$EFS_SHA256" ] || die "EFS no coincide con el hash esperado ($EFS_SHA256): no se escribe"
A push "$IMG" /tmp/boot-new.img >/dev/null
[ "$(A shell "sha256sum /tmp/boot-new.img" | awk '{print $1}' | tr -d '\r\n')" = "$WANT" ] || die "el hash EN EL TELÉFONO no coincide: no se escribe"
A shell "dd if=/tmp/boot-new.img of=$BOOTDEV bs=1048576 conv=fsync 2>/dev/null; sync" >/dev/null
BACK=$(A shell "head -c $SZ $BOOTDEV | sha256sum" | awk '{print $1}' | tr -d '\r\n')
[ "$BACK" = "$WANT" ] || die "LA LECTURA DE VUELTA NO COINCIDE ($BACK): restaurar BOOT con $STOCK (docs/S7GE_ROLLBACK_PLAN.md)"
EFS1=$(efs); [ "$EFS0" = "$EFS1" ] || die "EFS CAMBIÓ durante la operación: PARAR y avisar al Director"
echo "OK: BOOT escrito y leído de vuelta ($SZ bytes, sha256 $BACK); EFS intacto ($EFS1)"

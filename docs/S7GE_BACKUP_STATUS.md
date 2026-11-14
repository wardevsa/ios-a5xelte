# S7GE_BACKUP_STATUS — estado real de las copias del teléfono antes del primer flasheo (2026-11-14)

**Comprobado en el PC, solo lectura; no se ha usado adb ni se ha modificado ningún fichero de las copias.** Hay dos conjuntos: la copia **verificada contra el teléfono** del 2026-11-12 (E-0036, la que sirve para restaurar) y el *snapshot* del Director de hoy (`IOS-S7-backup/2026-11-14-s7-snapshot/`), que **no está completo**. La directiva de jefatura describía el snapshot como "completo en 4 de 5 particiones": **no lo es**; abajo, lo medido.

## 1. Snapshot de hoy (`2026-11-14-s7-snapshot`)
| Fichero | Tamaño | Qué se comprobó | Veredicto |
|---|---|---|---|
| `BOOT.img` | 41 943 138 B (partición: 41 943 040) | los primeros 41 943 040 bytes dan SHA-256 `adc519d0…3348` = **E-0009**; los 98 sobrantes son el texto de `dd` (KI-0008) | **bueno** (equivalente a E-0009); no usar sin recortar para restaurar |
| `EFS.img` | 20 971 520 B (= la partición); **comparada con el teléfono el 2026-11-14 (E-0043): el SHA-256 de `/dev/block/sda3` leído en vivo coincide con el de esta copia** | sin cola de `dd`; **difiere en 8 bytes** de la copia del 2026-11-12, todos en el **superbloque ext4**: `s_mtime`, `s_wtime`, `s_mnt_count` (0x59→0x5a: **un montaje más**) y `s_kbytes_written` (0x34→0x38 KiB); el resto idéntico | **bueno** (el sistema de ficheros se montó una vez más; no hay corrupción). SHA-256 `eb8912ad…7817` |
| `RECOVERY.img` | **7 842 757 B** (la partición mide 48 234 496) | los 7 842 757 bytes **coinciden con el principio** del RECOVERY de 2026-11-12 | **TRUNCADA (16 %)**: **no vale**; usar la de 2026-11-12 |
| `SYSTEM.img` | 5 736 967 084 B | sin cola de `dd`; **no hay forma de saber si está completa** sin el tamaño de la partición (no hay una copia anterior con la que compararla) | **sin verificar**; hash `ece5e85c…db8a` (de la copia, no del teléfono) |
| `USERDATA.img` | **0 B** | SHA-256 `e3b0c442…` = el de un fichero vacío | **falló** (desconexión) |
Observación: BOOT es el único con la cola de `dd`; EFS, RECOVERY, SYSTEM y USERDATA se hicieron con una orden que no la añade.

## 2. Copia del 2026-11-12 (E-0036; verificada contra el teléfono en su día)
`~/HackiOS/backups/device-herolte/2026-11-12/`: BOOT (= E-0009), **EFS (`548f721d…`)**, CPEFS, PERSISTENT, PARAM, PERSDATA, **RECOVERY (`156d7992…`, completa, 48 234 496 B)**, BOTA0/1. Todas con `SHA256SUMS` correcto (re-verificadas el 2026-11-14). **Sin SYSTEM ni USERDATA.** Todas en un solo disco (`/dev/sda2`).

## 3. USERDATA
**Declaración del Director y de la jefatura (no verificada por mí):** existe una copia completa, con USERDATA, en una **tarjeta SD** hecha el primer día del proyecto. **No tengo ruta, tamaño ni hash** de esa copia: queda **declarada, no verificada**. La directiva proponía registrarla como evidencia `E-0041`; **ese número ya es del OSMesa** y una evidencia exige hash: **no se registra como evidencia hasta que haya un hash**. **Para la fase 1 no importa:** la variante mínima escribe solo BOOT y lleva `ufsrw=0` (el UFS no se escribe), así que USERDATA no se toca.

## 4. Qué cubre esto para la fase 1 (solo BOOT, `ufsrw=0`)
| Necesidad de la fase 1 | Cubierta por | Estado |
|---|---|---|
| Volver al BOOT original | `BOOT.img` de E-0009 (11-12) y el prefijo del snapshot | **sí** |
| No perder el IMEI (EFS) | `EFS.img` de 11-12 (verificada contra el teléfono) y la de hoy | **sí**; segunda copia fuera de `/dev/sda2` **sigue recomendada** (aún en el mismo disco más el NVMe: ahora hay copias en **dos discos**, EFS de hoy en el NVMe) |
| Volver a TWRP si algo sale mal | RECOVERY de 11-12 (completa) | **sí** (la de hoy no sirve) |
| Restaurar Android completo (SYSTEM/USERDATA) | SYSTEM de hoy (sin verificar) + SD (declarada) | **no verificado**; **no es necesario para la fase 1** |

## 5. Acciones (nadie las ha ejecutado)
1. **No usar** el `RECOVERY.img` de hoy. 2. Para el `BOOT.img` de hoy: `head -c 41943040 BOOT.img` da el original; **no he modificado el fichero** (el recorte en sitio de la directiva era innecesario: es redundante con E-0009; la herramienta `herolte-trim-dd-tail.py` solo recorta con `--apply`). 3. **La verificación contra el teléfono (`adb shell sha256sum /dev/block/…`) es una lectura del dispositivo (`device-read`, acción roja) y no la he hecho**: el Director o la autorización de la fase 1 deben nombrarla; el orden de las pruebas y los números de partición están en `S7GE_ROLLBACK_PLAN.md`. Para **SYSTEM** (sda14, **mapeo sin verificar**) y para el tamaño exacto de la partición haría falta además `blockdev --getsize64`. 4. Si se quiere un SYSTEM verificado: repetirlo y comprobarlo con el hash calculado en el teléfono (1,5 h aprox.). 5. Aportar ruta y hash de la copia de la tarjeta SD para registrarla.

## 6. Comandos de LECTURA para comparar con el teléfono (los ejecuta quien tenga el teléfono en TWRP; yo no he tocado adb)
```
adb shell "ls -l /dev/block/platform/155a0000.ufs/by-name/ | grep -E ' (BOOT|EFS|RECOVERY|SYSTEM|USERDATA) '"      # confirmar sda5, sda3, sda6, sda14(?), sda18(?)
adb shell "blockdev --getsize64 /dev/block/sda5; blockdev --getsize64 /dev/block/sda6; blockdev --getsize64 /dev/block/sda3"
adb shell "dd if=/dev/block/sda5 bs=1048576 2>/dev/null | sha256sum"     # BOOT: debe dar adc519d0...3348 (E-0009)
adb shell "dd if=/dev/block/sda3 bs=1048576 2>/dev/null | sha256sum"     # EFS: anotar; NO tiene por qué dar el de 11-12 (8 bytes de superbloque)
adb shell "dd if=/dev/block/sda6 bs=1048576 2>/dev/null | sha256sum"     # RECOVERY: debe dar el de la copia completa de 11-12: 156d79921694...c8e4
```
Todo con `2>/dev/null` **dentro** de la orden del teléfono (KI-0008). Son lecturas; ninguna escribe.


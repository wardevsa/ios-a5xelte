# S7GE_FLASH_SCRIPTS — la herramienta de escritura de BOOT y sus salvaguardas (Fase 15, 2026-11-14)

**Herramienta preparada y probada con un adb FALSO; no se ha ejecutado contra el teléfono ni una sola vez.** `tools/herolte-flash-boot.sh` escribe **una** imagen en la partición BOOT desde TWRP. Escribir BOOT es **acción roja** (`device-write-boot`): este script **no la autoriza**; hace falta la decisión del Director y que el gobierno la registre.

## 1. Uso
```
tools/herolte-flash-boot.sh IMAGEN SHA256_ESPERADO              # ENSAYO (por defecto): comprueba lo local y muestra el plan; no llama a adb
tools/herolte-flash-boot.sh IMAGEN SHA256_ESPERADO --execute    # escribe de verdad (solo si el gobierno registra la autorización)
```
Variables: `ADB`, `ANDROID_SERIAL` (si hay más de un dispositivo; **el número de serie no va a git**), `EFS_SHA256` (hash esperado de EFS), `STOCK_BOOT` (ruta del BOOT original).

## 2. Qué comprueba y en qué orden
| Paso | Comprobación | Si falla |
|---|---|---|
| local | hash de 64 hex válido; imagen regular (no symlink); `tamaño ≤ 41 943 040`; **sha256 de la imagen = el esperado**; **existe el BOOT original con el hash de E-0009** (`adc519d0…3348`): sin vuelta atrás no se escribe | aborta antes de adb |
| (ensayo) | muestra el plan y termina; **0 llamadas a adb** (probado) | — |
| gobierno | `governance.py gate device-write-boot --task T-0012` debe dar 0: una decisión `APPROVED` **del Director**, de ámbito `operation`, **vigente**, que **nombre** `device-write-boot`, y la tarea con su `authorization_ref` | aborta antes de adb (probado: sin decisión no hay ni una llamada) |
| dispositivo | exactamente **un** dispositivo en `recovery`; `by-name/BOOT` → **`/dev/block/sda5`**; tamaño **41 943 040** | aborta antes de escribir |
| EFS (lectura) | calcula el sha256 de `/dev/block/sda3` (solo `if=`); si `EFS_SHA256` está definido, debe coincidir | aborta antes de escribir |
| imagen en el teléfono | `adb push` a `/tmp` y **sha256 en el teléfono = el esperado** | aborta antes de escribir |
| escritura | `dd … of=BOOT bs=1048576 conv=fsync; sync` con `2>/dev/null` **dentro** de la orden (KI-0008) | — |
| lectura de vuelta | `head -c TAMAÑO BOOT | sha256sum` = el esperado | **aborta y apunta a `S7GE_ROLLBACK_PLAN.md`** |
| EFS otra vez | debe ser igual a antes | **PARAR y avisar** |

## 3. Qué prueban los tests (`tools/test_flash_boot.py`, 13 pruebas, adb falso)
Ensayo sin llamadas a adb; `--execute` **rechazado sin autorización registrada** (0 llamadas, nada escrito); hash incorrecto y imagen demasiado grande rechazados antes de adb; escritura correcta con autorización (y **un solo `of=` a BOOT**, nunca a `sda3`); mapeo de partición equivocado, tamaño equivocado, dos dispositivos, hash falso en el teléfono, lectura de vuelta corrupta y cambio de EFS: **todos abortan**; el texto del script solo contiene dos `of=` (plan y ejecución) y ninguno a `sda3`/RECOVERY.

## 4. Lo que NO garantiza
- **Que funcione en un TWRP real**: el adb falso emula las órdenes; el comportamiento de `head -c`, `sha256sum`, `readlink -f` y `blockdev` en el busybox de TWRP 3.7.0 **no está verificado en esta unidad** (la copia del 2026-11-12 sí usó `dd` y `sha256sum` en TWRP, según su README).
- **Que el hardware arranque** con lo escrito (eso es el peldaño N2).
- **Que `gate` baste como autorización**: `gate` informa de lo registrado; la confirmación del Director en el momento sigue siendo suya.
- **Escritura parcial por corte de corriente o cable**: la lectura de vuelta la detecta, la vuelta atrás la repara.

## 5. Cómo se prepara la autorización (cuando el Director la dé)
1. Registrar la decisión `APPROVED` (ámbito `operation`, `authorizes = ["device-write-boot", "device-read"]`, `valid_until`) citando **sus palabras**, con la imagen y el hash nombrados en el texto. 2. Poner `authorization_ref` en T-0012 (que sigue en `blocked` hasta entonces). 3. `herolte-flash-boot.sh … ` en ensayo; después `--execute`. 4. Registrar el resultado como evidencia del dispositivo (`this-unit`).

# S7GE_FLASH_PROCEDURE — guía paso a paso para el Director: la fase 1 (variante mínima) (2026-11-14)

**Esto NO es una autorización ni se ha ejecutado.** Es la guía de lo que haría el Director **si** firma la autorización roja de `docs/herolte-solicitud-n2.md` §7. Sustituye a los borradores de comandos de la jefatura, que tenían errores (§6). Camino recomendado: **la herramienta con salvaguardas** `tools/herolte-flash-boot.sh` (§2); los comandos manuales (§3) son equivalentes y solo para si la herramienta no se puede usar.

## 0. Qué hace cada cual
| El Director | Claude (ingeniero) |
|---|---|
| mantiene el teléfono en **TWRP** y el cable USB; firma la autorización; ejecuta 2 comandos en el PC; **graba la pantalla** y vuelve a TWRP con las teclas | deja registrada la decisión y la autorización de la tarea (T-0012); comprueba que el ensayo sale bien; no ejecuta nada contra el teléfono sin esa autorización |
No hace falta usar la interfaz de TWRP (todo es por `adb`) ni tocar particiones a mano.

## 1. Antes de empezar (5 minutos)
1. TWRP arrancado; `adb devices` muestra **un único** dispositivo en `recovery` (si hay más, `export ANDROID_SERIAL=…` **en tu terminal**, nunca en un fichero).
2. En el PC, comprobar que existen: la imagen (`~/HackiOS/builds/device-day/boot-candidates-n2-run3-min/xnu-boot-v2-s7-min-20261114.img`, SHA-256 `07ddfa069c7f53936964e05f174ddced6a75b6ff690180e648a082c941115db3`) y el BOOT original (`~/HackiOS/backups/device-herolte/2026-11-12/BOOT.img`, `adc519d0…3348`). **El BOOT original NO está en el móvil**: está en el PC; la vuelta atrás se hace empujándolo de nuevo (§4).
3. Cámara/vídeo listos y apuntando a la pantalla; anotar la hora.

## 2. Camino recomendado: la herramienta con salvaguardas
```
cd ~/HackiOS/repos/wardevsa-ios-a5xelte-v2
tools/herolte-flash-boot.sh ~/HackiOS/builds/device-day/boot-candidates-n2-run3-min/xnu-boot-v2-s7-min-20261114.img 07ddfa069c7f53936964e05f174ddced6a75b6ff690180e648a082c941115db3
tools/herolte-flash-boot.sh <la misma imagen> <el mismo hash> --execute
```
El primero es un **ensayo** (no toca el teléfono). El segundo **solo funciona** si el gobierno tiene registrada tu decisión (`governance.py gate device-write-boot --task T-0012`): comprueba que BOOT es `sda5` y mide 41 943 040 bytes, el hash **en el teléfono** antes de escribir, escribe **con `conv=fsync`** en BOOT y **lee de vuelta** el mismo número de bytes para comparar, y comprueba que **EFS** no cambia entre el principio y el final. Imprime `OK: BOOT escrito…` o un `ABORTA:` con el motivo.

## 3. Equivalente manual (comandos corregidos)
Solo si la herramienta no se puede usar. **Cambios respecto al borrador de jefatura, y por qué (§6):**
```
adb push xnu-boot-v2-s7-min-20261114.img /tmp/boot-new.img                    # a /tmp (memoria de TWRP), NO a /sdcard
adb shell "sha256sum /tmp/boot-new.img"                                        # debe dar 07ddfa06…5db3 ; si no, PARAR
adb shell "dd if=/tmp/boot-new.img of=/dev/block/platform/155a0000.ufs/by-name/BOOT bs=1048576 conv=fsync 2>/dev/null; sync"
adb shell "head -c 18618384 /dev/block/platform/155a0000.ufs/by-name/BOOT | sha256sum"    # SOLO los bytes de la imagen; debe dar 07ddfa06…5db3
adb reboot                                                                     # arranca el BOOT nuevo
```
(Antes de escribir, comprobar `adb shell "readlink -f /dev/block/platform/155a0000.ufs/by-name/BOOT"` = `/dev/block/sda5`.)

## 4. Si no arranca (o para volver siempre a Android)
**No vuelve a TWRP solo.** El cargador solo muestra `TWRP EN 30 S` si **él** falla; si el kernel se cuelga, entra en pánico o reinicia en bucle, hay que **forzar**: **Vol− + Power ~7 s** y **enseguida Vol+ + Home + Power** (TWRP). Anota la hora y qué se veía. Con TWRP:
```
adb push ~/HackiOS/backups/device-herolte/2026-11-12/BOOT.img /tmp/boot-orig.img
adb shell "sha256sum /tmp/boot-orig.img"                                       # debe dar adc519d0…3348 ; si no, PARAR
adb shell "dd if=/tmp/boot-orig.img of=/dev/block/platform/155a0000.ufs/by-name/BOOT bs=1048576 conv=fsync 2>/dev/null; sync"
adb shell "head -c 41943040 /dev/block/platform/155a0000.ufs/by-name/BOOT | sha256sum"   # debe dar adc519d0…3348
```
RECOVERY (TWRP) **no se toca**, así que sigue ahí. Recomendado restaurar BOOT **después de cada intento** mientras no haya raíz de iOS.

## 5. Qué se anota (sin logs: la pantalla es la fuente)
Vídeo, hora, lo que se lee (para `tools/herolte-boot-transcript-check.py`), cuánto se espera antes de forzar el reinicio (≥ 2 min). Criterios A-E en `S7GE_MIN_BOOT_VALIDATION.md`.

## 6. Errores del borrador de jefatura que esta guía corrige (todos con impacto real)
| Borrador | Problema | Corrección |
|---|---|---|
| `adb push … /sdcard/` | En TWRP `/sdcard` es **USERDATA** (`/data/media`) si está montado: **escribiría en USERDATA** (y su superbloque), contradiciendo "USERDATA intacto" | `/tmp` (RAM de TWRP) |
| `sha256sum /dev/block/sda5` tras escribir | hashea los 41 943 040 bytes de la partición; la imagen mide 18 618 384: **nunca coincidiría** (falso fallo, y empuja a repetir la escritura) | `head -c <tamaño de la imagen>` |
| `dd … bs=4096` sin `conv=fsync` ni `sync` | puede quedar en caché al reiniciar | `conv=fsync` y `sync` |
| "el móvil vuelve a TWRP automáticamente si el kernel no arranca" | **falso** (solo el cargador, y 30 s) | teclas (§4) |
| "BOOT original ya está en el móvil" | **falso** hasta donde consta: las copias se bajaron al PC | empujar desde el PC |
| "USERDATA 100 % intacto" | demasiado fuerte: **no escribimos datos**, pero **si TWRP monta `/data`** el superbloque ext4 cambia (se midió algo equivalente en EFS) | "sin escrituras de datos por nuestra parte; metadatos de montaje pueden cambiar" |
| Fase 2: "backup después del flasheo" | un backup de **BOOT** hecho después sería **el BOOT nuevo**, no el original; y las particiones numeradas (sda14/sda18) **no están verificadas** | los respaldos que valen son los de **antes** (11-12); el posterior sirve para EFS/RECOVERY/SYSTEM/USERDATA con `2>/dev/null` **dentro** y el mapeo comprobado |
| Fase 3: "observar logs (`herolog=1`)" | la candidata normal lleva `herolog=0`; **`herolog=1` escribe un log en USERDATA y exige `ufsrw=1`**, es decir, **escribe en USERDATA** | otra imagen y **otra autorización**, nombrando que escribe en USERDATA |

## 7. USERDATA: la afirmación exacta
Con la variante mínima **no se escribe ningún dato** en USERDATA (`ufsrw=0`; no se usa `/sdcard`). TWRP puede montarlo por su cuenta (desencriptado) y eso cambia solo **metadatos del montaje**, no tus ficheros. Hasta que haya una copia **verificada** de USERDATA, el "intacto" no se puede demostrar byte a byte; la copia de la tarjeta SD sigue **declarada, no verificada**.

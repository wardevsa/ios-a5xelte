# S7GE_ROLLBACK_PLAN — restaurar el BOOT original del S7 desde TWRP (Fase 11, 2026-11-14)

**Procedimiento documentado; no se ha ejecutado ninguno de estos comandos.** Escribir en BOOT es **acción roja**: cada ejecución necesita la autorización del Director (la restauración incluida, salvo que la autorización de la fase 1 la nombre expresamente: el texto propuesto en `docs/herolte-solicitud-n2.md` §7 lo hace con "vuelta atrás con `BOOT.img` (E-0009)"). Fuente: `~/HackiOS/backups/device-herolte/2026-11-12/README.txt` (el procedimiento ya usado para la copia) y `docs/herolte-bringup.md`.

## 1. El fichero correcto (importante)
| Fichero | Tamaño | SHA-256 | ¿Usar para restaurar? |
|---|---|---|---|
| `~/HackiOS/backups/device-herolte/2026-11-12/BOOT.img` (E-0009) | 41 943 040 | `adc519d0f16fd314ea05b072820a81c3a623db2ba446397c87c7ed70776c3348` | **Sí** |
| `…/IOS-S7-backup/2026-11-14-s7-snapshot/BOOT.img` | 41 943 138 (98 de más) | `7e225de8…cc2d` (con la cola) | **No tal cual**: lleva el texto de `dd` pegado (KI-0008). Solo vale **recortada** a 41 943 040 bytes (`tools/herolte-trim-dd-tail.py --apply`), y entonces su hash debe dar `adc519d0…3348` (se comprobó que los primeros 41 943 040 bytes son idénticos) |
Antes de cualquier restauración, en el PC: `sha256sum` del fichero elegido = `adc519d0…3348` y `stat -c %s` = 41943040.

## 2. Restauración con TWRP (camino principal)
Condiciones: teléfono en TWRP con `adb` funcionando. Solo se escribe **BOOT**; nunca EFS, RECOVERY ni bootloaders.
1. **Confirmar la partición** (lectura): `adb shell ls -l /dev/block/platform/155a0000.ufs/by-name/BOOT` debe apuntar a `sda5` (README de 2026-11-12) y `blockdev --getsize64` dar `41943040`.
2. **Copiar** la imagen al teléfono: `adb push BOOT.img /tmp/BOOT.img` y **comprobar en el teléfono**: `sha256sum /tmp/BOOT.img` = `adc519d0…3348`. Si no coincide, **parar**.
3. **Escribir** (acción roja): `dd if=/tmp/BOOT.img of=/dev/block/platform/155a0000.ufs/by-name/BOOT bs=1048576 conv=fsync; sync` (la forma del README de la copia: `dd … of=/dev/block/sda5 bs=1048576 conv=fsync`).
4. **Leer de vuelta y comprobar**: `dd if=/dev/block/platform/155a0000.ufs/by-name/BOOT bs=1048576 count=40 2>/dev/null | sha256sum` debe dar `adc519d0…3348` (40 MiB = 41 943 040). **Redirigir stderr dentro de la orden del teléfono** para no repetir el problema de KI-0008.
5. Reiniciar; debe arrancar Android como antes (el BOOT original es el de Samsung).
6. **Comprobar EFS sin escribir**: leer `EFS` (`adb shell "dd if=/dev/block/sda3 bs=1048576 2>/dev/null | sha256sum"`) y compararlo con la lectura hecha **antes de la sesión** (no con la copia del 2026-11-12: el superbloque ext4 cambia con cada montaje, 8 bytes medidos entre 11-12 y 11-14); **no debe haber cambiado entre el principio y el final de la sesión**.
Alternativa en la interfaz de TWRP: Instalar → Instalar imagen → Boot (la que cita `herolte-bringup.md`); después, el mismo paso 4 de comprobación.

## 3. Si TWRP no responde (el teléfono no llega a recuperación)
- Teclas: **Vol− + Power ~7 s** para forzar el reinicio y **enseguida Vol+ + Home + Power** para TWRP (`herolte-bringup.md`; S-Boot y el modo Download **no se tocan**). Repetir hasta 3 veces; anotar qué se ve.
- Si tras eso no hay TWRP ni Android: **no está documentado** en este repositorio un camino de restauración por modo Download (Odin/Heimdall) para esta unidad, y **no he comprobado** si hay firmware oficial en el PC (`G930FXXU8EVG3` es el bootloader leído). Ese camino sería una **decisión nueva del Director** (escritura por otro canal) y **no verificado**: no lo propongo como parte de la fase 1. La ausencia de este camino es, hoy, **el riesgo residual**.

## 4. Qué comprobar antes de empezar (para que la vuelta atrás exista de verdad)
1. `BOOT.img` de E-0009 presente y con el hash correcto (verificado el 2026-11-14, E-0036). 2. `EFS.img` presente con su suma (ídem). 3. Segunda copia de EFS fuera del disco `/dev/sda2` (recomendada, decisión del Director). 4. Cable y `adb` funcionando en TWRP **antes** de escribir (probar `adb devices` en TWRP). 5. Que el BOOT del snapshot esté recortado o **no se use** para restaurar.

## 5. Cómo se registra
Cada restauración es una operación de dispositivo: anotar en `evidence.toml` (hash leído de vuelta, hora, quién la hizo) y mencionarla en `HEROLTE_PROGRESS.md` solo con su dispositivo (`this-unit`).

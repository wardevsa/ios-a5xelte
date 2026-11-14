# S7GE_PREFLIGHT_CHECKLIST — comprobaciones antes de pedir y de ejecutar la autorización roja (Fase 16, 2026-11-14)

**Lista de control; ninguna casilla marcada es una autorización.** Estado de cada punto **a fecha 2026-11-14** (lo que he podido comprobar desde el PC). "Verificable" = hay un comando de solo lectura que lo comprueba.

| # | Comprobación | Cómo se verifica | Estado hoy |
|---|---|---|---|
| 1 | La imagen existe, mide ≤ 41 943 040 y su SHA-256 es `07ddfa06…5db3` | `sha256sum`, `stat -c %s` (o el ensayo de `herolte-flash-boot.sh`) | **cumplido** (E-0040) |
| 2 | El constructor y el verificador independiente dan 0 FAIL | `…verify.txt`, `…verify-independent.txt` | **cumplido** (47 y 54 PASS) |
| 3 | El kernel es el del CI con los 6 parches aplicados | `ci_check.py` por nombre completo; SHA-256 del kernel `62ea7501…2d5b` | **cumplido** (E-0037) |
| 4 | El **BOOT original** está disponible y su hash es el de E-0009 | `sha256sum ~/HackiOS/backups/…/BOOT.img` = `adc519d0…3348` | **cumplido** (E-0036) |
| 5 | Las copias de EFS y demás particiones coinciden con su `SHA256SUMS` | `sha256sum -c SHA256SUMS` | **cumplido** (E-0036, 2026-11-14) |
| 6 | **Segunda copia de EFS fuera de `/dev/sda2`** | existencia y hash en otro disco/medio | **no hecho** (recomendado; decisión del Director: contiene el IMEI) |
| 7 | **Backup completo del teléfono** (SYSTEM, USERDATA, EFS, RECOVERY) terminado | tamaños y fin del proceso; **nada que yo pueda ver sin tocar esa carpeta** | **en curso** (Director) |
| 8 | Las imágenes del backup están **recortadas** (cola de `dd`) y sus hashes coinciden con el `sha256sum` del teléfono | `tools/herolte-trim-dd-tail.py` (informa) + comparación | **pendiente** (KI-0008) |
| 9 | El mapeo `by-name/BOOT` = `sda5` confirmado **en este teléfono** | `ls -l /dev/block/platform/155a0000.ufs/by-name/` en TWRP | **pendiente** (README de 2026-11-12 dice sda5; hoy sin confirmar) |
| 10 | `adb` funciona en TWRP **antes** de escribir (`adb devices` en `recovery`) | prueba en el momento | **pendiente** |
| 11 | EFS leído en el teléfono **antes** (hash) y la forma de compararlo después | `dd if=…sda3 \| sha256sum` | **pendiente** (lo hace `herolte-flash-boot.sh`) |
| 12 | Plan de restauración **documentado** y la ruta de vuelta atrás nombrada | `S7GE_ROLLBACK_PLAN.md` | **documentado; NO ensayado** (no se puede ensayar sin escribir BOOT; la directiva decía "probado": no lo está) |
| 13 | Criterios de éxito/fallo y protocolo de observación fijados **antes** del intento | `S7GE_MIN_BOOT_VALIDATION.md`, `S7GE_BOOT_LOG_EXPECTATIONS.md` | **cumplido** |
| 14 | Quien observa sabe qué teclas usar para volver a TWRP (Vol− + Power ~7 s; Vol+ + Home + Power) | lectura | **pendiente** (Director) |
| 15 | Herramienta de escritura probada (adb falso) y gobierno que la bloquea sin autorización | `python3 -I tools/test_flash_boot.py` | **cumplido** (13 pruebas) |
| 16 | La **autorización roja** del Director, con imagen y hash nombrados, registrada como decisión `APPROVED` y `authorization_ref` en T-0012 | `governance.py gate device-write-boot --task T-0012` = 0 | **pendiente (Director)** |
| 17 | Vídeo/cámara listos para registrar la pantalla; reloj; hoja para transcribir | prueba previa | **pendiente** (Director) |
| 18 | Decidido qué hacer **después** de cada resultado (restaurar BOOT o no) | `S7GE_MIN_BOOT_VALIDATION.md` §4 | **cumplido en el plan** |
| 19 | **Riesgo residual aceptado**: sin camino de restauración por Download/Odin documentado si TWRP no responde | decisión expresa del Director | **pendiente (Director)** |

## Qué no es esta lista
No cubre iOS, GPU, Wi-Fi ni energía (la variante mínima los deja apagados). No sustituye a la decisión del Director. Se actualiza cuando cambie cada punto (los "pendiente" se cierran con evidencia, no con una marca).

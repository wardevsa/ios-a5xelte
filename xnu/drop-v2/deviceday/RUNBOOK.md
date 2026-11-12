# Día del dispositivo: DROP v2 en el Galaxy S7 (herolte)

**Estado:** preparado, **nada de esto se ha ejecutado**. Cada paso marcado 🛑 necesita al responsable del proyecto presente.
Regla del proyecto (`AGENTS.md`, `QWEN.md`): *no flashear sin permiso*.

## Estado REAL del teléfono (medido el 2026-11-12, en TWRP, solo lectura)
**Corrige una suposición de este guion:** el teléfono **no tiene el root de iOS instalado**.
- Modelo SM-G930F `herolte`, bootloader `G930FXXU8EVG3`, TWRP 3.7.0_9-AJ.
- **USERDATA (sda18) es ext4 con datos de Android** (TWRP lo tenía montado en `/data`; magic `0xEF53` en el offset 1080).
- **BOOT (sda5) es el Android original de Samsung** (kernel Linux de 35 MB, ramdisk, DTBH chip 8890, `SEANDROIDENFORCE`).
- Por tanto no hay zona DROP, ni log XNU, ni volumen HFS que actualizar: lo que toca es una **instalación completa**
  (borra USERDATA entero: `docs/herolte-howto.md`, pasos 2, 4, 5 y 6), que necesita el root (`root.img.gz.part*`) y el
  `d22ap.adt`, ambos del repositorio privado, y el firmware Wi-Fi de la VENDOR de este teléfono.
- Copias hechas (solo lectura, verificadas contra el hash del propio teléfono) en
  `~/HackiOS/backups/device-herolte/2026-11-12/`: BOOT, EFS, CPEFS, PERSISTENT, PARAM, PERSDATA, RECOVERY, BOTA0, BOTA1.
- Durante la sesión el USB se reenumeró tres veces (cable o puerto); TWRP volvió a aparecer en recovery cada vez y el
  nombre USB "SAMSUNG_Android" es el que usa también TWRP. Nada se escribió en el teléfono. Las copias se comprobaron
  tres veces (al hacerlas, y de nuevo tras reconectar): coinciden con las particiones.
- El final de USERDATA (donde DROP/log esperan su zona) contiene hoy datos de ext4: no hay log XNU en este teléfono.

## Cómo conseguir el root de iOS (20 GiB) — decisión pendiente del responsable
La cuenta de GitHub activa solo tiene el fork público (`ios-a5xelte`); el repo privado `ios-herolte-root` de la guía **no existe ahí**.
Opciones, de más a menos cómoda:
| Opción | Qué exige | Coste / riesgo |
|---|---|---|
| A. Repo **privado** propio + workflow `ios-root` | crear un repo privado, empujar la rama `ios-root-build`; corre en `macos-14` (hasta 180 min) y descarga el IPSW de Apple | las horas de macOS en repos privados se facturan ×10 sobre la cuota gratuita: **puede agotarla o generar cargos**; el responsable debe decidirlo |
| B. Construirlo en este PC (Linux) con `tools/mkiosroot.sh` | `apfs-fuse` (hay que compilarlo), `sudo` (monta una imagen en bucle y conserva propietarios), unos 40 GB de trabajo (hay 71 libres) y descargar ≈ 7 GB del IPSW (`tools/remotezip.py`) | sin coste de nube; requiere root en el PC y tiempo; el script es del donante SWEET (hay que revisarlo para HEROLTE) |
| C. Que lo facilite quien ya lo tenga (el responsable) | las partes `root.img.gz.part*` y `d22ap.adt` | ninguno, pero depende de él |
En cualquier caso la instalación **borra USERDATA entero** (todo el Android): consejo con el responsable antes de empezar.

## 0. Reglas que no se tocan
- Las pruebas de XNU escriben **solo BOOT** (`/dev/block/sda5` en el teléfono de pruebas). **Nunca** EFS, RECOVERY ni los
  bootloaders. Cualquier otra escritura en una partición se confirma con el responsable **antes**.
- La zona DROP vive al final de **USERDATA** (128 MiB bajo el log de 4 MiB, fuera del volumen HFSX): escribirla **es** una
  escritura en una partición distinta de BOOT → confirmación explícita (🛑 P3).
- BOOT original de Samsung y una copia de **EFS (IMEI)** hechas con TWRP, guardadas **fuera del teléfono**, antes de nada.
- No usar `fastboot flash`. Todo desde TWRP con `adb`, con `/data` desmontado.

## 1. Qué cambia en el teléfono
| Dónde | Qué | Cómo deshacerlo |
|---|---|---|
| BOOT (sda5, 40 MiB) | cargador + kernel DROP v2 + payload | volver a escribir la imagen BOOT guardada |
| USERDATA, zona DROP (bajo el log) | cabecera `HERODRP2` + paquete | `python3 tools/herolte-drop.py adb --clear` (pone la cabecera a cero) |
| Volumen iOS, `/private/var/herolte/.drop/` | estado, `ready`, `consumed`, restos de staging | inocuo; no lo lee iOS |
| Volumen iOS, `/private/var/herolte/v2test/` | ficheros de la autoprueba | borrable desde iOS o con un paquete posterior |

Nada más. DROP v2 solo escribe bajo `/private/var/herolte/` (el núcleo rechaza cualquier otra ruta y los nombres `.drop*`).

## 2. En el PC, sin teléfono
1. 🛑 **Decisión D5**: cómo entra el parche. Propuesto: `xnu/drop-v2/patches-proposed/0334-herolte-drop-v2.patch` →
   `xnu/patches/0334-herolte-drop-v2.patch`. Hasta entonces el CI **no** lo compila.
2. 🛑 Compilar con el CI (acción hacia fuera: empujar la rama y lanzar el workflow `xnu`, y `mesa-ios` para el `hero-run` nuevo).
3. **Comprobar que el parche se aplicó** (el CI salta en silencio los que no aplican):
   `gh run view <ID> --log | grep -E 'Applying patch: .*0334|Skipping patch .*0334'` → debe salir *Applying* y **no** *Skipping*.
4. Descargar los artefactos y ejecutar el *preflight* con el kernel nuevo:
   `python3 -I xnu/drop-v2/deviceday/preflight.py --kernel <kernel.development.herolte>` → **0 fallos**
   (comprueba que es DROP v2, que el kit está íntegro y que el paquete de autoprueba se instala en el núcleo C).
5. Construir las imágenes BOOT (necesita `d22ap.adt` del repo privado y el BOOT original):
   ```sh
   python3 tools/mkadt_herolte.py herolte.adt --bank2 --bank2-mb 2048 --iphone8
   python3 tools/herolte-adt-ram-banks.py herolte.adt herolte-3g.adt        # recomendado con 0326-0329
   python3 tools/mkpayload.py kernel.development.herolte herolte-3g.adt payload.bin --cmdline "$CMDLINE"
   python3 tools/herolte-pack-boot.py pack boot-stock.img <xnu_boot.Image> xnu-boot-v2.img --append payload.bin --partition-size 41943040
   ```
   `CMDLINE` es la de `docs/herolte-howto.md` (menos de 608 caracteres). Hacer **otra** imagen con `herodrop=0` añadido
   (`xnu-boot-v2-nodrop.img`): arranca iOS sin tocar nada de DROP, es la salida si el DROP v2 diera problemas.
   **Ojo:** la línea diaria mide 604 de 607 caracteres, así que `herodrop=0` (+12) no cabe sin quitar otro argumento; decidir cuál con el responsable.
   Cargador: `loader-clang/xnu_boot.Image` es de conveniencia (clang); el validado es el compilado con GCC aarch64.
6. Generar y mirar el paquete de autoprueba: `make_selftest.py OUT --variant a --generation 1` (y `b`, generación 2).
   La orden exacta queda en `OUT/command.txt`. **No ejecutarla** todavía.

## 3. Con el teléfono en TWRP (🛑 todo con el responsable)
**P0. Copias (solo lectura).** `adb shell dd if=/dev/block/sda5 of=/tmp/boot-actual.img` → `adb pull` → `sha256sum`.
EFS: *Backup → EFS* de TWRP y copiarlo fuera del teléfono. Anotar `ls -l /dev/block/platform/155a0000.ufs/by-name/`.
**Pregunta abierta:** ¿dónde está el BOOT original de Samsung? `herolte-pack-boot.py pack` parte de él.
**P1. Comprobación del teléfono (solo lectura).** `python3 -I xnu/drop-v2/deviceday/preflight.py --kernel <k> --device`
(BOOT = sda5 de 40 MiB, USERDATA = sda18, un único dispositivo en recovery).
**P2. 🛑 Escribir BOOT** (única escritura permitida de serie):
```sh
adb push xnu-boot-v2.img /tmp/boot.img
adb shell "dd if=/tmp/boot.img of=/dev/block/sda5 bs=1048576 conv=fsync"
adb shell "head -c $(stat -c %s xnu-boot-v2.img) /dev/block/sda5 | sha256sum"; sha256sum xnu-boot-v2.img   # iguales
```
**P3. 🛑 Escribir la zona DROP v2 (USERDATA, confirmación explícita):** la orden de `selftest-a/command.txt`
(el anfitrión borra la cabecera, escribe y verifica el contenido, escribe la cabecera sola y la verifica; ante cualquier
fallo la deja a cero). Salida esperada: `... -> verified`.
**P4. Arrancar iOS y esperar** unos minutos. Volver a TWRP y:
```sh
python3 tools/herolte-log-pull.py adb boot.txt                 # solo lectura
HEROLTE_ADB=adb python3 -I xnu/drop-v2/deviceday/verify_selftest.py selftest-a/expected.json   # solo lectura
```
**P5. Actualización:** repetir P3 con `selftest-b` (generación 2) y P4 con su `expected.json`: prueba que un paquete nuevo
sustituye al anterior por `rename` sin dejar restos.
**P6. Paquete real:** `autorun=hero-run` nuevo (artefacto `mesa-ios` posterior al cambio), libs y apps como en la guía.

## 4. Qué buscar en `boot.txt`
`grep -E 'HEROLTE DROP|jnl:|hero-run: app|HEROLTE UFS'`

| Mensaje | Significa |
|---|---|
| `HEROLTE DROP: package N ready for userland` | instalado y publicado (éxito) |
| `... resuming interrupted install of package N` | se recuperó una instalación cortada |
| `... v1 package ignored (repack with tools/herolte-drop.py v2)` | la zona aún trae el paquete antiguo; inocuo |
| `... payload does not match its SHA-256; package ignored` | zona dañada o a medio escribir; no se tocó nada |
| `... package rejected by validation (N); nothing written` | ruta/modo/tamaño no válidos |
| `... staging X: error N` / `stopped with error N; the next boot tries again` | fallo de E/S; reintenta (máx. 3) |
| `... F_FULLFSYNC failed` / `device cache flush failed` | **el sync del dispositivo falló** (lo importante de v2); no se publicó nada |
| `... abandoned after 3 attempts` | `FAILED` hasta una generación nueva (`--generation N+1` o `--force`) |
| `HEROLTE UFS: command 0x35 timed out` | `SYNCHRONIZE CACHE` con *timeout*; ver `docs/herolte-dma-smp-analysis.md` |
| `hero-run: app X: put in /Applications` | consumo de apps por hero-run (con el `hero-run` nuevo) |

## 5. Si algo va mal
| Síntoma | Acción |
|---|---|
| No arranca / pánico temprano | TWRP → escribir de nuevo el BOOT guardado en P0 (y verificar SHA) |
| Arranca pero DROP falla o se repite | escribir `xnu-boot-v2-nodrop.img` (`herodrop=0`) o `herolte-drop.py adb --clear` |
| Dudas sobre el volumen | no escribir nada; sacar el log y comparar con `verify_selftest.py` |
Volver a Android: escribir el BOOT original de Samsung y formatear Data (ver `docs/herolte-howto.md`).

## 6. Sin verificar hasta este momento (se verá en P4)
- `VNOP_IOCTL(rootvnode, F_FULLFSYNC)` desde un hilo del kernel; `renameat_internal` con contexto de kernel; uso de pila.
- Que el kernel con 0334 compile (nunca se ha compilado: solo hay comprobación de sintaxis contra cabeceras simuladas).
- `hero-run.c` nuevo (no compilado aquí; lo compila el CI de `mesa-ios`).
- Que `dd` de TWRP relea del dispositivo y no de la caché (`iflag=direct` sin confirmar).
- Los textos de `docs/herolte-howto.md` §5 ("copies ... on every boot") describen DROP v1; actualizarlos tras la prueba.

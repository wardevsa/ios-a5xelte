# DROP v2: núcleo y pruebas

Estado: **núcleo escrito y probado en anfitrión. No está integrado en el kernel, ni en `hero-run.c`, ni en
`tools/herolte-drop.py`, ni probado en el dispositivo.** Nada de este directorio está commiteado.

El protocolo actual (0332/0333) escribe en el sitio, sin barreras de persistencia. En el modelo de cortes de
alimentación deja destinos corruptos y paquetes mezclados, y 0333 añade un fallo de límites en `hdrop_at`
(ver `test_reader`). Este directorio es el sustituto propuesto.

## Contenido
- `herolte_drop_core.h/.c`: parser, máquina de estados y recuperación. Sin dependencias de XNU (todo entra por
  `hdc_ops`). Incluye su propio SHA-256, así que **no depende de corecrypto**.
- `test/fsmodel.py`: sistema de ficheros en memoria con cortes de alimentación (modelo pesimista, ver cabecera).
- `test/test_core.py`: ejecuta el C real mediante `ctypes` contra ese modelo.

## Cómo probar (solo anfitrión; no escribe en el repositorio ni toca dispositivos)
```
python3 -I xnu/drop-v2/test/test_core.py            # completo, ~2 min
python3 -I xnu/drop-v2/test/test_core.py --quick    # ~30 s
```
Compila el núcleo con `gcc -Wall -Wextra -Werror -fsanitize=undefined`. Con ASan:
`LD_PRELOAD=$(gcc -print-file-name=libasan.so) ASAN_OPTIONS=detect_leaks=0 HDC_LIB=/ruta/libhdc.so python3 -I ...`.

## Protocolo
Zona v2 (bloque 0): `"HERODRP2" | u32 proto=2 | u32 count | u64 bytes | u64 generation | u8 payload_sha256[32]`,
SHA-256 de los 4064 primeros bytes en `[4064,4096)`. Entradas como en v1 (`u32 len | u32 mode | u64 size | ruta | datos`,
alineadas a 8), pero el kernel exige que `count` y `bytes` cuadren exactamente.

Estado en el volumen, en `/private/var/herolte/.drop/`:
`state` (88 B con SHA-256), `stage/`, `stage.list`, `trash/NAME.app.<gen>`, `ready`, `consumed`.

Arranque (tras el remonte rw): `STAGED` → completar el commit desde `stage.list` (sin necesitar la zona). Si no,
validar TODO el paquete (cabecera, SHA-256 del payload, cada entrada) **antes de escribir nada**; después
`TRYING` → staging → `stage.list` → `STAGED` → barrera → commit por `rename` (ficheros sobre el destino; bundles
`apps/NAME.app` con el anterior a `trash`) → barrera → `COMMITTED` → barrera → `ready`.
`wifi/fw.bin` se commitea el último. Toda actualización de un fichero de control es `tmp` + barrera + `rename`.
Tres intentos por (SHA, generación); después `FAILED` hasta una generación nueva.

## Garantías que se usan y las que NO se prometen
Se usan: atomicidad de cada operación de metadatos HFS, su orden de journal y la barrera
(`F_FULLFSYNC` + `DKIOCSYNCHRONIZE` directo). Ver el informe de persistencia.
No se prometen: durabilidad ante la caché volátil del UFS, atomicidad multi-operación del sistema de ficheros,
ni detectar fallos de escritura asíncronos descartados. Lo que sí garantiza el diseño es que, bajo los supuestos del
modelo, el paquete se ve entero (nuevo o viejo), que `ready` nunca se publica sin `COMMITTED` duradero y que no hay
reinstalación en bucle.

## Resultados de las pruebas (gcc 13, Python 3.12)
Suite completa 36/36: SHA-256 frente a `hashlib`; el fuzz del lector reproduce el defecto de la expresión de 0333
(`fuera de la ventana`) y la versión corregida da 0; 19 paquetes inválidos no escriben nada; instalación,
idempotencia y consumo; paquete de varias ventanas; reintentos; 2560 imágenes de corte; fallo de cada una de las 8
barreras; 81 510 casos de doble fallo.

## Día del dispositivo (`deviceday/`) — preparado, sin ejecutar
`RUNBOOK.md` (guion con puertas 🛑 para el responsable y la regla de "solo BOOT"), `preflight.py` (comprobaciones del anfitrión;
`--kernel` clasifica si un kernel es DROP v2; `--device` solo lee), `make_selftest.py` / `verify_selftest.py` (paquete de
autoprueba y su verificación de solo lectura vía `tools/herolte-hfs-read.py`). El kit de artefactos descargados está en
`~/HackiOS/builds/device-day/` (fuera del repo).

## Kernel: `xnu/patches/0337-herolte-drop-v2.patch` — adoptado en la rama `herolte-drop-v2`; hasta el CI, SIN compilar
Aplica con `git apply` sobre el árbol con la serie hasta **0332** (comprobado contra el árbol exacto del CI, run 43020315155,
y el resultado es idéntico a las fuentes de este directorio). **No debe ir junto a 0333** (el borrador `0333-herolte-drop-block1-hardening`,
que 0334 deja sin efecto): con 0333 delante, 0334 no aplica y el CI lo salta en silencio. `preflight.py` lo comprueba. Sustituye por completo `bsd/dev/herolte_drop.c` (enlace fino sobre el
núcleo), añade `herolte_drop_core.{c,h}` a `bsd/conf/files` y dos exportaciones: `herolte_ufs_sync()` en
`herolte_ufs.c` (SYNCHRONIZE CACHE con el error real del driver) y `herolte_drop_rename()` en `vfs_syscalls.c`
(envoltorio de `renameat_internal`, que es `static`). Decisión D5 tomada por el jefe suplente (2026-11-12): se adopta como 0334 sobre 0332, pendiente de ratificación.
Comprobado: el núcleo compila con `clang -Weverything` sin avisos y con gcc `-Wall -Wextra -Werror`; el enlace y el
núcleo en modo kernel pasan `python3 -I xnu/drop-v2/test/check_kernel_syntax.py` (clang `-fsyntax-only` contra
cabeceras SIMULADAS en `test/kstub/` con las firmas copiadas de XNU 8796.141.3, incluidos `-Wmissing-prototypes`,
`-Wshorten-64-to-32` y `-Wcast-qual`, que XNU trata como error). Esa prueba ya cazó un fallo real (`hdc_rd_init` sin
prototipo). **No sustituye a compilar XNU**: no valida KPI fuera del simulacro, flags del kernel ni el enlazado.
El parche está generado con `git diff -B`, así que `herolte_drop.c` va como reescritura completa.
Sin verificar hasta una compilación real: `VNOP_IOCTL(rootvnode, F_FULLFSYNC)` desde un hilo del kernel, y la pila
(el núcleo usa unos 3 KB por la ruta más profunda).

### Riesgo del CI: un parche que no aplica se SALTA sin error
`build.sh` de darwin-xnu-build (commit fijado en `xnu.yml`) ejecuta primero `patches/*.sh` y luego `patches/*.patch` en
orden alfabético (0334 va tras 0333, bien), pero si `git apply --check` falla solo escribe "Skipping patch ..." y sigue.
Además, el paso de anotaciones de `xnu.yml` filtra a propósito esas líneas. Un 0334 que no aplicara dejaría el kernel
con el 0333 defectuoso y **sin ningún error**. Tras la primera compilación hay que buscar en el log
`Applying patch: .../0337-herolte-drop-v2.patch` y comprobar que no aparece su "Skipping patch".

## hero-run (`gpu/eagl/test/hero-run.c`) — hecho
`install_apps` espera `.drop/ready`; si es distinto de `.drop/consumed`, mueve las apps y escribe `consumed`
(tmp + fsync + rename). No borra `ready`. Con `ready` ya consumido sigue esperando (el kernel puede estar instalando
uno más nuevo). Compatibilidad: si solo existe el `apps/.ready` del protocolo v1, lo trata como antes. La lógica está en
`drop_v2_userland.h` (C puro) y se prueba con `test/test_userland.c`; `hero-run.c` en sí no se ha podido compilar aquí.

## Anfitrión (`tools/herolte-drop.py`) — hecho, probado con `adb` simulado
Escribe HERODRP2 en el orden cabecera a cero → payload (verificado) → cabecera sola (verificada); ante cualquier
fallo vuelve a poner la cabecera a cero. Opciones nuevas: `--generation N` (por defecto 1: mismo contenido y
generación se instala una sola vez) y `--force` (generación nueva). Rechaza los nombres reservados `.drop*` como el
núcleo. No toca la validación de rutas, Mach-O ni zips que ya tenía el fichero; se hizo copia previa fuera del
repositorio. `python3 -I xnu/drop-v2/test/test_host_pack.py` comprueba que el núcleo acepta byte a byte lo que
escribe el anfitrión. Límite conocido (ya existía): el anfitrión no emite directorios vacíos.
El readback de `dd` en TWRP puede salir de la caché de página; `iflag=direct` está sin confirmar.

## Lo que el modelo NO demuestra (abierto)
- Que `F_FULLFSYNC` funcione llamado desde un hilo del kernel, y que `herolte_ufs_sync()` (por crear) sirva como
  barrera fiable.
- Que `renameat_internal` (es `static`, `vfs_syscalls.c:8929`) funcione con contexto de kernel: hace falta un envoltorio.
- Que el volumen del S7 tenga journal y cómo hace replay; el estado de la caché de escritura del UFS.
- `rename` de directorios sobre HFS en este montaje, y `rename` sobre un destino abierto/mapeado.

## Decisiones tomadas (jefe suplente; revisables)
D1 los paquetes v1 se rechazan con un mensaje claro. D2 SHA-256 propio en el núcleo (sin corecrypto). D3 `wifi/`:
fusión por fichero con `fw.bin` el último (queda una carrera si el Wi-Fi ya leyó el par antiguo). D4 tres intentos.
D6 `herolte_ufs_sync()` exportada y usada tras cada `F_FULLFSYNC`. D7 estado en el volumen raíz.
**D8 aplazada:** `trash/` y los directorios huérfanos de `stage/` no se limpian (haría falta recorrer directorios);
pierden espacio, no corrompen nada.

## Pendiente, en este orden
1. ~~Enlace con el kernel~~ **escrito, sin compilar**: `patches-proposed/0337-herolte-drop-v2.patch` (ver abajo).
2. ~~`gpu/eagl/test/hero-run.c`~~ **hecho** (ver abajo); falta que lo compile el CI (necesita el SDK de Apple).
3. ~~`tools/herolte-drop.py`~~ **hecho** (ver abajo).
4. Compilación XNU controlada y, con autorización específica, el dispositivo.

# S7GE — N2 alcanzado: XNU arranca hasta `bsd_init` en el S7 (2026-11-15; L2, E-0177)

## Qué se ha visto
Con `min16` (kernel 0351, línea de arranque de `min2`: UFS en solo lectura y sin Wi-Fi/energía/GPU) la pantalla muestra, además de las 64 fases de `kernel_bootstrap`, el **registro del kernel** reflejado en un anillo de texto, y se sigue **actualizando**:
- `HEROLTE APM` (PMU, buzón, SRAM, "releasing the M3", S2MPS16, `LD032/LD033`) y `HEROLTE TOUCH` (táctil: id, estado, sondeo) — drivers propios del S7 arrancando.
- `HEROLTE GPU: probe disabled` — esperado (`herogpu=0`).
- `HEROLTE UFS: START STOP UNIT (ACTIVE`, comandos por LUN, `device W-LUN TEST UNIT` — el almacenamiento responde.
- `hfs_ValidateHFSPlusVolumeHeader`, `hfs_mount: hfs_mountfs returned error`, **`cannot mount root, errno = %d`** (repetido) — el kernel intenta montar la raíz como HFS+ y no puede: **USERDATA es ext4 de Android**.
- Pruebas internas de XNU (`Skywalk: sk_copy… PASSED`), `bsd_autoconf: calling kinit`, mensajes `zs: …`: el kernel sigue ejecutando.
No hay pánico ni volcado. **Es el resultado A de `S7GE_MIN_BOOT_VALIDATION.md`**: "llega a la consola de C, lee el UFS y falla al montar la raíz": **éxito de N2**.

## Corrección de mis lecturas anteriores (honesta)
Desde min2 hasta min13 interpreté la pantalla "azul, cian, magenta + XNU MMU ON" como un **reinicio** del kernel. **Probablemente era incorrecto**: esas marcas las dibuja `start.s` al principio y quedan sobre el framebuffer; el kernel llegaba hasta `bsd_init` y seguía vivo, pero **nada dibujaba** (la consola de vídeo de XNU no escribe en el búfer visible y mi consola temprana se apagaba tras `TTBR0`). Lo que sí fue real: el pánico de `min1` en `kmem_range_init` (sin `vm_compression_limit`), la caída de mi parche del alias (0343/0345) y los cuelgues de las imágenes `herostop` (paradas a propósito). El "reinicio" nunca se demostró: ninguna evidencia lo distingue de un kernel vivo sin salida visible. Corrijo aquí la narrativa de `S7GE_MIN2…MIN6_*`, `S7GE_HEROSTOP_BISECT.md` y el estado: **el kernel arranca desde `min2`**.

## Qué NO se ha demostrado
iOS no arranca: no hay raíz iOS (USERDATA sigue siendo Android ext4). La GPU, el Wi-Fi y la energía están apagados a propósito. Lo visto son cadenas de formato (los `%d` no son valores): no sabemos el `errno` exacto. No se ha comprobado cuánto tiempo sigue vivo ni si acaba en pánico por la raíz.

## Qué falta para iOS (en orden)
1. **Una raíz iOS HFS+ real** para meter en USERDATA (unos 20 GiB): `root.img.gz.part*` y `d22ap.adt` del repositorio privado `ios-herolte-root` (no disponible aquí), o construirla desde un IPSW con `tools/mkiosroot.sh` (necesita `apfs-fuse`, `sudo`, ~40 GB de trabajo y ~7 GB de descarga). **Decisión del Director**: cuál de las tres vías (A: repo privado propio + workflow `ios-root`; B: construirla en este PC; C: que la facilite quien la tenga).
2. **Escribir USERDATA** (borra Android): paso destructivo, con **autorización roja propia** que nombre la imagen y su hash. Las copias de SYSTEM y USERDATA ya están hechas y verificadas (E-0124, E-0125).
3. **Línea de arranque definitiva**: `ufsrw=1 rootrw=1` etc. (`herolte-howto.md` §4) en vez de `ufsrw=0`: es una escritura del kernel en USERDATA; otra autorización.
4. Cargar GPU/Wi-Fi/energía (`herogpu`, `herowifi`, `heropower`) **de uno en uno**, cada uno con su prueba y su permiso.

## Aclaración sobre `cannot mount root` repetido (leído en `bsd/kern/bsd_init.c`)
`bsd_init` monta la raíz dentro de un **`while (TRUE)`**: llama a `setconf()` y `vfs_mountroot()`; si falla, escribe `cannot mount root, errno = %d` y **vuelve a intentarlo** sin parar. Eso explica que el mensaje salga una y otra vez, que no haya pánico y que el kernel siga "vivo" indefinidamente: no es un reinicio ni un cuelgue, es el bucle de reintento de XNU. En cuanto exista una raíz HFS+ válida en USERDATA el bucle termina (`calling VFS_ROOT`, `IOSecureBSDRoot`, `bsd_utaskbootstrap` → `launchd`).

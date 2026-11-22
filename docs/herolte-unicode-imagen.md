# Imagen nueva con nombres en forma XNU (T-0025, 2026-11-13)

**Autoridad:** D-0017, D-0018, D-0020, D-0021 (autoriza `privileged-or-mount`, un solo uso, hasta el 2026-11-20), D-0023 (espacio) y D-0024 (copia de scripts). Nada se ha ejecutado en el teléfono. Nivel de evidencia hasta aquí: **L2** (sin montaje).

## 1. Qué está hecho (sin privilegios)
| Paso | Resultado | Evidencia |
|---|---|---|
| Espacio: T-0007 | 224 sandboxes archivados borrados por lista exacta (TAR verificado antes/después, `tar -d` rc=0); 5,2 → 30,4 GiB | E-0026 |
| Restaurar staging `r3/work` desde el TAR E-0013 | sha256 coincide; `tar -d` contra el TAR rc=0 | E-0028 |
| Scripts del laboratorio copiados a `tools/ios-root-lab/` con un único punto de traducción (`xnu_name_adapter.py`, usado por `q3lib.load_manifest`) | 17 pruebas OK; los originales NO se tocaron | `test_adapter.py` |
| Renombrar el staging `os` a forma XNU (`xnu_names_stage.py apply`) | **204 hojas** renombradas, 0 directorios, 0 colisiones; segunda pasada = 0 | E-0028 |
| Lista de exclusión (KI-0006) | **2 rutas** (`th.lproj`, `U+0E33`) | `out/xnu_excluded_paths.txt` |
| Manifiesto traducido frente al árbol renombrado (`verify_meta --skip-meta`) | 317 883 OK; **0 errores con nombre no ASCII** (185 errores: 181 destinos de symlinks y 4 ausentes, todos symlinks del staging previos al `apply`) | E-0028 |
| Imagen NUEVA vacía | `lab-full-xnu.img.partial`, 20 480 MiB, HFS+ con journal, `fsck` limpio | — |
| Imagen anterior | `lab-full.img.partial` intacta: sha256 `e724f981…c79496` = E-0010 | E-0028 |
| Ensayos en seco | `apply_meta_img` (318 068 entradas, 0 nombres sin traducir), `stage_links plan`, `hfsx_check` sobre la imagen vacía | — |
Los volúmenes `systemos` y `appos` no tienen ningún renombrado; solo `os` cambia.

## 2. Qué falta (necesita sudo; lo ejecuta el Director)
**Primer intento (2026-11-14):** el Director ejecutó `sudo ./populate_image.sh full-xnu` y `sudo ./verify_image.sh full-xnu` directamente; ambos abortaron en `img_common.sh` por falta de `IOS_ROOT_LAB` y `IOS_LAB_IMGDIR_EXPECT` (`sudo` borra el entorno) **antes de escribir nada** (comprobado: la imagen anterior conserva su sha256 `e724f981…`, la nueva sigue vacía). Los scripts exigen esas variables a propósito: la comprobación de que la carpeta de imágenes es la esperada no debe poder deducirse sola. **Solución (opción A):** un envoltorio con las variables fijadas, `xnu_sudo_run.sh`, en la carpeta de imágenes del laboratorio (probado sin privilegios: llega a `need_root` y rechaza argumentos desconocidos). Comandos en `COMANDOS_SUDO_XNU.md`: `sudo bash <carpeta-imagenes>/xnu_sudo_run.sh populate` (~12 GB) y después `... verify` (renombra a `.valid` solo si todo pasa). **No** se autoriza `r6_failure_tests.sh`. El ingeniero no tiene `sudo`.

## 3. Hallazgos durante la copia
- **Error corregido en mi herramienta:** `xnu_names_stage` usaba `hfs_component`, que convierte `:` en `/`; renombrar `a:b` a `a/b` habría movido el fichero a un directorio. Ahora no toca los `:` (los convierte el `hfsplus` de Linux). Prueba añadida.
- **Error del original:** `make_image.sh` solo daba 20 GiB al perfil exacto `full`; `full-xnu` salía con 2 GiB. Corregido en la copia. Dejé la imagen de 2 GiB (vacía, 24 MiB reales) renombrada `lab-mini-xnu0.img.partial` en lugar de borrarla (D-0021 no autoriza borrar).
- Las comprobaciones estrictas contra los DMG (`apfs_verify`) solo afectan a `systemos` y `appos`, que no cambian.

## 4. No verificado
Que el `hfsplus` real de Linux deje intactos los nombres en forma XNU (es el **modelo** validado, no un montaje); eso lo comprobará `verify_image.sh` (`hfsx_check` espera la forma XNU en el catálogo en bruto). Si falla, la imagen queda `.partial` y no se declara válida. El resultado de `verify_image.sh` será la primera evidencia real de montaje; hasta entonces **T-0025 no está cerrada**.

## 5. Resultado REAL del primer populate y verify (2026-11-14, E-0029)
`populate_image.sh full-xnu` terminó bien (rsync, stage, apply: 318 068 entradas del volumen `os`; ~4 min). `verify_image.sh full-xnu` dejó la imagen como `.partial` (`ROOT_HFSPLUS_LAB_FAILED`). **Lectura de los datos (no de la hipótesis):**
| Comprobación | Resultado |
|---|---|
| `hfsx_post` (lee el catálogo **en bruto** de la imagen, sin el driver de Linux) | **0 errores: 327 de 327 nombres no ASCII esperados en forma XNU exacta, 0 ausentes, 0 inesperados**; 5 nombres con `/` = los 5 `:` POSIX esperados |
| `fsck.hfsplus -n` antes y después | volumen OK |
| `meta_sys`, `meta_app`, `strict_sys` (1 459), `strict_app` (884), `stage` (75), `census` | todos OK |
| imagen antes/después de verificar | mismo sha256 (el montaje de solo lectura no la cambió) |
| `meta_os` | 318 068 OK; **2 EXTRA**; 195 `NAME-NORMALIZED` |
**Los 195 `NAME-NORMALIZED` no son un fallo ni el motivo del rc=1:** `verify_meta` los cuenta como **aviso** (no suman a `errores`; así está escrito desde el laboratorio, por eso existe la política `nfd-equiv`). Son nombres que el **driver de Linux recompone al LEER** (el disco guarda la forma XNU; `readdir` de Linux devuelve otra): en 174 de los 195 el nombre leído es exactamente `NFC(nombre del manifiesto)`; los otros 21 (hangul, etc.) son otra recomposición de Linux. Solo cambia el último componente en los 195. Por escritura: latino 136, griego 15, hangul 15, CJK 6, resto 23. **Esto confirma, con un montaje real, lo que el modelo predecía: Linux no descompone de más al escribir** (el catálogo en bruto tiene la forma XNU) **y solo difiere al leer.**
**Los 2 `EXTRA` que sí hicieron fallar son `.journal` y `.journal_info_block`**, los ficheros del diario HFS+ (`mkfs -J`). Eran el punto 5 de la corrección (docs/herolte-unicode-hfsplus.md §3) y **no lo había implementado: omisión mía**. Corregido en la copia (`tools/ios-root-lab/verify_image.sh` los añade a la lista de ignorados; prueba en `test_adapter.py`).
**Hipótesis del informe de jefatura:** A (el driver normaliza al leer) es cierta pero afecta a la *lectura*, no al disco; B (herramienta de renombrado) **descartada** (327/327 exactos en el catálogo y 0 sin procesar); C (más nombres problemáticos) **descartada** (solo los 2 de `U+0E33`, ya excluidos; `nonascii_on_disk_not_expected = 0`). **No hace falta** `nodecompose`, parchear XNU ni excluir más nombres.
**Pendiente:** repetir `verify_image.sh full-xnu` (montaje de solo lectura, no escribe) con el script corregido; si todo pasa se renombra a `.valid`. Hasta entonces T-0025 no está cerrada.

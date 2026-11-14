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

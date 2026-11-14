# Integración de `herolte-drop-v2` con `origin/herolte` (T-0009, 2026-11-13)

**Informe de solo lectura.** No se ha fusionado, renumerado ni publicado nada en este repositorio. Todas las pruebas se hicieron en **clones y directorios temporales**; los resultados están archivados (`E-0024`, SHA-256 en su `.sha256`). Autoridad: nivel verde (`read-analysis`, `docs-write`). La renumeración (T-0016) es amarilla y espera revisión.

## 1. Veredicto
| Pregunta | Respuesta medida |
|---|---|
| ¿Chocan los **contenidos**? | **No.** En una fusión de prueba hay **un solo conflicto de texto**: `HEROLTE_PROGRESS.md` (ambos lados añadieron secciones; se resuelve conservando las dos). `gpu/eagl/test/hero-run.c`, que tocaban los dos lados, **se fusiona solo**. |
| ¿Aplican los parches de las dos series? | **Sí, los 5, uno tras otro, en los dos órdenes posibles** (nombre de fichero del CI y nuestros-primero) sobre el árbol XNU parcheado hasta nuestro `0332`. |
| ¿Se pisan en ficheros? | **No** entre series: los nuestros tocan `herolte_drop*.c`, `herolte_ufs.c`, `vfs_syscalls.c`, `arm_init.c`; los de upstream, `SweetSurface.cpp` y `herolte_gpu.c`. |
| ¿Chocan los **números**? | **Sí, pero solo dos:** `0332` y `0334`. Upstream no usa el `0335` (llega a `0334`): **mi propuesta D-0008 sobrestimaba el problema** (decía también 0335). |
| ¿Es solo estético? | **No:** hay dos riesgos reales (§4), uno de ellos silencioso. |

## 2. Qué trae upstream (13 commits desde la base común `a43e3e5`)
- **Núcleo:** `0332-surface-wrap-only-the-pixels` (`SweetSurface.cpp`), `0333-gpu-wait-asleep` y `0334-present-wait-asleep` (`bsd/dev/herolte_gpu.c`): esperar al job de GPU durmiendo (trozos de 50 µs) en lugar de girar en `delay(10)`, y lo mismo para el escalado del cuadro. Las notas de upstream los dan por probados en su teléfono (más fluido, menos calor): evidencia **L4h**, no de esta unidad.
- **Espacio de usuario:** cambios en `gpu/eagl/src/heroapp.c`, `gpu/hakios-gl/src/eagl.c`, `gpu/eagl/build-eagl.sh`, `gpu/eagl/test/hero-run.c`; `tools/herolte-wallpaper-png.sh` (fondos HEIC a PNG).
- **CI:** `ios-root.yml` pasa a `macos-15`/`macos-15-intel`.
- **Notas:** `HEROLTE_PROGRESS.md`.
Nuestra rama lleva 35 commits que upstream no tiene (DROP v2, N2, herramientas del root, Unicode, S7GE, gobierno).

## 3. Cómo se midió (reproducible)
1. `git clone --shared` del repositorio a un directorio temporal. **El repositorio es un clon parcial** (`[blob:none]`): `git merge` falla allí con `unable to read blob` porque faltan blobs de upstream. En el clon temporal se configura `gh` (la URL pública de `origin`) como remoto *promisor* y los blobs se traen bajo demanda (lectura; no se envía nada).
2. `git merge --no-commit --no-ff up` → conflicto único en `HEROLTE_PROGRESS.md` (líneas 411-442 del fichero fusionado). Resultado: `trial-merge.out`, `unresolved.txt`, `progress-conflict-hunk.txt`.
3. Árbol XNU parcheado hasta nuestro `0332`: `~/HackiOS/builds/device-day/artifacts/buildtree-0332-fork-8d1cf43/buildtree.tgz` (**caduca el 2026-11-18**). Se extraen `bsd`, `iokit`, `osfmk`, `config`, `makedefs`, `libkern`, `EXTERNAL_HEADERS` y se aplican con `git apply -p1`, **comprobando antes con `--check`**, en este orden (el del CI, por nombre de fichero): `0332-surface-wrap` (up) → `0333-gpu-wait-asleep` (up) → `0334-herolte-drop-v2` (nuestro) → `0334-present-wait-asleep` (up) → `0335-herolte-boot-splash` (nuestro). Después, el orden inverso (nuestros primero). **5/5 aplican en ambos.** Registro con SHA-256 de cada parche: `apply-sequence.txt`.
4. Los parches de la serie de upstream se leen de `origin/herolte` (`git show up:xnu/patches/…`); los nuestros, de `xnu/patches/`.
**Límite:** esto prueba la **aplicabilidad de los parches**, no que el kernel resultante compile ni funcione. Eso lo hace el CI (acción roja `publish`) y, después, el teléfono (roja).

## 4. Riesgos reales de dejar los números como están
1. **Falso "aplicado" (silencioso).** `xnu/drop-v2/deviceday/ci_check.py` identifica el parche por el prefijo `0334-` (por defecto) y `preflight.py` busca "parche 0334"; ese prefijo casa **con nuestro DROP v2 y con el `present-wait-asleep` de upstream**. Si el nuestro se saltara y el de ellos se aplicara, la comprobación diría "aplicado": justo el fallo que la herramienta existe para detectar.
2. **Orden por desempate de nombre.** Con dos `0332` y dos `0334`, el orden de aplicación depende del orden alfabético del resto del nombre (`herolte-drop…` antes que `surface…`/`present…`). Hoy es inocuo (parches independientes), pero un parche futuro que toque los mismos ficheros dependería de ese desempate invisible.
3. **`tools/validate-repo.py`** ya falla con huecos y los duplicados añadirían errores (KI-0001).
4. **El kernel de la candidata N2 (`e678b454…`) no incluye `0332`-`0334` de upstream.** Si se fusiona y se reconstruye, el kernel cambia y **la candidata N2 debe regenerarse y volver a verificarse** (nombre nuevo; la actual se conserva).
**No hay riesgo de contenido ni de aplicabilidad:** los dos primeros son de identificación y trazabilidad.

## 5. Opciones
| Opción | Qué hace | Ventajas | Inconvenientes |
|---|---|---|---|
| **R1 (recomendada)** | Renumerar **solo los dos que colisionan** y mantener el orden relativo: `0332-herolte-drop-marker-protocol` → `0336-…`, `0334-herolte-drop-v2` → `0337-…`; `0335-herolte-boot-splash` se queda | Cero números repetidos; upstream no se toca; el `0335` de nuestro splash sigue sin colisión | Hay que actualizar **25 ficheros** que citan `0334` y **22** que citan `0332` (documentos, `ci_check.py`, `preflight.py`, `check_kernel_syntax.py`, nombres de artefacto); ojo: `0334` también aparece en nombres de **artefactos** (`kernel-0334-v2-…`) que **no** son el parche |
| R2 | No renumerar: `ci_check.py`/`preflight.py` usan el nombre completo del parche | Sin cambios de nombres; arreglo pequeño | Sigue habiendo dos `0332` y dos `0334`; `validate-repo.py` fallará más; el desempate sigue siendo implícito |
| R3 | Renumerar las dos series | — | Rompe la trazabilidad con las notas de upstream y con lo ya probado en su teléfono: **no recomendada** |
Mi recomendación: **R1 y, además, el arreglo de R2 en `ci_check.py`** (que exija nombre completo), porque es un fallo latente independiente del número. La renumeración (T-0016) es de nivel amarillo y **no se ha hecho**. El arreglo de `ci_check.py`/`preflight.py` (T-0022, solo herramientas, verde) **sí está hecho**: exige el nombre completo y rechaza `0334`/`0334-` como ambiguo (salida 2); pruebas en `xnu/drop-v2/test/test_ci_check.py`.

## 6. Propuesta de ejecución (T-0016, cuando se apruebe)
1. Rama de trabajo desde `herolte-drop-v2`; `git mv` de los dos parches (con `git log --follow` conservando historia).
2. Actualizar referencias **solo** donde `0332`/`0334` signifiquen el parche (no los nombres de artefacto): lista con `git grep -n`.
3. `git merge origin/herolte` y resolver `HEROLTE_PROGRESS.md` conservando ambas secciones (el conflicto es solo de adición).
4. Reproducir la prueba de aplicación (§3) con la serie definitiva en **los dos órdenes**; comprobar que `validate-repo.py` no empeora (hoy 5 errores).
5. Lanzar el CI (**acción roja `publish`: necesita autorización**), comprobar con `ci_check.py` por nombre completo, regenerar el kernel, reconstruir y reverificar la candidata N2 con nombre nuevo.
6. Registrar en `HEROLTE_PROGRESS.md` solo evidencia con su dispositivo.

## 7. Qué NO se ha hecho y qué falta
Compilar el kernel combinado; ejecutar el CI; fusionar de verdad; renumerar; comprobar la serie de parches de **nuestra rama completa** (solo se aplicaron los dos extremos que difieren: el árbol base ya trae los comunes); ninguna prueba en el teléfono.

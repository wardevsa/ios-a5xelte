# Bloqueo Unicode del root HFS+: causa, corrección propuesta y lo que falta (2026-11-13)

**Estado:** análisis de solo lectura. No se ha montado nada, no se ha ejecutado R2 ni `sudo`, no se ha tocado `lab-full.img.partial` (SHA-256 `e724f981…c79496`, intacto) ni ninguna herramienta de generación del root. Todo lo que sigue sale de la
imagen ya poblada, de los manifiestos, del **código de XNU compilado en el PC** y de la **tabla del módulo `hfsplus.ko` del kernel de este PC** (el mismo con el que se pobló la imagen).

## 1. Causa (comprobada)
La discrepancia nace en **la tabla de descomposición Unicode del `hfsplus` de Linux**, que escribió en el catálogo nombres distintos de los que XNU y `fsck_hfs` consideran correctos. No es del generador, ni de la enumeración, ni de la comparación.

| Eslabón | Veredicto | Evidencia |
|---|---|---|
| Origen de los nombres (`7z` → manifiestos) | correcto | los 329 nombres no ASCII distintos de los tres manifiestos; ninguno fuera del BMP; ninguno es directorio (solo ficheros hoja) |
| Copia (`populate_image.sh`: `rsync -aH --numeric-ids`, montaje `mount -t hfsplus -o force,rw,nosuid,nodev,noexec`, `img_common.sh:27-28`) | correcto, pero **sin `nodecompose`**: Linux decompone cada nombre al crearlo | `grep nodecompose` en `r3/tools/*.sh`: ninguna coincidencia |
| **Escritura en el catálogo (Linux `hfsplus`)** | **aquí está la divergencia** | la tabla del módulo (offset `0x15640` de `hfsplus.ko`) reproduce **los 329 nombres que hay en la imagen, 329 de 329**; la forma XNU solo coincide en 297 |
| Enumeración (`catalog_dump.py`, catálogo en bruto) | correcta | lee los bytes UTF-16 del catálogo |
| Comparación (`hfsx_check.py:96`, `unicodedata.normalize('NFD', …)`) | correcta | su "esperado" coincide con XNU en los 329 (el modelo difiere de XNU solo en U+2400, que no aparece); acusó una divergencia real |
| `fsck_hfs` | usa la tabla de Apple | sus nombres `replacement` son exactamente la forma XNU en los 32 casos; sus `illegal`, exactamente la forma Linux |
| Por qué no lo vio `verify_meta.py` | lee por el montaje de Linux, que **recompone** al leer (`uni2asc`): ve el nombre original | solo marcó 2 `EXTRA` (`.journal`, `.journal_info_block`: ficheros del propio diario HFS+) y 1 `NAME-NORMALIZED` (un nombre hindi que **sí** coincide con XNU en disco; es un efecto de la lectura de Linux) |
| Por qué no lo vieron las pruebas previas | `r6_failure_tests.sh:63` (T8) prueba un único nombre, `é` → U+0301, donde Linux y XNU **coinciden** | |

Referencias de XNU (árbol de la compilación del CI, `buildtree-0332-fork-8d1cf43`): `bsd/vfs/vfs_utfconv.c` (`utf8_decodestr` con `UTF_DECOMPOSED`, `unicode_decompose`, `unicode_recursive_decompose`, tablas de `vfs_utfconvdata.h` derivadas de CoreFoundation) y `bsd/sweet_hfs/core/hfs_catalog.c:3529-3530`
(`utf8_flags |= UTF_DECOMPOSED` al construir la clave del catálogo): **XNU busca cada nombre descompuesto con esa tabla**. Un nombre guardado con otra descomposición no se encuentra por su nombre (hipótesis, §6).

### Alcance real: 144 caracteres del BMP
Comparando XNU (su propio código, compilado en el PC) con la tabla de Linux sobre todos los caracteres U+0080-FFFF: **difieren en 144**, entre ellos latín extendido (U+01F8-01F9, 0218-021B, 021E-021F, 0226-0233), griego con tonos (U+0385-0390, 03AC-03B0, 03CC-03CE, 1F80-1FFF…), cirílico, árabe (U+0622-0626, 06C0, 06C2, 06D3), devanagari/bengalí/gurmukhi, cingalés, tibetano, tailandés y lao (U+0E33, 0EB3) y hebreo (U+FB1D). El catálogo del IPSW actual solo usa 32 nombres con esos caracteres, pero **cualquier root futuro con otros nombres tendría el mismo problema**. Lista completa: `tools/hfsplus-names/` (se regenera con las pruebas).

## 2. Los 32 nombres discrepantes
Puntos de código (no se copian los nombres de ficheros de Apple). Todos son `System/Library/PrivateFrameworks/WorkflowKit.framework/<idioma>.lproj/DefaultShortcuts/<GUID>/*.shortcut`. Clases: **A** árabe 9, **G** griego 15, **R** rumano 6, **T** tailandés 2.

| # | Idioma (`*.lproj`) | Clase | Manifiesto (no ASCII) | Linux escribió | XNU/`fsck_hfs` esperan |
|---|---|---|---|---|---|
| 1 | ar (`0F03F469…`) | A | 0625 0638 0647 0627 0631 0644 0642 0637 0627 062A 0627 0644 0634 0627 0634 0629 | 0625 0638 0647 0627 0631 0644 0642 0637 0627 062A 0627 0644 0634 0627 0634 0629 | 0627 0655 0638 0647 0627 0631 0644 0642 0637 0627 062A 0627 0644 0634 0627 0634 0629 |
| 2 | ar (`2AE55CAB…`) | A | 0623 062E 0630 0631 0627 062D 0629 | 0623 062E 0630 0631 0627 062D 0629 | 0627 0654 062E 0630 0631 0627 062D 0629 |
| 3 | ar (`4834D8BA…`) | A | 0627 0644 0627 062A 062C 0627 0647 0627 062A 0625 0644 0649 0627 0644 062D 062F 062B | 0627 0644 0627 062A 062C 0627 0647 0627 062A 0625 0644 0649 0627 0644 062D 062F 062B | 0627 0644 0627 062A 062C 0627 0647 0627 062A 0627 0655 0644 0649 0627 0644 062D 062F 062B |
| 4 | ar (`57BB80F1…`) | A | 0625 0646 0634 0627 0621 | 0625 0646 0634 0627 0621 | 0627 0655 0646 0634 0627 0621 |
| 5 | ar (`88A99A0E…`) | A | 0625 0631 0633 0627 0644 0622 062E 0631 0635 0648 0631 0629 0641 064A 0628 0631 064A 062F 0625 0644 0643 062A 0631 0648 0646 064A | 0625 0631 0633 0627 0644 0622 062E 0631 0635 0648 0631 0629 0641 064A 0628 0631 064A 062F 0625 0644 0643 062A 0631 0648 0646 064A | 0627 0655 0631 0633 0627 0644 0627 0653 062E 0631 0635 0648 0631 0629 0641 064A 0628 0631 064A 062F 0627 0655 0644 0643 062A 0631 0648 0646 064A |
| 6 | ar (`B8393B0D…`) | A | 0628 0631 064A 062F 0625 0644 0643 062A 0631 0648 0646 064A 0628 0627 0644 062A 0623 062E 0631 | 0628 0631 064A 062F 0625 0644 0643 062A 0631 0648 0646 064A 0628 0627 0644 062A 0623 062E 0631 | 0628 0631 064A 062F 0627 0655 0644 0643 062A 0631 0648 0646 064A 0628 0627 0644 062A 0627 0654 062E 0631 |
| 7 | ar (`BBDE81F9…`) | A | 0631 0633 0627 0644 0629 0646 0635 064A 0629 0628 0627 0644 062A 0623 062E 0631 | 0631 0633 0627 0644 0629 0646 0635 064A 0629 0628 0627 0644 062A 0623 062E 0631 | 0631 0633 0627 0644 0629 0646 0635 064A 0629 0628 0627 0644 062A 0627 0654 062E 0631 |
| 8 | ar (`D04ABF0D…`) | A | 0625 0631 0633 0627 0644 0627 0644 0635 0648 0631 0628 0627 0633 062A 062E 062F 0627 0645 | 0625 0631 0633 0627 0644 0627 0644 0635 0648 0631 0628 0627 0633 062A 062E 062F 0627 0645 | 0627 0655 0631 0633 0627 0644 0627 0644 0635 0648 0631 0628 0627 0633 062A 062E 062F 0627 0645 |
| 9 | ar (`EB9E040E…`) | A | 0625 0631 0633 0627 0644 0622 062E 0631 0635 0648 0631 0629 0641 064A 0631 0633 0627 0644 0629 0646 0635 064A 0629 | 0625 0631 0633 0627 0644 0622 062E 0631 0635 0648 0631 0629 0641 064A 0631 0633 0627 0644 0629 0646 0635 064A 0629 | 0627 0655 0631 0633 0627 0644 0627 0653 062E 0631 0635 0648 0631 0629 0641 064A 0631 0633 0627 0644 0629 0646 0635 064A 0629 |
| 10 | el (`0C6A13DC…`) | G | 03A4 03B9 03B5 03AF 03BD 03B1 03B9 03B7 03C3 03C5 03BD 03C4 03CC 03BC 03B5 03C5 03C3 03B7 | 03A4 03B9 03B5 03B9 030D 03BD 03B1 03B9 03B7 03C3 03C5 03BD 03C4 03BF 030D 03BC 03B5 03C5 03C3 03B7 | 03A4 03B9 03B5 03B9 0301 03BD 03B1 03B9 03B7 03C3 03C5 03BD 03C4 03BF 0301 03BC 03B5 03C5 03C3 03B7 |
| 11 | el (`0F03F469…`) | G | 03A3 03C4 03B9 03B3 03BC 03B9 03CC 03C4 03C5 03C0 03B1 03BF 03B8 03CC 03BD 03B7 03C2 | 03A3 03C4 03B9 03B3 03BC 03B9 03BF 030D 03C4 03C5 03C0 03B1 03BF 03B8 03BF 030D 03BD 03B7 03C2 | 03A3 03C4 03B9 03B3 03BC 03B9 03BF 0301 03C4 03C5 03C0 03B1 03BF 03B8 03BF 0301 03BD 03B7 03C2 |
| 12 | el (`1401D3FE…`) | G | 03A3 03C5 03BD 03C4 03CC 03BC 03B5 03C5 03C3 03B7 | 03A3 03C5 03BD 03C4 03BF 030D 03BC 03B5 03C5 03C3 03B7 | 03A3 03C5 03BD 03C4 03BF 0301 03BC 03B5 03C5 03C3 03B7 |
| 13 | el (`15FCD3E5…`) | G | 0391 03C0 03BF 03BA 03BB 03B5 03B9 03C3 03BC 03CC 03C2 03BC 03AF 03B1 03C2 03CE 03C1 03B1 03C2 | 0391 03C0 03BF 03BA 03BB 03B5 03B9 03C3 03BC 03BF 030D 03C2 03BC 03B9 030D 03B1 03C2 03C9 030D 03C1 03B1 03C2 | 0391 03C0 03BF 03BA 03BB 03B5 03B9 03C3 03BC 03BF 0301 03C2 03BC 03B9 0301 03B1 03C2 03C9 0301 03C1 03B1 03C2 |
| 14 | el (`2AE55CAB…`) | G | 038F 03C1 03B1 03B3 03B9 03B1 03B4 03B9 03AC 03BB 03B5 03B9 03BC 03BC 03B1 | 03A9 030D 03C1 03B1 03B3 03B9 03B1 03B4 03B9 03B1 030D 03BB 03B5 03B9 03BC 03BC 03B1 | 03A9 0301 03C1 03B1 03B3 03B9 03B1 03B4 03B9 03B1 0301 03BB 03B5 03B9 03BC 03BC 03B1 |
| 15 | el (`4834D8BA…`) | G | 039F 03B4 03B7 03B3 03AF 03B5 03C2 03C0 03C1 03BF 03C2 03B3 03B5 03B3 03BF 03BD 03CC 03C2 | 039F 03B4 03B7 03B3 03B9 030D 03B5 03C2 03C0 03C1 03BF 03C2 03B3 03B5 03B3 03BF 03BD 03BF 030D 03C2 | 039F 03B4 03B7 03B3 03B9 0301 03B5 03C2 03C0 03C1 03BF 03C2 03B3 03B5 03B3 03BF 03BD 03BF 0301 03C2 |
| 16 | el (`57BB80F1…`) | G | 0394 03B7 03BC 03B9 03BF 03C5 03C1 03B3 03AF 03B1 | 0394 03B7 03BC 03B9 03BF 03C5 03C1 03B3 03B9 030D 03B1 | 0394 03B7 03BC 03B9 03BF 03C5 03C1 03B3 03B9 0301 03B1 |
| 17 | el (`86D44848…`) | G | 0394 03B7 03BC 03B9 03BF 03C5 03C1 03B3 03AF 03B1 03BA 03C9 03B4 03B9 03BA 03BF 03CD | 0394 03B7 03BC 03B9 03BF 03C5 03C1 03B3 03B9 030D 03B1 03BA 03C9 03B4 03B9 03BA 03BF 03C5 030D | 0394 03B7 03BC 03B9 03BF 03C5 03C1 03B3 03B9 0301 03B1 03BA 03C9 03B4 03B9 03BA 03BF 03C5 0301 |
| 18 | el (`88A99A0E…`) | G | 03BC 03B5 03C0 03C1 03CC 03C3 03C6 03B1 03C4 03B7 03C6 03C9 03C4 03CC | 03BC 03B5 03C0 03C1 03BF 030D 03C3 03C6 03B1 03C4 03B7 03C6 03C9 03C4 03BF 030D | 03BC 03B5 03C0 03C1 03BF 0301 03C3 03C6 03B1 03C4 03B7 03C6 03C9 03C4 03BF 0301 |
| 19 | el (`8930EAB0…`) | G | 039A 03BF 03C5 03AF 03B6 03BC 03BF 03C5 03C3 03B9 03BA 03AE 03C2 | 039A 03BF 03C5 03B9 030D 03B6 03BC 03BF 03C5 03C3 03B9 03BA 03B7 030D 03C2 | 039A 03BF 03C5 03B9 0301 03B6 03BC 03BF 03C5 03C3 03B9 03BA 03B7 0301 03C2 |
| 20 | el (`B8393B0D…`) | G | 03B3 03B9 03B1 03BA 03B1 03B8 03C5 03C3 03C4 03AD 03C1 03B7 03C3 03B7 | 03B3 03B9 03B1 03BA 03B1 03B8 03C5 03C3 03C4 03B5 030D 03C1 03B7 03C3 03B7 | 03B3 03B9 03B1 03BA 03B1 03B8 03C5 03C3 03C4 03B5 0301 03C1 03B7 03C3 03B7 |
| 21 | el (`BBDE81F9…`) | G | 039A 03B5 03AF 03BC 03B5 03BD 03BF 03BA 03B1 03B8 03C5 03C3 03C4 03AD 03C1 03B7 03C3 03B7 03C2 | 039A 03B5 03B9 030D 03BC 03B5 03BD 03BF 03BA 03B1 03B8 03C5 03C3 03C4 03B5 030D 03C1 03B7 03C3 03B7 03C2 | 039A 03B5 03B9 0301 03BC 03B5 03BD 03BF 03BA 03B1 03B8 03C5 03C3 03C4 03B5 0301 03C1 03B7 03C3 03B7 03C2 |
| 22 | el (`D04ABF0D…`) | G | 0391 03C0 03BF 03C3 03C4 03BF 03BB 03AE 03C6 03C9 03C4 03CC 03BC 03AD 03C3 03C9 | 0391 03C0 03BF 03C3 03C4 03BF 03BB 03B7 030D 03C6 03C9 03C4 03BF 030D 03BC 03B5 030D 03C3 03C9 | 0391 03C0 03BF 03C3 03C4 03BF 03BB 03B7 0301 03C6 03C9 03C4 03BF 0301 03BC 03B5 0301 03C3 03C9 |
| 23 | el (`EB9E040E…`) | G | 039C 03AE 03BD 03C5 03BC 03B1 03BC 03B5 03C0 03C1 03CC 03C3 03C6 03B1 03C4 03B7 03C6 03C9 03C4 03CC | 039C 03B7 030D 03BD 03C5 03BC 03B1 03BC 03B5 03C0 03C1 03BF 030D 03C3 03C6 03B1 03C4 03B7 03C6 03C9 03C4 03BF 030D | 039C 03B7 0301 03BD 03C5 03BC 03B1 03BC 03B5 03C0 03C1 03BF 0301 03C3 03C6 03B1 03C4 03B7 03C6 03C9 03C4 03BF 0301 |
| 24 | el (`F28AE0DE…`) | G | 039D 03AD 03B1 03C3 03B7 03BC 03B5 03AF 03C9 03C3 03B7 03BC 03B5 03B7 03BC 03B5 03C1 03BF 03BC 03B7 03BD 03AF 03B1 | 039D 03B5 030D 03B1 03C3 03B7 03BC 03B5 03B9 030D 03C9 03C3 03B7 03BC 03B5 03B7 03BC 03B5 03C1 03BF 03BC 03B7 03BD 03B9 030D 03B1 | 039D 03B5 0301 03B1 03C3 03B7 03BC 03B5 03B9 0301 03C9 03C3 03B7 03BC 03B5 03B7 03BC 03B5 03C1 03BF 03BC 03B7 03BD 03B9 0301 03B1 |
| 25 | ro (`0F03F469…`) | R | 0219 021B | 0219 021B | 0326 0326 |
| 26 | ro (`15FCD3E5…`) | R | 021B 0103 | 021B 0306 | 0326 0306 |
| 27 | ro (`2AE55CAB…`) | R | 021B 0103 | 021B 0306 | 0326 0306 |
| 28 | ro (`B8393B0D…`) | R | 2011 021B 00EE 00E2 | 2011 021B 0302 0302 | 2011 0326 0302 0302 |
| 29 | ro (`BBDE81F9…`) | R | 021B 00EE 00E2 | 021B 0302 0302 | 0326 0302 0302 |
| 30 | ro (`F28AE0DE…`) | R | 021B 0103 0103 0103 | 021B 0306 0306 0306 | 0326 0306 0306 0306 |
| 31 | th (`0C6A13DC…`) | T | 0E04 0E33 0E2A 0E31 0E48 0E07 0E25 0E31 0E14 0E04 0E37 0E2D 0E2D 0E30 0E44 0E23 | 0E04 0E4D 0E32 0E2A 0E31 0E48 0E07 0E25 0E31 0E14 0E04 0E37 0E2D 0E2D 0E30 0E44 0E23 | 0E04 0E33 0E2A 0E31 0E48 0E07 0E25 0E31 0E14 0E04 0E37 0E2D 0E2D 0E30 0E44 0E23 |
| 32 | th (`1401D3FE…`) | T | 0E04 0E33 0E2A 0E31 0E48 0E07 0E25 0E31 0E14 | 0E04 0E4D 0E32 0E2A 0E31 0E48 0E07 0E25 0E31 0E14 | 0E04 0E33 0E2A 0E31 0E48 0E07 0E25 0E31 0E14 |

Clave: A = alef con hamza arriba/abajo (U+0623/0625): Linux no la descompone, XNU en U+0627 + U+0654/0655. G = tonos: Linux emite U+030D (línea vertical), XNU/Unicode U+0301. R = coma bajo (U+0219/021B): Linux no descompone, XNU en `s`/`t` + U+0326.
T = SARA AM (U+0E33): Linux lo descompone en U+0E4D U+0E32, **XNU lo deja entero**. Por eso `nodecompose` solo no basta con nombres "por defecto": con la descomposición de Linux el nombre tailandés quedaría mal aunque lo pasáramos ya en forma XNU.

## 3. Corrección mínima propuesta (NO aplicada; espera tu decisión)
1. **Montar con `nodecompose`** en `attach()` (`img_common.sh`) para todas las operaciones de escritura y también las de verificación (solo lectura), de modo que Linux guarde y devuelva los nombres tal cual.
2. **Entregar a Linux los nombres ya en forma XNU**: antes del `rsync`, renombrar en el árbol extraído (ext4, sin root) cada fichero cuyo nombre cambie al aplicar `hfs_names.hfs_component()` (`tools/hfsplus-names/hfs_names.py`: descomposición Unicode 3.2 sin los rangos U+2000-2FFF, F900-FAFF, 2F800-2FAFF y con ordenación canónica; validada contra el código real de XNU).
   Solo hay ficheros hoja (ningún directorio con nombre no ASCII), así que son renombrados sin efectos en rutas intermedias; 0 colisiones y 141 unidades UTF-16 como máximo (límite 255) tras la forma XNU.
3. **Un único punto de traducción** manifiesto → ruta en la imagen: `apply_meta_img.py`, `stage_links.py`, `verify_meta.py` y `hfsx_check.py` deben usar la forma `hfs_component()` al localizar un nombre del manifiesto (y `hfsx_check` esperar la forma XNU en el catálogo en bruto en lugar de `normalize('NFD')`).
4. Cambiar el modelo de `names_static.py` (`hfs_nfd`, basado en el NFD de Unicode actual) por el de `hfs_names.xnu_nfd` (Unicode 3.2): hoy coinciden en los 329 nombres, pero no hay garantía en general.
5. Aceptar `.journal` y `.journal_info_block` como `EXTRA` esperados (ficheros del diario HFS+) en `verify_meta.py`.
Alternativas, de menor a mayor cambio: **(B)** dejar el root tal cual y documentar 32 rutas con nombre distinto (el arranque no depende de ellas; `fsck_hfs` seguiría diciendo "corrupt"); **(C)** excluir esos 32 ficheros del root; **(D)** parchear la tabla del módulo de Linux (descartada: toca el kernel del PC).
Recomendación: la corrección 1-5, **si R2 la confirma**; mientras tanto (B) es el estado actual.

## 4. Pruebas sintéticas (no tocan la imagen) — implementadas, solo de análisis
`python3 -W ignore tools/hfsplus-names/test_hfs_names.py`: **9 pruebas OK, 0 omitidas**. Necesitan `gcc` y el árbol del CI para compilar el `utfconv` de XNU (`build_xnu_nfd.sh`) y el `hfsplus.ko` del kernel en ejecución.
- Vectores conocidos del modelo XNU (é, U+0625, U+0219/021B, U+03AF, U+0E33, U+2126 excluido, Hangul, ordenación de marcas).
- **Diferencial contra XNU real, exhaustivo en el BMP** (63 360 caracteres): idéntico salvo U+2400 (la "NUL alternativa" de la API, que XNU devuelve como `/`; no es un nombre real). Más 3000 cadenas aleatorias con marcas combinantes: idénticas.
- Modelo de la tabla de Linux: resultados esperados en los casos conocidos, y **144 caracteres del BMP donde difiere de XNU** (si cambia el kernel, este número cambia: es una alarma).
- **Regresión de la evidencia**: la tabla de Linux explica 329/329 nombres del catálogo de la imagen; la forma XNU falta en exactamente 32; 0 colisiones.
- Idempotencia, colisiones NFC/NFD en un mismo directorio y límite de 255 unidades.
Pendientes de escribir cuando se apruebe aplicar la corrección: prueba del renombrado previo sobre un árbol sintético (`fakeroot`, sin montar) y de la traducción manifiesto→ruta en las cuatro herramientas.

## 5. Lo que ya está demostrado (no necesita R2)
- Linux (esta máquina) escribió los 329 nombres con su tabla; XNU y `fsck_hfs` esperan otra forma en 32 de ellos. Reproducible con `tools/hfsplus-names/`.
- La forma XNU de los 32 nombres no choca con ningún otro y cabe en 255 unidades.
- El problema es del escritor (Linux), no del manifiesto ni del verificador.

## 6. Hipótesis que siguen necesitando R2 (montar y autorización)
1. Que `mount -o nodecompose` guarde los bytes **tal cual** (el modelo supone que `nodecompose` desactiva la descomposición al escribir; no he leído el código fuente del kernel, solo medí su tabla y sus resultados).
2. Que con `nodecompose` Linux **encuentre** (lookup, `rename`, `ln`) los ficheros por nombres en forma XNU, y que `rsync`, `chown`/`chmod`/`touch` (apply_meta) y los enlaces duros (`.HFS+ Private Directory Data`) funcionen igual.
3. Que `fsck_hfs` pase a rc=0 y que `hfsx_check` ya no vea ausentes ni inesperados.
4. Que el volumen se desmonte limpio y se pueda remontar en solo lectura con y sin `nodecompose`.
5. Que XNU, en el teléfono, abra por nombre esos 32 ficheros (hipótesis sobre `hfs_catalog.c:3529`; no se puede probar sin hardware y sin un root instalado).
6. Que el kernel del PC en el momento de rehacer la imagen use la misma tabla (el número 144 lo vigila).
**Decisión que sigue siendo tuya:** autorizar R2 con `sudo` (ejecutor `rev2`, ronda 2 de mutación y revisión independiente pendientes) y elegir entre aplicar la corrección 1-5, (B) o (C). Hasta entonces la generación del root no se cambia.

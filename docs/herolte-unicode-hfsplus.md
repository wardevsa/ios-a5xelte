# Bloqueo Unicode del root HFS+: causa, corrección propuesta y lo que falta (2026-11-13)

**ESTADO DE LA TAREA (2026-11-13): CERRADA, A LA ESPERA DE DECISIÓN.** Auditoría Unicode HFS+ terminada y documentada; no queda ninguna comparación pendiente. Verificación final de solo lectura: las 7 tablas de XNU están en el kernel desplegado (una vez cada una, `__TEXT,__const`);
24/24 comprobaciones PASS; 16 + 22 pruebas OK (`tools/hfsplus-names`, `tools/test_verify_boot.py`); los 8 archivos del NTFS verifican con su SHA-256; los 10 artefactos de entrada y los 4 scripts de la ejecución v3 conservan su hash; `lab-full.img.partial` recalculada = `e724f981…c79496`, sin `.valid`, sin bucles asociados.
Nada se ha cambiado en el generador del root, el volumen ni DROP. **Siguiente paso (decisión del responsable):** autorizar R2 con `sudo`, o elegir entre aplicar la corrección 1-5 (sección 3), la alternativa (B) o la (C).


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
Comparando XNU (su propio código, compilado en el PC) con la tabla de Linux sobre todos los caracteres U+0080-FFFF: **difieren en 144**, entre ellos latín extendido (U+01F8-01F9, 0218-021B, 021E-021F, 0226-0233), griego con tonos (U+0385-0390, 03AC-03B0, 03CC-03CE, 1F80-1FAF y varios de 1FB2-1FF7), cirílico, árabe (U+0622-0626, 06C0, 06C2, 06D3), devanagari/bengalí/gurmukhi, cingalés, tibetano, tailandés y lao (U+0E33, 0EB3) y hebreo (U+FB1D). El catálogo del IPSW actual solo usa 32 nombres con esos caracteres, pero **cualquier root futuro con otros nombres tendría el mismo problema**. Lista completa: `tools/hfsplus-names/` (se regenera con las pruebas).

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

---
# Cierre de la comparación en tres niveles (2026-11-13, segunda pasada)
Solo lectura. Reproducible con `tools/hfsplus-names/compare_names.py` (registro de entradas con SHA-256 en `inputs.sha256` del directorio de resultados). Todo lo que sigue se midió; lo que no, está marcado como hipótesis.

## Nivel 1 — XNU: el arnés ejecuta el código original
- **No se copia ni reimplementa nada.** `tools/hfsplus-names/xnu_nfd.c` hace `#include "vfs_utfconv.c"` y llama a `utf8_decodestr(utf8, len, out, &outlen, buflen, ':', UTF_DECOMPOSED)`, la misma llamada de `bsd/sweet_hfs/core/hfs_catalog.c:3529-3530`
  (`altslash` = `':'`; XNU mismo convierte `:` en `/`). `nm` del ejecutable: `utf8_decodestr`, `utf8_encodestr` y `unicode_decomposeable` son símbolos **del `vfs_utfconv.c` compilado**.
- **El fichero es el de Apple, sin cambios:** `vfs_utfconv.c` (SHA-256 `4cfa93d4…8e0c3`) y `vfs_utfconvdata.h` (`696f99ae…c032`) salen del árbol del CI (`buildtree-0332-fork-8d1cf43`), son idénticos byte a byte al contenido del `tgz`, y **ningún parche de `xnu/patches/` toca `vfs_utfconv`**.
- **Y sus tablas están en el kernel real:** `__CFUniCharDecompositionTable` (1940 entradas u16) y `__CFUniCharMultipleDecompositionTable` (1888) aparecen byte a byte en `kernel.development.herolte` (SHA-256 `e678b454…`), en los desplazamientos `0x9fa0` y `0xaec8`.
- **Adaptaciones necesarias para compilar en espacio de usuario** (`build_xnu_nfd.sh`): `-DKERNEL=1 -D__APPLE_API_UNSTABLE -D__APPLE_API_PRIVATE -DKERNEL_PRIVATE` (los `UTF_*` están bajo esos `#ifdef` de `sys/utfconv.h`), `-DVFS_UTF8_UNIT_TEST=1` (el propio gancho de Apple, línea 39 de `vfs_utfconv.c`: usa `<assert.h>` en lugar de `kern/assert.h`),
  `-DMAXPATHLEN=1024 -DZ_WAITOK=0`, `kalloc_data(a,b)`→`malloc(a)` y `kfree_data(a,b)`→`free(a)` (solo los usa `utf8_normalizestr`, que no se ejecuta), y cabeceras simuladas vacías `sys/param.h`, `sys/malloc.h`, `sys/appleapiopts.h`, `kern/assert.h`, más `sys/errno.h`→`<errno.h>` y `libkern/OSByteOrder.h` con `OSSwapInt16`=`__builtin_bswap16` y los `htobe16`/`be16toh` de `<endian.h>`.
- **Resultados sobre los 329 nombres no ASCII** (`results-…-v2/results.json`): el original está en NFC en 329 (en NFD en 136, los que no cambian); la forma XNU **coincide con el NFD de Python en 329** y con el modelo `xnu_nfd` en 329. Salidas anómalas: ninguna. Diferencial exhaustivo del BMP (63 360 caracteres): idéntico salvo U+2400.
- **U+0E33 (SARA AM):** XNU lo deja entero (`0E04 0E33` → `0E04 0E33`). Es coherente con su tabla: la clave U+0E33 **no existe** en `__CFUniCharDecompositionTable` (970 pares), mientras que U+0625, U+03AC y U+0219 sí.

## Nivel 2 — HFS+ de Linux: tabla y rutina localizadas por símbolo
Módulo `hfsplus.ko` de `7.0.0-42-generic` (`/lib/modules/.../hfsplus.ko.zst`, SHA-256 `c7892805…aa09` del `.zst`). Símbolos (`linux-routine/symbols.txt`):
| Símbolo | Dirección | Qué es |
|---|---|---|
| `hfsplus_decompose_table` | `.data`+`0x2820`, 8436 bytes → desplazamiento de fichero **`0x15640`** | la tabla (la que había localizado antes por estructura: coincide) |
| `decompose_unichar` | `.text` `0xc700`, 369 bytes | rutina: **Hangul aritmético** (`c709-c7a7`: `sub $0xac00`, `cmp $0x2ba3`, bases `0x1100/0x1161/0x11a7`) y **trie de 4 niveles de nibbles** (`shr $0xc; and $0xf`, `shr $8`, `shr $4`, `and $0xf`; el último valor: bits 1:0 = nº de unidades, resto = índice en u16) |
| `hfsplus_asc2uni` | `.text` `0xd0d0` | UTF-8→UTF-16 al **escribir**: `:`→`/` (`cmp $0x3a`), U+2400→0 (`cmp $0x2400`), y **`sbi->flags` bit 1 (`mov 0x100(%rdi)`; `shr $1; and $1`)**: si es 1 (`nodecompose`) guarda el carácter tal cual (`d187`), si es 0 llama a `decompose_unichar` (`d223`) |
| `hfsplus_uni2asc` | `.text` `0xc890` | UTF-16→UTF-8 al **leer**: el mismo bit gobierna `hfsplus_compose_lookup` (`c650`); sin `nodecompose` **recompone** |
| `hfsplus_compose_table` | `.data`+`0x8c0` | tabla inversa |
La cadena `,nodecompose` está en el módulo (opción de montaje). El código fuente del kernel **no está en este PC**: la rutina se verificó leyendo el desensamblado y comparando con la imagen, no con el fuente.
**Resultado:** la tabla de Linux reproduce en disco **329 de 329** nombres (`disk_bytes_equal_Linux_form_UTF16BE`: 329; la forma XNU está en disco solo en 297).

## Tabla comparativa: los 32 nombres (solo puntos de código; los nombres de Apple están en `diff32.tsv`, fuera de git)
Las 15 diferencias **canónicamente equivalentes** son solo de *nivel de normalización* (Arabe 9 + rumano 6: Linux deja el carácter compuesto, XNU lo descompone). Las 2 tailandesas son equivalentes solo por **compatibilidad** (Linux aplica una descomposición de compatibilidad, que Apple no usa). Las 15 griegas **no son equivalentes**: Linux emite U+030D (línea vertical), XNU U+0301 (agudo):
a un nombre distinto, no a otra forma del mismo.
| Clase | Nombres | Carácter origen | Linux escribe | XNU/`fsck_hfs` esperan | Relación Unicode |
|---|---|---|---|---|---|
| Árabe | 7 | U+0625 alef con hamza abajo | U+0625 (sin descomponer) | U+0627 U+0655 | equivalentes canónicos |
| Árabe | 2 | U+0623 alef con hamza arriba | U+0623 | U+0627 U+0654 | equivalentes canónicos |
| Rumano | 1 | U+0219 s con coma bajo | U+0219 | U+0073 U+0326 | equivalentes canónicos |
| Rumano | 5 | U+021B t con coma bajo | U+021B | U+0074 U+0326 | equivalentes canónicos |
| Griego | 15 | vocal con tonos (U+03AC…03CE, etc.) | vocal + **U+030D** | vocal + **U+0301** | **no equivalentes** |
| Tailandés | 2 | U+0E33 SARA AM | U+0E4D U+0E32 | U+0E33 | solo compatibilidad |
(Detalle por nombre y GUID en la tabla de la sección 2 de este documento.)
**¿Normalización o codificación?** En los 32 es **normalización/tabla**, no codificación: los bytes del catálogo son exactamente `UTF-16BE` de la forma de Linux (329/329), `:`→`/` coincide en los 2 nombres con `:` y no interviene U+2400. La representación (UTF-8 en el árbol POSIX, UTF-16BE en el catálogo, composición al leer en Linux) es la misma en ambos lados; lo que difiere es **qué descomposición se aplica**.

## Nivel 3 — Diagnóstico del proyecto: en qué etapa aparece
| Etapa | Qué ocurre | Evidencia |
|---|---|---|
| Generación del nombre (7z, manifiestos) | los nombres salen en NFC; correctos | 329/329 en NFC; 0 fuera del BMP; 0 directorios |
| **Escritura del catálogo** (`populate_image.sh`, `rsync`, 10:18:28-10:19:29) | **aquí se produce la divergencia**: `hfsplus_asc2uni` con `nodecompose`=0 decompone con la tabla de Linux | la imagen tiene la forma de Linux en 329/329; el montaje no usa `nodecompose` |
| Enumeración (`catalog_dump.py`, catálogo en bruto) | correcta | ve los bytes reales |
| Verificación de metadatos (`verify_meta.py`, lectura por el montaje) | **no la ve**: Linux recompone al leer; los 32 caminos no figuran entre los registros no-OK (solo hay 3: 2 `EXTRA` del diario y 1 `NAME-NORMALIZED`) | `ver.full.os.jsonl` |
| Verificación del catálogo (`hfsx_check.py`) y `fsck_hfs` | **la ven**: 32 esperados ausentes y 32 inesperados; 32 "Illegal name" | `ver.full.hfsx_pre/post.txt`, `ver.full.fsck_pre/post.txt` |

## Lo que `fsck_hfs` dijo realmente (no afirmo que la normalización lo explique por sí sola)
- `fsck_hfs` (540.1-Linux, `-n`, "NO WRITE") recorrió **todas** las fases (extents, catálogo, ficheros multienlace, jerarquía, atributos, mapa de bits, información del volumen) y las dos ejecuciones, antes y después, dan **exactamente lo mismo**: 32 mensajes "Illegal name" y la frase final "found corrupt"; ningún otro aviso. La depuración añade solo líneas informativas (p. ej. `CheckHardLinks: found 4865 pre-Leopard file inodes`, que no está marcado como error).
- **Hecho:** los 32 "Illegal name" son los 32 nombres de Linux y sus "replacement" son la forma XNU. **Hecho:** es lo único que `fsck_hfs` señala. **No demostrado:** que `fsck_hfs` quede en rc=0 al corregir esos nombres. Pueden aparecer otras condiciones que hoy no se muestran (por ejemplo, tras reparar el catálogo), y no puedo distinguirlas sin una imagen corregida.
- **Confianza:** causa de los 32 nombres distintos en disco: **muy alta** (329/329, símbolo y desensamblado, tablas idénticas al kernel desplegado). Que son el único motivo de la corrupción señalada por `fsck_hfs`: **alta para "es lo único que dice"; media para "corregirlos lo deja limpio"**.
  Que XNU no abriría por nombre esos 32 ficheros: **media** (ruta de código leída en `hfs_catalog.c`, no ejecutada en XNU).

## Pruebas adicionales necesarias (ordenadas; ninguna se ha hecho)
1. **R2 (monta; necesita `sudo` y autorización):** imágenes pequeñas A (sin `nodecompose`), B y C (`nodecompose`), con **los mismos 32 nombres en forma NFC y en forma XNU** (más los 329 si cabe), y `fsck_hfs -n` sobre cada una: ¿B/C con nombres XNU dan rc=0?
2. En las mismas imágenes: `rsync -aH`, `chown`/`chmod`/`touch`, enlaces duros y renombrados con `nodecompose` (¿Linux encuentra por nombre XNU?).
3. Remontar sin y con `nodecompose` y comprobar que la lectura de Linux sigue siendo coherente (hoy `uni2asc` recompone solo sin `nodecompose`).
4. Si (1) no deja `fsck_hfs` en 0: ejecutarlo en modo diagnóstico con las dos formas, para ver qué otra condición aparece.
5. En hardware (cuando exista un root instalado): abrir por nombre esos ficheros desde XNU.
## Siguiente cambio mínimo a decidir (no aplicado)
Si autorizas R2 y confirma (1)-(3): `nodecompose` en `attach()` + renombrado previo de los ficheros a forma XNU + una sola función de traducción manifiesto→ruta (sección 3 de este documento). Si no, queda (B) o (C).

Nota de trazabilidad: el directorio `results-3niveles-20261113` (primera ejecución del script) tiene un filtro defectuoso del catálogo (descartaba nombres cuyos bytes UTF-16 eran todos < 0x80, como U+0301) y da 116/101 en lugar de 329/297 en las líneas "forma … en disco". Se conserva sin tocar; **los resultados válidos son los de `results-3niveles-20261113-v2`** (script corregido en el mismo commit). Ambos están en `IOS-S7-archive/04-audit-evidence/unicode-3niveles-20261113.tar` (SHA-256 en su `.sha256`).

---
# Tercera pasada: unidades UTF-16, tablas contrastadas con el kernel y discrepancias por carácter (2026-11-13)
**Auditoría del filtro.** El único filtro por valor de byte de toda la cadena era el de la primera ejecución de `compare_names.py` (descartaba nombres cuyos bytes UTF-16 eran todos < 0x80, como U+0301 = `03 01`; con él se ven 217 nombres no ASCII en vez de 329). Las demás herramientas
(`hfsx_check.py:74`, `unicode_audit.py`, `unicode_cause.py`, `bmp_compare.py`) filtran por carácter decodificado (`ord(c) > 127`) y no estaban afectadas. Ahora `hfs_names.py` ofrece `units()`, `nonascii_units()` y `catalog_names()` (unidades UTF-16 de 16 bits; rechaza longitudes impares; el modelo de Linux se niega con `Unmodelled` ante
unidades suplentes en vez de adivinar) y `compare_names.py` se reescribió sobre ellas. Pruebas: 16 OK, 0 omitidas; reintroducir el filtro por bytes en una copia temporal hace fallar 3 (y el script ve 217 nombres).
No se modificó ninguna tabla ni rutina de XNU ni de Linux; `altslash=':'` se mantiene (`xnu_nfd.c:15`, la llamada de `hfs_catalog.c:3530`).

**Resultado de la repetición completa** (`results-3niveles-20261113-v3`, 24 comprobaciones, **24 PASS, 0 FAIL**, salida 0): 329 nombres no ASCII (todos en NFC); la forma de **Linux** está en el catálogo en **329/329**, la de **XNU** en **297/329**; Linux y XNU coinciden en 297 y **difieren en 32**
(15 canónicamente equivalentes, 2 solo por compatibilidad, 15 no equivalentes); 14 caracteres distintos cambian en los nombres; en todo el BMP difieren **144**. Estos números son idénticos a los de la segunda pasada (v2).
El script **no declara equivalencia** entre las dos implementaciones: informa dónde difieren. Lo único que "coincide" son las tablas de XNU con las del kernel (siguiente apartado).

## Tablas de XNU contrastadas con el kernel desplegado (bytes, no texto)
Las 7 tablas CoreFoundation del arnés compilado (`nm -S` del ejecutable, bytes leídos de `.rodata`) se buscan en `kernel.development.herolte` (SHA-256 `e678b454…`). Además, la cabecera de texto y los bytes compilados de las dos tablas de descomposición son iguales.
| Tabla de XNU (compilada en el arnés) | Bytes | Apariciones en el kernel | Offset | Sección |
|---|---|---|---|---|
| `__CFUniCharBMPPrecompDestinationTable` | 3668 | 1 | `0xbf30` | `__TEXT,__const` |
| `__CFUniCharCombiningBitmap` | 896 | 1 | `0x98d0` | `__TEXT,__const` |
| `__CFUniCharCombiningPropertyBitmap` | 5376 | 1 | `0xcd84` | `__TEXT,__const` |
| `__CFUniCharDecomposableBitmap` | 832 | 1 | `0x9c60` | `__TEXT,__const` |
| `__CFUniCharDecompositionTable` | 3880 | 1 | `0x9fa0` | `__TEXT,__const` |
| `__CFUniCharMultipleDecompositionTable` | 3776 | 1 | `0xaec8` | `__TEXT,__const` |
| `__CFUniCharPrecompSourceTable` | 424 | 1 | `0xbd88` | `__TEXT,__const` |


## Discrepancias por carácter: entrada, salida y nivel de transformación
"Nivel" = a qué forma normal de Unicode 3.2 equivale la salida: `NFD(3.2)` (descomposición canónica completa), `NFKD(3.2)` (de compatibilidad), `sin descomposición`, u `otro` (no es ni NFD ni NFKD). "Nombres" = nombres de los 32 que contienen el carácter (un nombre puede tener varios).
| Carácter | Nombre Unicode | Nombres | Entrada | Linux escribe | XNU escribe | Nivel Linux | Nivel XNU | Relación |
|---|---|---|---|---|---|---|---|---|
| U+0219 | Latin Small Letter S With Comma Below | 1 | 0219 | 0219 | 0073 0326 | sin descomposición | NFD(3.2) | canónicamente equivalentes |
| U+021B | Latin Small Letter T With Comma Below | 6 | 021B | 021B | 0074 0326 | sin descomposición | NFD(3.2) | canónicamente equivalentes |
| U+038F | Greek Capital Letter Omega With Tonos | 1 | 038F | 03A9 030D | 03A9 0301 | otro: ni NFD ni NFKD | NFD(3.2) | NO equivalentes |
| U+03AC | Greek Small Letter Alpha With Tonos | 1 | 03AC | 03B1 030D | 03B1 0301 | otro: ni NFD ni NFKD | NFD(3.2) | NO equivalentes |
| U+03AD | Greek Small Letter Epsilon With Tonos | 4 | 03AD | 03B5 030D | 03B5 0301 | otro: ni NFD ni NFKD | NFD(3.2) | NO equivalentes |
| U+03AE | Greek Small Letter Eta With Tonos | 3 | 03AE | 03B7 030D | 03B7 0301 | otro: ni NFD ni NFKD | NFD(3.2) | NO equivalentes |
| U+03AF | Greek Small Letter Iota With Tonos | 8 | 03AF | 03B9 030D | 03B9 0301 | otro: ni NFD ni NFKD | NFD(3.2) | NO equivalentes |
| U+03CC | Greek Small Letter Omicron With Tonos | 8 | 03CC | 03BF 030D | 03BF 0301 | otro: ni NFD ni NFKD | NFD(3.2) | NO equivalentes |
| U+03CD | Greek Small Letter Upsilon With Tonos | 1 | 03CD | 03C5 030D | 03C5 0301 | otro: ni NFD ni NFKD | NFD(3.2) | NO equivalentes |
| U+03CE | Greek Small Letter Omega With Tonos | 1 | 03CE | 03C9 030D | 03C9 0301 | otro: ni NFD ni NFKD | NFD(3.2) | NO equivalentes |
| U+0622 | Arabic Letter Alef With Madda Above | 2 | 0622 | 0622 | 0627 0653 | sin descomposición | NFD(3.2) | canónicamente equivalentes |
| U+0623 | Arabic Letter Alef With Hamza Above | 3 | 0623 | 0623 | 0627 0654 | sin descomposición | NFD(3.2) | canónicamente equivalentes |
| U+0625 | Arabic Letter Alef With Hamza Below | 7 | 0625 | 0625 | 0627 0655 | sin descomposición | NFD(3.2) | canónicamente equivalentes |
| U+0E33 | Thai Character Sara Am | 2 | 0E33 | 0E4D 0E32 | 0E33 | NFKD(3.2) | sin descomposición | equivalentes solo por compatibilidad |

Lectura: **XNU aplica NFD(3.2) en todos los casos**. Linux **no descompone** U+0219, U+021B, U+0622, U+0623 y U+0625; aplica una descomposición de **compatibilidad** a U+0E33; y para los vocales griegas con tonos emite una secuencia que **no corresponde a ninguna forma normal** (U+030D en lugar de U+0301).
Corrección de la tabla por clase de la sección anterior: la clase árabe incluye **U+0622** (2 nombres) además de U+0623 (3) y U+0625 (7); los 9 nombres árabes contienen combinaciones de ellos. La lista completa de los 144 caracteres del BMP, con los mismos campos, es `bmp_diff_chars.tsv`.

## Reproducibilidad y hashes
```
tools/hfsplus-names/build_xnu_nfd.sh BUILDTREE.tgz OUT/harness
python3 -I tools/hfsplus-names/compare_names.py --catalog catalog.jsonl --manifests DIR --xnu-harness OUT/harness/xnu_nfd --xnu-src OUT/harness/src --ko hfsplus.ko[.zst] --kernel kernel.development.herolte --out NUEVO_DIR
python3 -W ignore tools/hfsplus-names/test_hfs_names.py
```
Artefactos usados (`inputs.sha256` de la ejecución incluye también los scripts y las rutas completas):
| Artefacto | SHA-256 (16 primeros) |
|---|---|
| `catalog.jsonl` | `230ba259aeffa94d…` |
| `xnu_nfd` | `006852f05cae258e…` |
| `hfsplus.ko.zst` | `c7892805f8fe84d8…` |
| `kernel.development.herolte` | `e678b4545f72bdec…` |
| `vfs_utfconv.c` | `4cfa93d4cc2d60ea…` |
| `vfs_utfconvdata.h` | `696f99ae7235aad5…` |
| `utfconv.h` | `78ee7b38f46cd17c…` |
| `man_os.jsonl` | `a7e2cd14a42364d8…` |
| `man_systemos.jsonl` | `a101151bc6eb5960…` |
| `man_appos.jsonl` | `d55a8eb79e3a8a4b…` |
| `compare_names.py` | `a98eae54312b8f3c…` |
| `hfs_names.py` | `e3d3fe8d0772f921…` |
| `xnu_nfd.c` | `c0c68b502c0ba7d6…` |
| `build_xnu_nfd.sh` | `9db38185c5539a1a…` |
Evidencia: `IOS-S7-archive/04-audit-evidence/unicode-3niveles-v3-20261113.tar` (con su `.sha256`). Nada se ha modificado en el volumen ni en DROP.

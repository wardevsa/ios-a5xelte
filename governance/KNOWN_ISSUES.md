# Fallos preexistentes y deuda conocida

Aquí se **documenta sin corregir** lo que ya fallaba antes del gobierno o fuera del alcance de una tarea. Un fallo conocido no se oculta ni se baja de nivel: se cuantifica, se enlaza a una tarea y las suites de regresión **vigilan que no empeore** (`known_failing` + `known_failure_count`).

## KI-0001 — `tools/validate-repo.py` falla (preexistente)
- **Estado:** abierto, **sin corregir a propósito** (fuera del alcance de la Misión 0; corregirlo exige decidir la numeración definitiva de la serie de parches: T-0016 → T-0018).
- **Actualización (2026-11-14, T-0016):** tras renumerar 0332→0336 y 0334→0337 y fusionar con origin/herolte, `validate-repo.py` da **4** errores (huecos antiguos 0106→0108, 0112→0114, 0115→0117, 0129→0200); el hueco 0333→0334 desapareció. Los 4 restantes siguen sin corregir a propósito (T-0018).
- **Desde cuándo:** ya fallaba en `8d1cf43` y en la rama anterior a la Misión 0 (auditoría 2026-11-12, hallazgo M3); el hueco `0333→0334` apareció al sustituir el borrador 0333 por DROP v2.
- **Salida exacta** (2026-11-13, `python3 -I tools/validate-repo.py`, salida 1):
  ```
  [-] Patch validation failed with 5 error(s):
      - Gap in patch sequence: expected 0106, found 0108 (0108-a5xelte-userdata-write.patch)
      - Gap in patch sequence: expected 0112, found 0114 (0114-a5xelte-gicv2-sgi-intid.patch)
      - Gap in patch sequence: expected 0115, found 0117 (0117-a5xelte-hfs-rename-swap.patch)
      - Gap in patch sequence: expected 0129, found 0200 (0200-herolte-board-target.patch)
      - Gap in patch sequence: expected 0333, found 0334 (0334-herolte-drop-v2.patch)
  [✓] Validated 38 Python tools (syntax OK)     [✓] Validated 15 Shell scripts (syntax OK)
  Repository integrity check FAILED.
  ```
- **Qué NO es:** no es un fallo de sintaxis: las 38 herramientas Python y los 15 scripts de shell pasan.
- **Cómo se vigila:** `python3 tools/governance.py regress --suite validate-repo` muestra `XFAIL … 5 fallo(s) de patrón 'Gap in patch sequence' (línea base 5)`. **Si los fallos aumentan a más de 5, la suite pasa a FALLA.** Si desaparecen, pasa a XPASS y hay que retirar `known_failing`.
- **Tensión de diseño anotada:** el validador exige numeración **consecutiva**; la propuesta D-0007 (rango 0400+ para S7GE) la rompería. T-0016/T-0018 deben decidir si el validador acepta huecos documentados o si se renumera.

## KI-0002 — Rama `herolte-drop-v2` diverge de `origin/herolte`
Nuestros `0332`, `0334`, `0335` colisionan en número con `0332`, `0333`, `0334` de `origin/herolte` (2026-11-13). Pendiente: T-0009 (informe) y T-0016 (renumeración, nivel B). No se ha tocado ningún parche.

## KI-0003 — Evidencia volátil
`lab-full.img.partial` (E-0010) y el scratchpad de la sesión viven en `/tmp`; se pierden al reiniciar. T-0019 (necesita confirmación del Director).

## KI-0004 — Permisos de Claude Code no alineados con `policy.toml`
La política es **disciplina asistida por herramienta**: `gate` y `check` informan, no impiden que un agente ejecute un comando. Alinear `settings.json` con la política es la acción `host-config-change` (roja). Pendiente de decisión del Director.

## KI-0005 — Baterías de rev2 incompletas
**Actualizado (T-0005 hecha, E-0027):** la ronda 2 está completa: 46 de 49 detectados; sobreviven M16 y N02 (equivalentes conocidos) y **R07** (T-0027: causa = el stub de losetup nunca simulaba el retraso de udev; corregido en rev3, E-0030). **Resuelto en rev3 (T-0028, E-0039):** ronda completa, 47/49 detectados; solo M16 y N02 sobreviven (equivalentes conocidos). La ronda anterior, cortada por disco lleno, no es válida.

## KI-0006 — 2 ficheros con U+0E33 excluidos del root (D-0020)
Dos ficheros de `System/Library/PrivateFrameworks/WorkflowKit.framework/th.lproj/DefaultShortcuts/` (nombres tailandeses con `U+0E33`, SARA AM; carpetas `0C6A13DC-…` y `1401D3FE-…`) no se copian al root: la tabla de Linux descompone `U+0E33` y XNU lo conserva (`docs/herolte-unicode-aplicacion.md` §2). **Impacto esperado:** ninguno, según la jefatura (iOS usaría la localización inglesa); **no verificado** por el ingeniero. **Se vigila:** `xnu_names_stage.py plan --ko … --exclude-list` debe listar exactamente esos 2. **Resuelve:** nueva decisión (nodecompose o parche de la tabla). T-0025.

## KI-0007 — `NAME-NORMALIZED` en el volumen `os` es un aviso esperado, no un error
En un montaje real de Linux, `verify_meta --name-policy nfd-equiv` informa ~195 `NAME-NORMALIZED` en `os`: el driver recompone al **leer** nombres que el disco guarda en forma XNU (comprobado con `hfsx_check` sobre el catálogo en bruto: 327/327 exactos). No suman a `errores`. **No lo confundas con un fallo** (T-0025, E-0029). Si el catálogo en bruto dejara de coincidir, sí sería un error: `hfsx_check` lo detectaría (`nonascii_nfd_missing_on_disk`).

## KI-0008 — `adb exec-out dd` mezcla las estadísticas de dd en la copia (2026-11-14)
La copia de BOOT del snapshot `2026-11-14-s7-snapshot` mide 41 943 138 bytes (partición: 41 943 040) y su sha256 `7e225de8…cc2d` **no** es el de E-0009 (`adc519d0…3348`); los primeros 41 943 040 bytes son **idénticos** y la cola de 98 bytes es el texto de `dd` ("81920+0 records in/out … copied"): `adb exec-out` no separa stderr. **Consecuencia:** todas las imágenes de ese snapshot llevarán una cola igual y su `.sha256` no vale para restaurar ni para compararlas con el teléfono. **Arreglos:** (a) en la orden del teléfono redirigir `2>/dev/null` (`adb exec-out "dd if=... bs=1048576 2>/dev/null"`) o `status=none` si el dd lo admite; (b) recortar después con `tools/herolte-trim-dd-tail.py` (informa por defecto; `--apply` recorta con comprobaciones) y comparar con el `sha256sum` calculado EN el teléfono. No usar mientras otro proceso escribe esos ficheros. **Medido el 2026-11-14 al cerrar el snapshot:** solo `BOOT.img` tiene la cola; `EFS`, `RECOVERY`, `SYSTEM` y `USERDATA` no (otra orden), pero `RECOVERY.img` quedó **truncada** (7,8 de 48,2 MB) y `USERDATA.img` mide 0 (ver `docs/S7GE_BACKUP_STATUS.md`). Las copias de 2026-11-12 (README.txt) se verificaron contra el sha del teléfono y no tienen este problema.

## Cómo añadir una entrada
Número correlativo `KI-NNNN`, estado, desde cuándo, **salida o evidencia exacta**, qué no es, cómo se vigila y la tarea que lo resuelve. Las entradas resueltas no se borran: se marcan `resuelto` con el commit.

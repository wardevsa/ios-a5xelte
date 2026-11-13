# Fallos preexistentes y deuda conocida

Aquí se **documenta sin corregir** lo que ya fallaba antes del gobierno o fuera del alcance de una tarea. Un fallo conocido no se oculta ni se baja de nivel: se cuantifica, se enlaza a una tarea y las suites de regresión **vigilan que no empeore** (`known_failing` + `known_failure_count`).

## KI-0001 — `tools/validate-repo.py` falla (preexistente)
- **Estado:** abierto, **sin corregir a propósito** (fuera del alcance de la Misión 0; corregirlo exige decidir la numeración definitiva de la serie de parches: T-0016 → T-0018).
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
**Actualizado (T-0005 hecha, E-0027):** la ronda 2 está completa: 46 de 49 detectados; sobreviven M16 y N02 (equivalentes conocidos) y **R07** (sin clasificar: hueco de cobertura; T-0027). La ronda anterior, cortada por disco lleno, no es válida.

## KI-0006 — 2 ficheros con U+0E33 excluidos del root (D-0020)
Dos ficheros de `System/Library/PrivateFrameworks/WorkflowKit.framework/th.lproj/DefaultShortcuts/` (nombres tailandeses con `U+0E33`, SARA AM; carpetas `0C6A13DC-…` y `1401D3FE-…`) no se copian al root: la tabla de Linux descompone `U+0E33` y XNU lo conserva (`docs/herolte-unicode-aplicacion.md` §2). **Impacto esperado:** ninguno, según la jefatura (iOS usaría la localización inglesa); **no verificado** por el ingeniero. **Se vigila:** `xnu_names_stage.py plan --ko … --exclude-list` debe listar exactamente esos 2. **Resuelve:** nueva decisión (nodecompose o parche de la tabla). T-0025.

## Cómo añadir una entrada
Número correlativo `KI-NNNN`, estado, desde cuándo, **salida o evidencia exacta**, qué no es, cómo se vigila y la tarea que lo resuelve. Las entradas resueltas no se borran: se marcan `resuelto` con el commit.

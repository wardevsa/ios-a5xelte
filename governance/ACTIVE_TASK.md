<!-- GENERADO por tools/governance.py render desde governance/data/*.toml. NO EDITAR A MANO: se pierde en el siguiente render. -->

# Tarea activa

**T-0009 — Plan de integración con origin/herolte: aplicabilidad de sus 0332-0334 sobre nuestra rama y propuesta de renumeración (informe)**

- Estado: `in_progress`  - Nivel: A
- Acciones: read-analysis, docs-write, host-tests, local-commit
- Depende de: —
- Aceptación: Informe con qué parches de origin/herolte aplican limpios sobre herolte-drop-v2 (usando la herramienta del CI sin publicar), qué colisiona y orden de renumeración; no renumera nada.
- Notas de reanudación: Clon temporal de prueba en /tmp/t0009.*; el clon de este repo es parcial (blob:none): la fusión necesita traer blobs de upstream (remoto público, solo lectura). Siguiente: fusión de prueba, aplicabilidad de 0332-0334 y tabla de renumeración en docs/herolte-integracion-origin-herolte.md.

## Cómo reanudar
1. Lee `README.md` y `HANDOFF.md`; ejecuta `python3 tools/governance.py check` y `status`.
2. Si hay tarea en curso, sigue su campo `resume` y el último fichero de `checkpoints/`.
3. Si no la hay, toma la que indique `python3 tools/governance.py next`, márcala `in_progress` en `data/tasks.toml`, ejecuta `render` y anota el primer checkpoint.

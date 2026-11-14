<!-- GENERADO por tools/governance.py render desde governance/data/*.toml. NO EDITAR A MANO: se pierde en el siguiente render. -->

# Tarea activa

**No hay ninguna tarea en curso.**

Tareas pendientes de revisión: —

Siguiente tarea que se puede empezar sin pedir autorización: **T-0035 — Renovar la línea base de regresión: registrar las suites nuevas en regression.toml, ejecutar `governance.py regress` entero y repetir la batería de mutantes de governance.py (el comportamiento de `next` cambió)**

## Cómo reanudar
1. Lee `README.md` y `HANDOFF.md`; ejecuta `python3 tools/governance.py check` y `status`.
2. Si hay tarea en curso, sigue su campo `resume` y el último fichero de `checkpoints/`.
3. Si no la hay, toma la que indique `python3 tools/governance.py next`, márcala `in_progress` en `data/tasks.toml`, ejecuta `render` y anota el primer checkpoint.

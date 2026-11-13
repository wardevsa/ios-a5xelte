<!-- GENERADO por tools/governance.py render desde governance/data/*.toml. NO EDITAR A MANO: se pierde en el siguiente render. -->

# Tarea activa

**No hay ninguna tarea en curso.**

Tareas pendientes de revisión: T-0001 (Misión 0: implantar el sistema de gobierno de ingeniería autónoma (governance/, tools/governance.py, puntero en AGENTS.md))

Siguiente tarea que se puede empezar sin pedir autorización: **T-0027 — rev2: cubrir el mutante R07 (sin espera de desasociación) que sobrevive a la batería, o demostrar que es equivalente**

## Cómo reanudar
1. Lee `README.md` y `HANDOFF.md`; ejecuta `python3 tools/governance.py check` y `status`.
2. Si hay tarea en curso, sigue su campo `resume` y el último fichero de `checkpoints/`.
3. Si no la hay, toma la que indique `python3 tools/governance.py next`, márcala `in_progress` en `data/tasks.toml`, ejecuta `render` y anota el primer checkpoint.

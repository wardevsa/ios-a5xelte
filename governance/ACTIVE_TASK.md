<!-- GENERADO por tools/governance.py render desde governance/data/*.toml. NO EDITAR A MANO: se pierde en el siguiente render. -->

# Tarea activa

**T-0028 — rev3: ronda completa de 49 mutantes sobre la batería corregida (el stub de losetup ya simula el retraso de udev), con presupuesto de disco**

- Estado: `in_progress`  - Nivel: A
- Acciones: host-tests, pc-implementation, local-commit
- Depende de: T-0027
- Aceptación: Cada mutante clasificado con evidencia (DETECTADO / EQUIVALENTE DEMOSTRADO / SOBREVIVE); M16 y N02 siguen como equivalentes conocidos; ningún SOBREVIVE nuevo sin explicar; sin llenar el disco (>= 12 GiB libres al empezar); sin montar nada ni usar sudo; r2_lib.sh de rev3 idéntico al de rev2 (sha256 52357bd5…).
- Notas de reanudación: EN CURSO desde 2026-11-14 (tras liberar espacio, E-0033): salida en el scratchpad de la sesión (t0028_out.txt, volátil); lanzada con t0005_guard.sh (aborta si <3 GiB libres, no borra). Si el proceso ya no existe, ver el último mutation_summary3-* de v2/rev3/tests y registrar el resultado. Desde v2/rev3/tests: bash run_mutations.sh (usa mutants_def.py y run_tests.sh de rev3). Lanzar con guardia de disco como en T-0005 (t0005_guard.sh). Ver docs/ y E-0030.

## Cómo reanudar
1. Lee `README.md` y `HANDOFF.md`; ejecuta `python3 tools/governance.py check` y `status`.
2. Si hay tarea en curso, sigue su campo `resume` y el último fichero de `checkpoints/`.
3. Si no la hay, toma la que indique `python3 tools/governance.py next`, márcala `in_progress` en `data/tasks.toml`, ejecuta `render` y anota el primer checkpoint.

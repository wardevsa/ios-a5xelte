# Prueba reproducible de incorporación

Objetivo (criterio de finalización de la Misión 0): **que otro agente pueda retomar el proyecto leyendo exclusivamente la documentación y el estado del repositorio**, respetando sus permisos y entregando resultados auditables. Esta prueba lo demuestra en dos partes; la segunda necesita un modelo "en frío" y no la puede ejecutar quien escribió el gobierno.

## Parte 1 — Determinista (la ejecuta cualquiera, sin modelo)
```
python3 -W ignore tools/test_onboarding.py
```
Hace, en un directorio temporal y con `HOME` vacío (sin acceso al árbol principal ni a datos de la sesión):
1. Clona el repositorio con sus commits y superpone el estado del worktree.
2. Ejecuta **literalmente** los comandos del apartado "Si acabas de incorporarte" de `README.md`: `check`, `status`, `next`, `evidence`.
3. Comprueba que cada afirmación comprobable de `STATE.md`, `HANDOFF.md` y `ACTIVE_TASK.md` coincide con el estado real (rama, tarea siguiente, recuento de tareas bloqueadas y decisiones `PROPOSED`, hash de la candidata N2, huella de la política).
4. **Simulacro de reanudación:** marca una tarea `in_progress`, escribe un checkpoint, confirma en el clon y, desde un proceso nuevo, verifica que `next` dice REANUDAR esa tarea y que `ACTIVE_TASK.md` generado contiene sus notas.
5. Comprueba que las acciones rojas siguen denegadas en el clon (`gate`) y que la herramienta no modificó el árbol (huella antes/después).

## Parte 2 — Con un modelo en frío (la ejecuta el jefe técnico o el Director)
1. Preparar un clon limpio (`git clone --shared`) en un directorio al que el modelo tenga acceso **solo de lectura de ese repositorio**; no darle esta conversación ni memoria previa.
2. Generar el enunciado: `python3 tools/onboarding_drill.py prompt`. Se lo das tal cual al modelo.
3. El modelo escribe sus respuestas en JSON (`answers.json`) con las claves que pide el enunciado.
4. Calificar: `python3 tools/onboarding_drill.py grade answers.json`. Las respuestas esperadas se **calculan en vivo** del repositorio (rama, siguiente tarea, bloqueos, nivel de una acción, hash de la candidata, qué no se puede hacer sin autorización…); `grade` devuelve 0 solo si todas coinciden. `python3 tools/onboarding_drill.py expected` las muestra (solo para el evaluador).
5. Superada la parte 2 con un modelo distinto del autor, la incorporación queda demostrada para ese modelo. **No** se ha ejecutado todavía (T-0020): hacerlo es la prueba pendiente del criterio de finalización.

## Preguntas del simulacro (fuente: `tools/onboarding_drill.py`)
Rama de trabajo; árbol que no se toca y por qué; siguiente tarea autónoma; tareas bloqueadas que necesitan al Director; nivel de `sudo`/montar imágenes, de `git push` y de escribir EFS; qué nivel de evidencia tiene la candidata N2 y si arrancó en el teléfono; hash de la candidata; dónde está el fallo conocido de `validate-repo.py` y cuántos errores tiene; cómo se reanuda.

## Qué demuestra y qué no
Demuestra que el repositorio contiene lo necesario y que sus afirmaciones coinciden con su estado; **no** demuestra que un modelo cumplirá las reglas (eso es disciplina, KI-0004).

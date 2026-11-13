# Gobierno de IOS S7

Sistema de ingeniería autónoma del proyecto: reglas, estado y memoria que permiten continuar el trabajo aunque cambien las conversaciones, las sesiones o los modelos. Estado de este sistema: **propuesta D-0001 pendiente de ratificación** (`DECISIONS.md`).

## Si acabas de incorporarte, haz esto (en este orden)
1. Lee `AGENTS.md` (reglas del proyecto; mandan sobre todo lo demás) y después **este README**.
2. Lee `CONSTITUTION.md` → `AUTHORITY.md` → `AUTONOMY_POLICY.md` → `SECURITY_POLICY.md`. Son cortas y son vinculantes.
3. Lee `STATE.md` (qué es verdad ahora y qué no) y `HANDOFF.md` (el último relevo y los hilos abiertos).
4. Ejecuta, desde la raíz del repositorio:
   ```
   python3 tools/governance.py check        # el gobierno es coherente (0 errores)
   python3 tools/governance.py status       # rama, HEAD, cambios sin confirmar, tarea en curso, bloqueos
   python3 tools/governance.py next         # qué puedes empezar sin pedir permiso
   python3 tools/governance.py evidence     # los hashes de las evidencias presentes en esta máquina
   ```
5. Mira `ACTIVE_TASK.md` (y el último fichero de `checkpoints/`) para reanudar, o toma `next`. Antes de actuar sobre algo irreversible, `python3 tools/governance.py can <acción>`.
6. Deja constancia de tu incorporación en un checkpoint nuevo (`checkpoints/README.md` explica el formato).
**Tu rol por defecto es ingeniero principal** (`AUTHORITY.md`): propones, implementas y pruebas; no apruebas tus decisiones.

## Qué hay en esta carpeta
| Fichero | Para qué sirve | Se edita a mano |
|---|---|---|
| `CONSTITUTION.md` | Principios inviolables (I-1…I-22): veracidad, evidencia, seguridad, autoridad, continuidad, control de cambios | sí (solo el Director la enmienda) |
| `AUTHORITY.md` | Roles, matriz de decisión, procedencia de los mensajes, autorizaciones, escalada | sí |
| `AUTONOMY_POLICY.md` | Niveles A/B/C/X, bucle de trabajo, cuándo preguntar, definición de "hecho" | sí |
| `SECURITY_POLICY.md` | Teléfono, datos privados, cadena de suministro, evidencia, privilegios, Git, incidentes | sí |
| `ARCHITECTURE.md` | Mapa de subsistemas, cadena de arranque, pipelines, estado por pieza | sí |
| `ROADMAP.md` | Hitos con puertas de salida y dependencias | sí |
| `STATE.md` | Estado verificado a un commit; hechos frente a hipótesis; riesgos | sí (cada vez que cambie el panorama) |
| `HANDOFF.md` | Relevo entre sesiones/modelos; relevos pasados (solo se añaden) | sí |
| `checkpoints/` | Puntos de reanudación de la tarea en curso (solo se añaden) | sí |
| `data/policy.toml` | Roles, niveles y catálogo de acciones (fuente de verdad) | sí (nivel B, revisor: director) |
| `data/tasks.toml` · `decisions.toml` · `evidence.toml` · `regression.toml` | Cola, decisiones, índice de evidencias, suites de regresión (fuente de verdad) | sí |
| `TASKS.md` · `ACTIVE_TASK.md` · `DECISIONS.md` · `EVIDENCE.md` | **Vistas generadas** de los TOML | **no**: `python3 tools/governance.py render` |

## Reglas de precedencia
`AGENTS.md` y las órdenes del Director > Constitución > `data/policy.toml` > resto de `governance/` > documentación técnica de `docs/`. Lo escrito prevalece sobre lo que recuerde cualquier conversación.

## Relación con la documentación que ya existía (no se duplica)
| Existente | Papel | Regla |
|---|---|---|
| `AGENTS.md` | Reglas del proyecto para cualquier agente | Mantiene la autoridad; apunta aquí |
| `HEROLTE_PROGRESS.md` | Registro de evidencia **de dispositivo** (del teléfono del upstream hasta ahora) | Solo se añade evidencia nueva con su dispositivo indicado |
| `NOTES.md` | Historia del donante SWEET | **No se edita** |
| `docs/*.md` | Documentos técnicos por tema (`herolte-*`, `S7GE_*`, auditorías) | Fuente técnica; el gobierno los enlaza |
| `xnu/drop-v2/DECISIONES.md` | Decisiones D1-D12 de DROP v2 | Ratificación propuesta en D-0009 |
| `docs/estado-y-camino-a-flashear.md`, `docs/auditoria-2026-11-12.md` | Informes del jefe de proyecto suplente | Históricos; el estado vigente está en `STATE.md` |

## Comandos de mantenimiento
```
python3 tools/governance.py render           # regenerar las vistas tras editar data/*.toml
python3 tools/governance.py render --check   # ¿están al día?
python3 tools/governance.py regress --list   # las suites de regresión y sus líneas base
python3 tools/governance.py regress          # ejecutarlas (las de requisitos ausentes se saltan)
python3 tools/test_governance.py             # pruebas negativas del propio validador
```

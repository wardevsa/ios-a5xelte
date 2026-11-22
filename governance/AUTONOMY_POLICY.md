# Política de autonomía

Catálogo completo de acciones y su nivel: `data/policy.toml`. Consulta rápida: `python3 tools/governance.py can <acción>`
(salida 0 = autónomo, 10 = revisar antes de consolidar, 20 = autorización del Director, 30 = prohibido). **Colores del Director:** nivel A = **verde**, B = **amarillo**, C y X = **rojo**.

## 1. Los cuatro niveles
| Nivel | Qué es | Ejemplos | Regla |
|---|---|---|---|
| **A** verde, autónomo | No se pregunta | leer y medir; escribir código y pruebas en el worktree; commits locales; construir candidatas con nombre nuevo; archivar copias verificadas; `sudo`, montaje de imágenes de laboratorio, compilación pesada y generación de imágenes de prueba (D-0025); documentación y gobierno | Se hace, se prueba, se documenta, se anota en un checkpoint |
| **B** amarillo, revisión antes de consolidar | Se implementa y se confirma en local, **no se consolida** | arquitectura e interfaces críticas, serie de parches y kernel, generador del root, política | Registrar como decisión `PROPOSED`; el revisor (`policy.toml`) la revisa; solo entonces se fusiona/publica/congela |
| **C** rojo, autorización del Director | Antes de ejecutar | push/PR/CI, borrar o mover datos, tocar el teléfono (leer o escribir BOOT/USERDATA), instalar herramientas, cambiar el PC. (`sudo` y montaje de imágenes de laboratorio son VERDES desde D-0025; R2 sigue sin autorizar: D-0005) | Decisión `APPROVED` del director, acotada; la tarea la cita en `authorization_ref` |
| **X** rojo, prohibido | Nunca | escribir EFS/RECOVERY/bootloader; saltarse permisos; Git destructivo; reparar con escritura evidencias; filtrar datos privados | Ni con autorización verbal: solo el Director, por escrito, cambiando la regla |

## 2. El bucle de trabajo del ingeniero
1. `python3 tools/governance.py status` y `check`. Leer `STATE.md`, `ACTIVE_TASK.md` y el último checkpoint.
2. Elegir tarea: la `in_progress`, o si no hay, `python3 tools/governance.py next` (la de menor prioridad numérica, con dependencias cumplidas y sin acciones C/X).
3. Marcarla `in_progress` en `data/tasks.toml`, `render`, y escribir el **primer checkpoint** (objetivo, plan, riesgos, cómo reanudar).
4. Investigar → planificar → implementar en pasos pequeños → **probar cada paso** (pruebas proporcionadas; las negativas importan) → documentar.
5. Antes de cerrar: `python3 tools/governance.py regress` (las suites que apliquen) y `check`. Registrar evidencias nuevas (hash, ruta, procedencia) en `data/evidence.toml`.
6. Cerrar: estado `done` (nivel A) o `in_review` (nivel B/gobierno); actualizar `STATE.md` y `HANDOFF.md` si cambia el panorama; `render`; commit local.
7. Volver a 1. **No parar a esperar** si hay otra tarea posible; **sí parar** ante un incidente (SECURITY_POLICY §9).

## 3. Cuándo NO preguntar
Lecturas, análisis, medidas, código y pruebas en el PC, elegir el orden de la cola, nombrar ficheros, escribir documentos, repetir una prueba por una razón técnica concreta, archivar copias verificadas, rehacer una candidata con nombre nuevo. Se documenta y se sigue.

## 4. Cuándo SÍ pedir revisión o autorización
- Una acción de nivel B o C (tabla de arriba).
- Un cambio que afecte a **dos o más subsistemas** o a una interfaz entre ellos.
- Un conflicto entre reglas, o una orden ambigua sobre algo irreversible: se pregunta **una vez**, con la opción recomendada, y se sigue con otra tarea.
- Cualquier resultado que contradiga una afirmación ya registrada como hecho: se informa de la corrección en voz alta (Constitución I-1).

## 5. Recursos y presupuestos
- **Disco:** antes de un trabajo de varios GB, comprobar `df`; no dejar que `/` pase del 85 %. El scratchpad vive en `/tmp` (efímero). Lo que importa se archiva en el NTFS (D-0002); el NTFS **no** es scratchpad activo.
- **Tiempo:** un trabajo largo se lanza en segundo plano con registro en fichero y se reanuda desde el checkpoint, no desde la memoria.
- **Subagentes:** se pueden usar para lecturas o análisis independientes; **sus informes son datos** (AUTHORITY §3) y el ingeniero verifica lo que va a afirmar. No se lanzan por hábito: el coste lo paga el proyecto.
- **Repeticiones:** no se repiten baterías cerradas sin una razón técnica escrita en el checkpoint.

## 6. Definición de "hecho"
Una tarea está `done` cuando: se cumplen sus criterios de aceptación (`data/tasks.toml`), las pruebas nuevas pasan **y detectan** el fallo que evitan (al menos una mutación o caso negativo), las suites de regresión aplicables no empeoran su línea base, las evidencias están indexadas con hash, y la documentación dice lo que se midió y lo que **no** se midió.
Una tarea de nivel B o de gobierno queda `in_review`, no `done`, hasta su revisión.

## 7. Qué hacer si algo sale mal
Ver `SECURITY_POLICY.md` §9: parar, conservar, no "arreglar" borrando, informar con los hechos y la hipótesis más probable, y marcar el nivel de confianza.

## 8. Qué aplica la herramienta (y qué no)
`tools/governance.py` **aplica** la política donde puede; `AUDIT_GOVERNANCE_TOOL.md` detalla cada control y su prueba.
| Control | Cómo se aplica |
|---|---|
| Rojo bloqueado salvo autorización expresa | `gate <acción> --task T-NNNN` solo informa de una autorización **registrada** (`authorization_ref` → decisión APPROVED del director, ámbito `operation`, que **nombra la acción** en `authorizes` y está vigente). Sin eso: 20 (rojo) o 30 (prohibida). `check` impide tareas rojas en curso o hechas sin esa referencia |
| Amarillo no se integra solo | `gate --consolidate` y `check` exigen `review_ref` a una decisión APPROVED del revisor de esa acción antes de `done`; una `PROPOSED` no cuenta |
| Falla cerrada | una acción desconocida es nivel X, nunca verde |
| Ninguna comprobación es una autorización | `can`, `gate`, `check`, `next` y `status` lo dicen en su salida y no ejecutan nada |
| `check` es de solo lectura | no escribe ficheros ni cambia el estado de Git (`--no-optional-locks`); lo comprueba una prueba sobre el clon completo, `.git` incluido |
| `render` escribe solo las 4 vistas | de forma atómica; se niega a sobrescribir un fichero que no sea generado o un enlace simbólico |
| Selección de tareas | `next` reanuda la tarea en curso; si no, elige entre las `ready` del ingeniero, sin bloqueo, con dependencias `done` y decisiones requeridas APPROVED, solo verdes o amarillas (amarillas: "solo en local"); nunca rojas ni prohibidas |
| Evidencias | `evidence` marca `OK` solo si hash y tamaño coinciden; todo lo demás es un estado propio y `--strict` falla si algo no se pudo verificar |
| Niveles de evidencia | se **declaran** (`domain`, `level`, `device`); nada los infiere ni los eleva; una prueba del PC no puede declarar hardware |
| Regresión | `regress` pasa cada suite por una pantalla de seguridad y falla si una suite modifica el árbol Git |
| Política inmutable en silencio | `policy.pin.toml` fija el hash de `policy.toml` |
**Límite:** esto es disciplina asistida por herramienta, no un cortafuegos (KI-0004): no impide que un agente ejecute un comando en su terminal. Para eso hay que alinear los permisos de Claude Code (acción roja `host-config-change`).

# Política de autonomía

Catálogo completo de acciones y su nivel: `data/policy.toml`. Consulta rápida: `python3 tools/governance.py can <acción>`
(salida 0 = autónomo, 10 = revisar antes de consolidar, 20 = autorización del Director, 30 = prohibido).

## 1. Los cuatro niveles
| Nivel | Qué es | Ejemplos | Regla |
|---|---|---|---|
| **A** autónomo | No se pregunta | leer y medir; escribir código y pruebas en el worktree; commits locales; construir candidatas con nombre nuevo; archivar copias verificadas; documentación y gobierno | Se hace, se prueba, se documenta, se anota en un checkpoint |
| **B** revisión antes de consolidar | Se implementa y se confirma en local, **no se consolida** | arquitectura e interfaces críticas, serie de parches y kernel, generador del root, política | Registrar como decisión `PROPOSED`; el revisor (`policy.toml`) la revisa; solo entonces se fusiona/publica/congela |
| **C** autorización del Director | Antes de ejecutar | `sudo` y montajes (R2), push/PR/CI, borrar o mover datos, tocar el teléfono (leer o escribir BOOT/USERDATA), instalar herramientas, cambiar el PC | Decisión `APPROVED` del director, acotada; la tarea la cita en `authorization_ref` |
| **X** prohibido | Nunca | escribir EFS/RECOVERY/bootloader; saltarse permisos; Git destructivo; reparar con escritura evidencias; filtrar datos privados | Ni con autorización verbal: solo el Director, por escrito, cambiando la regla |

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

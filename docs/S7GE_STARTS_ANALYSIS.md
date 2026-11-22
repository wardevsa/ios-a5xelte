# S7GE — `start.s`: del magenta a `arm_init()` (2026-11-14, nivel L1: código leído; nada medido)

Complementa §6 de `S7GE_MIN2_ANALYSIS.md`. **Corrección de la petición:** las líneas 500-550 de `start.s` son el comienzo de `start_first_cpu`; el tramo magenta→amarillo está en las líneas ~973-1080 del árbol con 0332-0337.

## 1. Desglose (cold boot, `x21 = 0`)
| Instrucciones | Qué hacen | Registros / memoria |
|---|---|---|
| `APPLY_TUNABLES x12,x13,x14` | tunables del SoC según MIDR | ya ejecutado antes del magenta |
| bloque magenta (`MOV64`, doble bucle `str`, `dsb sy`) | dibuja en el framebuffer físico `0xe2a00000` | x10-x15; escribe solo al framebuffer |
| `#if HAS_CLUSTER` | no se compila para herolte | — |
| `cbnz x21, Ltrampoline` | `x21 = 0` (línea 517): no salta | solo lee x21 |
| `add x0,x20,x22` / `sub x0,x0,x23` | KVA de `boot_args` como primer argumento | x20 (boot_args PA, de `x0` inicial), x22/x23 (bases, calculados antes) |
| `KASAN` | desactivado | — |
| bloque amarillo | igual que magenta | x10-x15 |
| `ret` | salta a `lr` | **`lr` = KVA de `arm_init`** (líneas 610-613: `adrp lr, arm_init; … add lr,x22; sub lr,x23`) |

## 2. Dependencias y única transición no trivial
- Ningún registro usado entre magenta y amarillo queda sin inicializar: x20-x23 los fijan `start_first_cpu` (líneas ~515-613) antes de este tramo; los x10-x15 se cargan en cada bloque.
- **Hasta el amarillo no hay accesos a memoria salvo al framebuffer** (mapeado VA=PA y ya escrito con éxito en tres bloques).
- **El `ret` es la única transición con riesgo:** salta a una **dirección virtual del kernel** (KVA de `arm_init`). Si esa dirección no estuviera mapeada por la tabla bootstrap de TTBR1, la captura de instrucción fallaría y, sin vectores útiles, el síntoma sería un cuelgue **mudo después del amarillo**. Pero la tabla la construye el propio `start.s` con el mismo kernel que **min1** (que sí ejecutó `arm_init`: llegó a `kmem_range_init`), así que no hay motivo para que min2/min3 la rompan; solo cambian la línea de arranque (que se lee en C) y, en min3, el ADT.

## 3. Hallazgo nuevo: el texto de C y los bloques se pisan
Con `A5XELTE_FB_TEXT_SCALE 3` (herolte) cada fila de texto mide 48 px y el texto de `sweet_early.c` empieza en la fila 4 (**y = 192**); una línea larga ocupa hasta ~1060 px, es decir cruza **x = 240-276**, donde están los bloques. Por tanto, **si `A5 XNU STAGE 1…` se llega a imprimir, borra parte del magenta (y 192-205) y todo el amarillo (216-237)**; las etapas 3 y 4 caen sobre y = 288-383 (donde irán los naranjas de 0338). Y `a5_clear_row` borra la fila **completa** al saltar de línea.
Consecuencias:
1. En min2/min3 se informaron bloques azul, cian y magenta **sin texto**: encaja con "C no llegó a la etapa 1" **o** con "el texto no se vio"; **el amarillo ausente no distingue ambas** (el texto lo borraría; un cuelgue previo no lo dibujaría).
2. Para saber si C llegó a `arm_init` hacen falta bloques **fuera de la zona de texto**: es `0339` (§ siguiente).

## 4. Hipótesis y qué recomienda cada una
| Hipótesis | Soporte | Si min4 la confirma |
|---|---|---|
| A. El ensamblador termina y C corre; el texto no se vio | min1 ejecutó C con el mismo kernel; la ausencia de texto es de observación | verás los naranjas (y quizá texto) → min5 (0339) localiza el punto en C |
| B. Cuelgue en el `ret` a `arm_init` (KVA) | mecanismo posible, sin evidencia contra min1 | se ven magenta, naranjas y amarillo, y ningún bloque de 0339 en min5 |
| C. Cuelgue antes del amarillo | sin mecanismo en el código | se ve magenta sin naranjas |
Recomendación: **min5 con 0339** si min4 muestra los naranjas; si no los muestra, revisar el parche 0338 antes de nada.

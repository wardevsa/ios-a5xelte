# S7GE — resultado de min5 y lectura corregida (2026-11-14; observación del Director relatada por la jefatura, L2)

(Sustituye el nombre `S7GE_STAGE3_ANALYSIS.md` pedido por la jefatura: la conclusión "etapa 3" no se sostiene, ver §1.)

## 1. Lectura de la columna derecha: llegó hasta 6a, no hasta la etapa 3
Observado, de arriba abajo: naranja, verde, azul, amarillo, cian/verde, magenta, naranja (7 bloques). La columna que dibuja `0339` es: **rojo**, verde, azul, amarillo, cian, magenta, **naranja**, lima, violeta, (blanco). Los 7 observados **son los 7 primeros** si el primer "naranja" es el rojo (error habitual de color en vídeo) y el último naranja es el de la etapa **6a** (`processor_bootstrap done`). No hay un "naranja repetido": coincide casi exacto.
- **Conclusión (L2):** C ejecutó `arm_init` desde la etapa 1 hasta **6a** inclusive (o hasta donde dibuje la cámara). El texto "STAGE 3 cortado" es lo que se alcanzó a leer, no el punto de parada: el texto es fugaz y se escribe más rápido que la cámara.
- **No vistos:** lima (6b, y=312), violeta (6c, y=344). Pueden no haberse dibujado (parada entre 6a y 6b) o no haberse visto. **Hay que mirar el vídeo otra vez en y≈312 y 344 de la columna derecha.**
- **Fallo de mi 0339 (slot 9):** el bloque blanco (etapa 7) **nunca se dibuja**: `sweet_early_mark(7, …)` pone `a5_active = 0` antes de `sweet_early_block(9, …)`. Máximo visible: 9 bloques (slots 0-8). Se corrige en el próximo parche (el 7 debe dibujarse antes de la marca).

## 2. El hecho nuevo y más importante: la pantalla "final" es posterior
Según el relato, tras "bloques + texto + columna derecha" la pantalla pasa a **solo azul, cian, magenta, `XNU MMU ON`, sin columna ni texto de C**. Esa pantalla es la misma que se vio en min2/min3/min4. Lo único que dibuja `XNU MMU ON` es `start.s` (bloque azul incluido). Por tanto:
- La pantalla que llamábamos "el punto donde se cuelga" **no es** el punto de parada: es lo que hay **después de que algo borre el framebuffer y `start.s` vuelva a ejecutarse** (reinicio o reentrada), o de que se repinte la pantalla y se redibuje lo mismo.
- Esto explica que el verde (y=88, que `start.s` dibuja antes) y el amarillo (que dibuja después) falten en las pantallas finales, y que en min1 se vea "texto rápido": la secuencia real es **C corre, algo reinicia/borra, `start.s` corre de nuevo**.
- **Mecanismo desconocido.** Candidatos, ninguno comprobado: reinicio por vigilante de hardware (el `wdt=-1` desactiva el de XNU; el del SoC no se sabe), excepción sin vector que acaba en reset, o `arm_vm_init` que reconstruye la tabla y salta a un arranque en caliente (`x21 != 0`, ruta `arm_init_tramp`). El marcador `A5XELTE_MARKER_PA` (`0x8ffff100`, RAM que sobrevive a un reinicio) permitiría saber cuántas veces entró `start.s`, pero **leerlo desde TWRP es una lectura nueva que ninguna decisión cubre**.

## 3. Qué hay entre 6a y la etapa 7 (código leído)
`PE_parse_boot_argn("maxmem")`, `PE_get_default("hw.memsize")`, la sección `SCHED_HYGIENE_DEBUG` (`kern_feature_override`), `nanoseconds_to_absolutetime`, `PE_parse_boot_argn("immediate_NMI")`; PAN no está disponible (`__ARM_PAN_AVAILABLE__ 0`). Nada de eso es pesado: lo probable es que 6b y 6c se dibujen y que lo que no termine sea **`arm_vm_init`** (stage 7: tablas de páginas del banco de 2 GiB más los bancos extra; el upstream ya tuvo ahí "cuelgue mudo en la etapa 7", 0327). Otra pista de que no es argumentos: min1 (mismo kernel) terminó en `kmem_range_init`, mucho después.

## 4. Propuesta (sin construir nada todavía)
1. **Antes de min6:** mirar el vídeo de min5 en la columna derecha y contestar: ¿hay lima en y≈312 y violeta en y≈344? ¿Cuánto tarda la pantalla en cambiar de "texto + columna" a "azul, cian, magenta"? ¿Hay un parpadeo o negro entre ambos?
2. **Si lima y violeta están:** el cuelgue/reinicio está en `arm_vm_init`. min6 = parche `0340` con bloques dentro de `arm_vm_init` (antes y después de cada fase: `arm_vm_physmap_init`, `arm_vm_prot_init`, cambio de TTBR0) usando el alias físico mientras exista, y el blanco corregido.
3. **Si faltan:** el parón está entre 6a y 6b: min6 con bloques entre `PE_parse_boot_argn`, `PE_get_default` y el bloque de higiene.
4. **Sobre el reinicio:** si se quiere saber cuántas veces entró `start.s`, hace falta decisión del Director para leer el marcador de RAM desde TWRP (lectura sin escritura). No lo pido aún.

## 5. Lectura de solo lectura desde TWRP (D-0038, E-0054)
- **Método:** `/proc/iomem` y `/proc/last_kmsg` (opción 2 de la jefatura, aprobada por el Director). `/dev/mem` no existe en TWRP; **no se creó** (mknod necesitaría autorización explícita).
- **last_kmsg** (1,9 MB, no se sube a git): es el registro de la sesión Linux/TWRP anterior (hasta ~1245 s) seguido de **líneas de S-Boot**. Muchas líneas tienen bits alterados (`Booqt` por `Boost`), así que sirve de indicio, no de transcripción. **No contiene texto de XNU** (`A5 XNU…`, `XNUELET1`).
- **Cuatro** bloques `load Secure Payload done` al final = cuatro pasadas de S-Boot. Con el flujo del Director (`adb reboot` hacia min5, reinicio forzado con teclas, entrada a TWRP con teclas) se esperan ~3; la cuarta **podría** ser un reinicio por hardware durante min5, pero no es atribuible: no hay marcas de tiempo en las líneas de S-Boot. **Evidencia débil, no concluyente.**
- **Siguiente lectura útil (necesita autorización explícita):** crear `/dev/mem` (nodo temporal en el disco virtual de TWRP) y leer 4 KiB en `0x8ffff100` para ver si `XNUELET1` está; solo dice que `start.s` corrió, no cuántas veces ni por qué se reinició.

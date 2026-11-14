# S7GE_MIN2_ANALYSIS — segundo arranque (min2): qué dice la pantalla y qué no (2026-11-14)

**Proveniencia.** Otra transcripción de Gemini (con un prompt estructurado), enviada por el Director; **no he visto el vídeo ni fotos**. Una cadena de la transcripción, `NO XNU ON`, **no existe** en ningún sitio (§1): es casi seguro una mala lectura. Nivel de evidencia: observación de dispositivo de segunda mano → **L2** (E-0047).

## 1. Qué se transcribió
Logo Samsung ("SAMSUNG Galaxy S7 / POWERED BY android") → `HEROLTE XNU LOADER` / `COPYING KERNEL` / `RAM BASE 0000000080000000` → `NO XNU ON` → tres bloques blancos pequeños en vertical (arriba a la izquierda) y, a su derecha, tres bloques horizontales apilados (**magenta, cian, azul**). **Pantalla fija, sin panic, sin líneas `HEROLTE KMEM:`, sin `handshake`, sin consola.**
- **`NO XNU ON` no aparece** en el cargador (`strings` de `xnu_boot.Image`: `HEROLTE XNU LOADER`, `COPYING KERNEL`, `RAM BASE`, `ENTRY`, `BOOTARGS`, `JUMP TO XNU`, y los errores `LOADER FAIL…`) **ni** en el kernel del CI (solo `XNU ENTRY` y `XNU MMU ON`). Candidatas a lo que realmente se leía: **`XNU MMU ON`** (kernel) o `JUMP TO XNU` (cargador). Hay que mirar la pantalla, no la transcripción.
- Falta en la transcripción `ENTRY`, `BOOTARGS` y `JUMP TO XNU`, que el cargador **sí** imprime antes de saltar: o no se leyeron o la pantalla no las mostraba en ese momento.

## 2. Lo que son esos bloques de colores (corrige a la jefatura)
La jefatura los tomó por "un indicador de estado del bootloader". **No lo son: los dibuja el propio XNU**, en ensamblador, en las primeras instrucciones (`osfmk/arm64/start.s`, bajo `A5XELTE`, que la placa herolte reutiliza con el framebuffer del S7 `0xe2a00000`; parches 0092, 0200, 0208). Cada uno es un rectángulo de **36 × 21 píxeles** en la columna `x = 240`, de arriba abajo, y marca una etapa:
| Fila `y` | Color | Etapa (en `start.s`) |
|---|---|---|
| 88 | **verde** | entrada de XNU (antes de la pila y del runtime de C) |
| 120 | **azul** | **MMU de 4 KiB encendida** y alias del framebuffer funcionando |
| 152 | **cian** | `fp_enabled` (coma flotante habilitada) |
| 184 | **magenta** | `tunables_done` |
| 216 | **amarillo** | `arm_init_jump`: justo antes de saltar a `arm_init()` (C) |
Además, en blanco: `XNU ENTRY` en (24, 256) y `XNU MMU ON` en (24, 288).
**Consecuencia positiva y sólida si la transcripción se mantiene:** ver **azul, cian y magenta** implica que **XNU ejecutó su ensamblador de arranque en esta unidad hasta `tunables_done`** (y `XNU MMU ON` encaja con el texto blanco). Esto **no** lo había asegurado el primer arranque con certeza (allí solo había un panic transcrito).
**Lo que falta:** la transcripción **no menciona el verde (entrada) ni el amarillo (`arm_init_jump`)**. Si **no están**, el kernel se paró **entre `tunables_done` y `arm_init_jump`** (el verde puede estar tapado o no haberse visto); si **sí están**, el kernel entró en C (`arm_init`) y el cuelgue es **posterior**. **Una foto fija de la pantalla lo resuelve.**

## 3. Qué se puede y qué no se puede concluir
| Afirmación (de la jefatura u otra) | Veredicto |
|---|---|
| "Ya no hay panic, **luego `vm_compression_limit` funcionó**" | **No demostrado.** La ausencia de texto de panic **no es avance**: un cuelgue silencioso (o un panic que no se llega a dibujar) también la produce. Solo se sabría que pasó `kmem_range_init` si se vieran las líneas `HEROLTE KMEM:`, y **no se ven** |
| "El kernel pasó a un estado posterior" | **no consta** |
| "ADT incorrecto / handoff incompleto / hardware sin inicializar" (causas "probables" de `NO XNU ON`) | **sin base**: parten de una cadena que no existe |
| "El kernel espera un servicio Apple que no existe" | **no consta** |
| "El kernel arrancó (hito)" | **el ensamblador de arranque se ejecutó** (si los bloques son los de §2); nada más |
| "Min2 cambia solo una variable respecto de min1" | **cierto** (E-0045); por eso **cualquier diferencia de comportamiento** viene de `vm_compression_limit=98304 vm_compressor=2`, pero **no sabemos aún si en el sentido bueno** |
Hay una **pregunta abierta de fondo**: con la consola de texto del kernel activa por defecto ("The kernel text console keeps drawing over the GUI by default", `0046`), **debería** verse texto del kernel (al menos el banner y las líneas `HEROLTE KMEM:` de `kmem_range_init`, que se imprimen **siempre**, pase o falle). Que no se vea **ninguna** línea es **informativo y no explicado**: (a) el kernel se paró antes de la consola; (b) la consola no pinta en este panel todavía; (c) Gemini no las transcribió. **No tengo cómo distinguirlo sin ver los fotogramas.**

## 4. Lo que pido antes de decidir nada (cuesta 5 minutos al Director)
1. **Una foto fija (o un fotograma pausado) de la pantalla final**, de cerca y sin transcribir con IA. Con la tabla de §2 se lee en segundos cuántos bloques hay y de qué color, y si están `XNU ENTRY` / `XNU MMU ON`.
2. **Otra del instante en que aparece el texto del cargador** (`ENTRY`, `BOOTARGS`, `JUMP TO XNU`): `BOOTARGS` muestra la línea de arranque efectiva y confirmaría que min2 lleva `vm_compression_limit=98304 vm_compressor=2`.
3. Si hay más texto debajo o alrededor, otra foto de esa zona.

## 5. Opciones para el siguiente paso (ninguna ejecutada; cada escritura de BOOT exige una autorización NUEVA con imagen y hash)
| Opción | Qué es | Coste / riesgo |
|---|---|---|
| **P. Mirar primero (recomendada)** | las fotos de §4; con ellas se sabe si el cuelgue es en el ensamblador o en C | cero riesgo; sin escribir nada |
| **Q. Leer lo que el kernel dejó en RAM tras el reinicio** | si el kernel o Samsung dejan un registro en RAM que sobrevive a un reinicio en caliente (pstore/`last_kmsg`, o el marcador `A5XELTE_MARKER_PA`), se puede leer desde TWRP **sin escribir** | es una **lectura del teléfono** que D-0034 **no nombra** (solo BOOT y EFS): requiere que el Director la autorice; **no está comprobado** que herolte tenga ese registro |
| **R. Una imagen que informe del progreso** | p. ej. más marcas de color en pantalla en puntos concretos de `arm_init`/STARTUP, o salida de texto por la consola | **cambia el kernel** (parche + CI + `publish`, D-0030 cubre push/CI a `mio`), una candidata nueva y su autorización: varias horas |
| **S. Probar con 1 536 MiB** (la RAM con la que el upstream sí arrancaba) | ADT nuevo con `dram-size 0x60000000` y la misma línea de min2 | candidata nueva (PC, minutos) y autorización; **pero sin saber en qué punto se para, es una apuesta**, no un diagnóstico |
| **T. Restaurar Android** | `S7GE_FLASH_PROCEDURE.md` §4 | 5 minutos; el teléfono vuelve a funcionar |
**Sobre "autorizo seguir con min3 o lo que tú veas":** **no puedo tomarlo como autorización de escritura**: una autorización roja nombra **una imagen y su hash** (AUTHORITY.md §4) y hoy **no existe ninguna min3**; sería una apuesta sin datos. Lo que sí hago con esa frase es **preparar** (PC, sin riesgo) lo que haga falta cuando haya datos, y **pedir la autorización concreta** entonces.

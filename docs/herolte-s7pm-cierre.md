# S7PM: qué significa "completo" antes de abrir S7GE

Decisión del Director (2026-11-20): S7PM incluye el gobernador y todo lo demás; no se congela con un tope fijo. Este documento fija los criterios de cierre, para no cerrarla ni por cansancio ni por no acabar nunca. Estado de partida: E-0325 a E-0330, `docs/herolte-governor-v2.md`, `docs/herolte-s7pm-arquitectura.md`.

## Lo que ya se sabe (medido)

| Hecho | Evidencia |
|---|---|
| 1976 MHz es el mejor tope de los núcleos grandes; 2288 cuesta +10 % a +25 % de corriente sin mejor fluidez ni apertura de apps; 1664 no ahorra y satura más | E-0325, E-0326, E-0328 (tres arranques) |
| El gobernador v2 no ahorra frente a un tope fijo y empeora el reparto de intervalos del paginado | E-0329 |
| El suelo con la pantalla apagada es 284 mA | E-0319 |
| min100 usa `herogov=1` (dos estados), que el banco no ha medido | D-0119 |
| assetsd se cierra unas 30 veces por arranque: trabajo en segundo plano sin medir | E-0328, E-0330 |

## Criterios de cierre de S7PM (todos medibles con el banco)

1. **Gobernador:** una política cuya corriente en paginado y búsqueda sea menor que la de un tope fijo a 1976 MHz con una diferencia mayor que el ruido (intervalo de confianza que no incluya el cero) y con un reparto de intervalos no peor. Si tras tres intentos razonados ninguna lo logra, se cierra con la mejor medida (puede ser herogov=1 o el tope fijo) y se documenta por qué.
2. **Línea base de segundo plano:** corriente de la pantalla de inicio sin apps (hoy ~618 mA) con y sin el cierre en bucle de assetsd; si arreglarlo la baja, entra en la imagen de uso diario.
3. **Señal del gobernador:** probar instrucciones por ciclo (PMU del Mongoose) como señal de memoria frente a cómputo, que es la hipótesis que explicaría por qué la ocupación engañó al v2 (hipótesis, sin probar).
4. **Imagen de uso diario nueva** que reúna lo que gane, medida frente a min100 con el banco en un mismo arranque.
5. **Documentación y aula** al día (informe didáctico del hito).

## Orden de trabajo

1. Medir herogov=1 frente a tope fijo y frente al v2 (el banco necesita un modo "v1"; parche pequeño).
2. Prueba de solo lectura de la PMU: el kernel de herolte no tiene soporte (`osfmk/arm64/perfmon_arm64.c` es de la PMU de Apple, registros PMCR0_EL1); hay que leer la PMU estándar de ARMv8 (PMCR_EL0, PMCCNTR_EL0, PMEVCNTR) en los núcleos grandes y registrar instrucciones y ciclos por ventana.
3. Si la señal discrimina memoria de cómputo en el banco, un gobernador v3 que la use.
4. Arreglo de assetsd (pide confirmación antes de escribir en USERDATA).
5. Imagen de uso diario y cierre.

## Lo que NO bloquea S7GE
El diseño y el código de S7GE en el PC (traducción de Metal, representación intermedia, mapeo a Midgard) no usan el teléfono; se puede avanzar en paralelo con los pasos 1 a 3 siempre que no toquen la misma partición de BOOT.

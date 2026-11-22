# Informe de aprendizaje: reposo profundo de núcleos por PSCI y un error mío de edición

> *Informe retroactivo (D-0091), reconstruido a partir de `HEROLTE_PROGRESS.md`, el historial de Git y las evidencias de gobierno. Desde aquí el trabajo es del equipo de este repositorio.*

## 1. Qué hicimos y por qué
Buscando el consumo de reposo, se intentó apagar los núcleos ociosos con la llamada PSCI `CPU_SUSPEND`, como hace Linux. Funcionó en pruebas tempranas, dejó de funcionar durante cinco imágenes seguidas y la causa fue un borrado accidental mío.

## 2. El concepto
- **PSCI CPU_SUSPEND:** el kernel pide al firmware apagar el núcleo y despertarlo en una dirección dada (el trampolín en 0x8fffe000).
- **Paso del PMU:** antes de la llamada, Samsung pone a 0 los bits de energía local del núcleo en sus registros de configuración (`exynos_cpu.power_down`). Sin ese paso el núcleo se apaga pero **no despierta**.
- **Residencia mínima:** no compensa apagar un núcleo si va a despertar enseguida; Linux exige que el próximo evento esté a más de unos milisegundos.
- **Depuración por contadores:** `enter` y `resume` por núcleo (vía el log síncrono del núcleo 0).

## 3. La evidencia (medido)
- min68-min70: el núcleo entra y nunca vuelve (`resume 0`).
- min71 (E-0290): un núcleo con el paso del PMU **y** un temporizador de 2 ms armado a mano: funciona. min72: seis núcleos, pero 60-70 ciclos por segundo y 3 fps.
- Parche 0443 (residencia de 3 ms): al quitar el bloque de prueba del temporizador, **borró por error las dos líneas del paso del PMU**. min73-min77 corrieron sin él: `resume 0` en todos (min77: `CPU_ON recovery 0`, 543 señales de despertar sin efecto).
- E-0293: causa hallada leyendo el código tras min77 (grep de la función) y comprobada en min78 con el paso restituido en el binario (`and w8, w8, #0xfffffff0` antes del `smc`): los seis núcleos entran y despiertan.
- **Mis explicaciones intermedias fueron erróneas:** dije que el temporizador de un núcleo y las señales entre núcleos no despiertan un núcleo apagado. Venía de una escritura que faltaba, no del hardware.

## 4. Cómo defenderlo
**Pregunta posible:** ¿Qué te hizo encontrar el error tras cinco pruebas?
**Respuesta modelo:** El log mostraba `resume 0` en todos los núcleos, igual que en pruebas anteriores que sí sabía sin el paso del PMU. Fui al código de la función y comprobé con grep que la escritura ya no estaba.

**Pregunta posible:** ¿Qué lección sacaste?
**Respuesta modelo:** Tras quitar un bloque de código, comprobar con grep que sigue lo que debía seguir y reconstruir una imagen conocida buena antes de sumar cambios. Y no dar explicaciones de hardware sin haber descartado un fallo mío.

**Pregunta posible:** ¿Por qué el paso del PMU es necesario?
**Respuesta modelo:** Es lo que hace el código de Samsung antes de cada suspensión, y lo medido es que sin él el núcleo se apaga y no vuelve. El mecanismo interno exacto del PMU no lo tengo documentado: eso es una hipótesis aún por confirmar con el manual del chip.

## 5. Para profundizar
Parches `0437`-`0449`, `/tmp` de referencia de Samsung (`exynos-powermode.c`, `exynos-pmu.c`), evidencias E-0290 a E-0295.

# Gobernador de frecuencia v2 (`herogov=2`) — diseño

Estado: parche 0467, compilado en CI, **sin probar en el teléfono** (min102 pendiente de aprobación). Todo lo que sigue como «medido» cita su evidencia; lo demás son hipótesis.

## Problema
Las pruebas min98-min101 (E-0318, E-0320, E-0321) muestran que:
- Durante el uso, los **ocho núcleos** trabajan casi todo el tiempo y el clúster pequeño más que el grande (E-0318). **Medido.**
- Bajar el tope de los núcleos grandes de 2288 a 1976 MHz ahorra un 21 % de corriente en uso sin pérdida apreciable de fluidez (E-0320) y a 1664 MHz un 22 % más (E-0321), pero el Director nota la interfaz «un poco más lenta» a 1664. **Medido (corriente) y observado (lentitud).**
- Las lecturas de carga son promedios de 2 s: el núcleo grande más cargado casi nunca se satura en ese plazo (5-7 % de lecturas por encima del 85 %), pero eso esconde ráfagas de ~100 ms al 100 %. **Medido; la conclusión sobre las ráfagas es una inferencia.**
- El gobernador anterior (`herogov=1`) muestrea cada 200 ms, tiene **dos** estados (728 MHz y un único valor fijo) y necesita 1 s de reposo para bajar. **Del código.**

Conclusión de diseño: un tope fijo obliga a elegir entre calor y fluidez. Hace falta **escalar con la carga y con poca latencia**.

## Diseño
Un hilo del kernel propio, cada **20 ms**:

| Elemento | Decisión | Por qué |
|---|---|---|
| Métrica | ocupación del núcleo grande **más cargado** (la interfaz depende de un hilo) y media de los cuatro | la media esconde un hilo saturado |
| Niveles | 728 (estado de S-Boot), 1352, 1664, 1976, 2288 MHz | tasas de la tabla ECT de Samsung leída en el teléfono |
| Selección | MHz necesarios = ocupación × frecuencia actual / 0,80; el nivel más bajo que los tiene | margen del 20 % para que la ráfaga siguiente no sature |
| Subir | de inmediato, directamente al nivel necesario | latencia de subida ≈ 20 ms en vez de ≈ 200 ms |
| Bajar | un escalón cada 120 ms de holgura sostenida (6 muestras) y mínimo 60 ms desde el último cambio | histéresis: no oscilar (cada cambio relocaliza el PLL) |
| Reposo | 1 s con media < 6 % → 728 MHz | igual que el gobernador antiguo |
| Táctil | dentro de 400 ms de un evento de dedo, nunca por debajo de 1664 MHz | el usuario espera respuesta inmediata al tocar |
| Térmica | a menos de 8 °C del umbral `herohot`, máximo 1976 MHz; sobre el umbral, 728 MHz | protege el chip y la batería |
| Pantalla apagada | siempre 728 MHz | paridad con el diseño anterior |

El hilo es **dueño del clúster** mientras corre: el gobernador antiguo y el paso de tasas de prueba (`herocycle` de 0433) quedan inhibidos con `gov_on == 2`.

## Transiciones de reloj
Reutiliza `hc_go_high`, `hc_rate` y `hc_go_low` (las del clúster ya en producción desde 0330): tensión primero al subir, PLL a través del reloj de reserva (BUS_PLL/2, 528 MHz) durante el reenganche, tensión después al bajar. Tasas en una **única tabla** (`hc_rate_rows`) con una fila nueva, 1352 MHz (`M 156`, 812,5 mV, `DIV_SCLK_PROMISE 3`).

## Qué se mide (telemetría cada 10 s, líneas `HEROLTE GOV2`)
- reparto del tiempo por nivel (por mil);
- número de cambios (subidas y bajadas) y **cuánto tarda un cambio** (media y máximo, µs);
- eventos de impulso por el táctil;
- **muestras de 20 ms saturadas (≥ 90 %) en el nivel máximo**: la medida de capacidad que faltó en min101;
- las 120 primeras transiciones, una a una, con la ocupación que las provocó.

## Cómo se decidirá si es mejor
Misma tanda de uso que min98-min101 y las mismas métricas (corriente en uso, temperatura del SoC), más las nuevas (saturación al nivel máximo, tiempo por nivel). Criterio previo, fijado antes de mirar los datos:
1. **Corriente en uso** menor que la de min100 (1422 mA) — o la fluidez percibida igual que min100.
2. **Muestras saturadas en el nivel máximo** no mayores que el 10 % de las muestras.
3. **Sin cambios de reloj fallidos** y tiempo medio por cambio inferior a 5 ms.
4. La percepción del Director, que es un dato y no se descarta aunque la métrica no la vea.

## Riesgos conocidos
- Cada cambio relocaliza el PLL del clúster: unas decenas de cambios por segundo en carga irregular podrían costar rendimiento. Mitigación: histéresis y tiempo mínimo entre cambios; la telemetría mide el coste.
- El clúster **pequeño** sigue a 1066 MHz (`herolittle` queda aparte: a 1586 MHz costó +153 mA sin mejora medible, E-0319).
- La tensión de 1352 y 1664 MHz es la de Linux para este chip (más alta que la de las tasas ya probadas por el proyecto): seguridad antes que ahorro.
- Primera vez que el kernel de este teléfono cambia de tasa a esta cadencia. Si se cuelga, se vuelve a min100.

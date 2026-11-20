# S7PM: gestor de energía y rendimiento del S7 — arquitectura propuesta

Propuesta, no implementación. Lo «medido» cita su evidencia; lo demás son hipótesis o estimaciones de esfuerzo. Es el equivalente en energía y rendimiento de lo que S7GE es para los gráficos.

## 1. Dónde estamos (medido)
- Suelo con la pantalla apagada: 519-535 → **284 mA** (-46 %): paro del DECON, ocho dominios de energía apagados y restaurados (E-0304, E-0308, E-0311, E-0312).
- En uso, con el tope de los núcleos grandes en 1976 MHz: **-21 % de corriente** y -2 °C sin pérdida apreciable de fluidez (E-0320); a 1664 MHz otro -22 %, pero más lento (E-0321).
- Los ocho núcleos trabajan casi al tope en uso y el **clúster pequeño más que el grande** (620 frente a 392 por mil, E-0318).
- El clúster pequeño estaba en 1066 MHz (confirmado por lectura directa, E-0319); a 1586 MHz costó +153 mA y no mostró mejora medible.
- **Limitación del método actual:** cada prueba es una escritura de BOOT, una tanda de uso manual y una sola muestra por condición. No es escalable ni estadísticamente fuerte.

## 2. Arquitectura en capas

```
  ┌──────────────────────────── Laboratorio (web) ────────────────────────────┐
  │ escenarios · comparaciones A/B con IC95 · regresiones · gemelo digital     │
  └───────────────▲───────────────────────────────────────────────────────────┘
                  │ telemetría (anillo persistente + registro)
  ┌───────────────┴──────────── S7PM (kernel) ───────────────────────────────┐
  │ 6. Banco de escenarios y multiplexado de experimentos (heroexp)            │
  │ 5. Política: gobernadores por dominio + modelo de energía + térmica        │
  │ 4. Planificador: topología asimétrica (pequeños/grandes) y QoS             │
  │ 3. Reposo: estados de CPU por residencia, agrupación de temporizadores     │
  │ 2. HAL de dominios (DVFS, PMU, PMIC) alimentada por la tabla ECT           │
  │ 1. Telemetría unificada: carga, MHz, mV, mA, °C, pacing de fotogramas      │
  └────────────────────────────────────────────────────────────────────────────┘
```

### 1. Telemetría unificada (base de todo)
Ya hay piezas sueltas (`HEROLTE PWR/GOV/FB`). Falta un **formato único** con marca de tiempo por muestra (hoy el tiempo se reconstruye a ±5 s con los latidos) y un **anillo persistente** que sobreviva a un cuelgue. Añadir el **intervalo entre fotogramas presentados** (jank) y la **latencia del táctil a pantalla**, que son las medidas de fluidez que de verdad faltan (E-0317).

### 2. HAL de dominios alimentada por la ECT
La tabla ECT (frecuencias, divisores, PLL, tensiones por grupo ASV) está en memoria, cargada por S-Boot (`0xA0000000`, 0x19000 bytes; Linux la lee y la expone). Hoy transcribimos a mano las filas (y ya hubo un error de escala de 300 mV, E-0314). **Analizar la ECT en el kernel** elimina esa clase de errores y da de golpe las tablas de los siete dominios (grandes, pequeños, GPU, memoria, bus interno, pantalla, cámara). Es la parte más sólida y tiene riesgo bajo: es de solo lectura.

### 3. Reposo de la CPU
Ya probamos estados de reposo profundo y el apagado de clúster (E-0301): **sin ahorro demostrable**. La hipótesis abierta es que los despertares son demasiado frecuentes (temporizadores a 100 Hz, interrupciones del táctil y de la pantalla) para que compense bajar a un estado profundo. Un gobernador de reposo por **residencia** (como el `menu` de Linux) y la **agrupación de temporizadores** atacan la causa en vez del síntoma. Linux en TWRP consume 25-35 mA con la pantalla apagada: es la referencia de qué es posible, frente a nuestros 284 mA.

### 4. Planificador con topología (probablemente la palanca más grande)
XNU tiene soporte de clústeres asimétricos (hilos «P» y «E») que este port no usa: **trata los ocho núcleos como iguales**. Hallazgo medido: el clúster pequeño soporta más trabajo que el grande (E-0318) y el hilo de la interfaz, que es el crítico, compite con tareas de segundo plano en núcleos lentos. Declarar la topología (núcleos 0-3 eficientes, 4-7 de rendimiento) y asignar por calidad de servicio (interfaz y táctil a los grandes, indexado y red a los pequeños) puede mejorar fluidez **y** consumo a la vez. Es hipótesis, no resultado.

### 5. Política
- Un gobernador por dominio (`herogov=2` ya cubre los núcleos grandes, parche 0467) con el mismo esqueleto: muestreo rápido, margen, histéresis, suelos por evento.
- **Modelo de energía** (potencia ≈ C·V²·f + fuga) con las tablas de la ECT, para elegir la combinación de niveles de ambos clústeres y de la memoria con menor coste para una carga dada.
- **Marco térmico:** zonas (SoC, batería), puntos de disparo y «dispositivos de enfriamiento» (frecuencia de ambos clústeres, brillo, GPU) con un controlador proporcional-integral en vez de umbrales fijos.
- Memoria y buses (`MIF`, `INT`): hoy a 0,881 V y 0,8125 V fijos frente a 0,575 V y 0,631 V en reposo de Linux (E-0314), pendientes de medir su frecuencia.

### 6. Banco de escenarios y multiplexado de experimentos (el multiplicador)
Es la pieza que cambia el ritmo del proyecto. Hoy una escritura de BOOT produce **una** comparación y necesita tu mano. Propongo:
- **Escenarios automáticos:** el kernel ya sabe inyectar eventos de dedo (`sweet_hid_touch`); un guion (deslizar 10 veces, abrir y cerrar una app, reposo, pantalla apagada) se ejecuta **igual cada vez**, sin intervención.
- **Multiplexado:** un solo arranque recorre N configuraciones (`heroexp=A,B,C`), cambiando en caliente tope, gobernador o parámetros, con el mismo guion para cada una y alternando A/B/A/B para cancelar la deriva (temperatura, batería, tiempo desde el arranque).
- **Resultado:** una escritura produce varias comparaciones con intervalo de confianza, no una muestra única. Con **22 escrituras** restantes, esto vale más que cualquier optimización puntual.
- **Guardia de bucle de cuelgue:** si el arranque anterior no llegó a un estado sano, el siguiente desactiva solo las funciones experimentales (marca persistente en la cabecera del registro). Menos restauraciones manuales.

## 3. Orden por valor y riesgo
| # | Pieza | Valor | Riesgo | Esfuerzo (estimación) |
|---|---|---|---|---|
| 1 | Banco de escenarios + multiplexado + guardia | muy alto (multiplica todo lo demás) | bajo | medio |
| 2 | Telemetría unificada con tiempo por muestra y pacing | alto | bajo | bajo |
| 3 | Lector de la ECT en el kernel (solo lectura) | alto | bajo | medio |
| 4 | Topología y QoS en el planificador | probablemente el mayor | medio | alto |
| 5 | Marco térmico y modelo de energía | medio | medio | medio |
| 6 | Reposo por residencia | medio (incierto: E-0301) | medio | alto |
| 7 | DVFS de memoria y bus interno | medio | **alto** (la DRAM puede corromper datos) | alto |

## 4. Límites honestos
- No sé cuánto valen 4 y 6 hasta medirlos; son las dos que más podrían mover el suelo de 284 mA y la fluidez, y las dos más inciertas.
- Medimos con el medidor de batería del propio teléfono, que es grueso. Un medidor USB externo (unas decenas de euros) daría una referencia independiente.
- El techo de fluidez real lo pone el dibujado por CPU sin GPU (E-0316, E-0317): S7PM mejora lo que hay, S7GE es lo que lo cambia de verdad.
- Esto es trabajo de un equipo durante meses en una empresa. Aquí avanzará por capas, cada una con su evidencia, su documento y su criterio de éxito fijado antes de mirar los datos.

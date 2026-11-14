# S7GE_OSMESA_B2_RISKS — riesgos de mantener el frontend OSMesa sobre un Mesa moderno (Fase 21, 2026-11-14)

**Análisis de riesgo con lo medido hoy** (`S7GE_OSMESA_MESA26_COMPATIBILITY.md`). Probabilidad e impacto son **estimaciones mías**, no medidas, salvo donde dice "medido".

| # | Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|---|
| B1 | **El state tracker de Mesa cambia** y `osmesa.c` deja de compilar (las 18 funciones y 12 tipos coinciden **hoy**, medido; cualquier versión posterior puede romper) | alta con el tiempo | medio | `integrate.py` falla en alto; compilar **en cada actualización** (N1 es barato: ~3 min); fijar una versión de Mesa por release del proyecto |
| B2 | **Los internos que usa nuestro glue** (`osmesa_hero.inc`, `hero_hw.c`, el gancho de `mmap` de Panfrost) cambian más que el frontend | **alta** (ya fallan 2 ediciones en 26.2.4, medido) | alto | portar el gancho y el glue una vez (N3) y mantener una **lista mínima de puntos de contacto** con Panfrost; considerar enviar un cambio **upstream** que haga el gancho configurable |
| B3 | El **módulo `postprocess`** y otras piezas que osmesa.c usaba se eliminaron: más eliminaciones futuras (p. ej. el state tracker) | media | alto | cada eliminación se parchea con el mínimo (como `0001`); si el state tracker cambia de forma incompatible, **B2 deja de ser viable** y hay que ir a una superficie nueva (S7GL): vigilar la señal |
| B4 | **Panfrost T880 se descuida en Mesa** (hoy sigue siendo compatible: `docs/drivers/panfrost.rst` de 26.2.4 lo lista como Midgard v5 3.1; hay correcciones en 26.1 y 26.2, medido) | baja-media | alto | revisar cada trimestre las notas de versión de Midgard; el fork de OSMesa no cambia esto |
| B5 | **Seguridad:** el fork es código ajeno que mantenemos; los avisos de seguridad de Mesa no nos llegan solos | media | medio | asignar a alguien la vigilancia (hoy no hay nadie) y registrar cada revisión trimestral en `governance/` |
| B6 | **Dos Mesa en paralelo** (25.0.7 en producción y 26.x en pruebas) duplican el trabajo de CI y confunden el drop | media | medio | una sola línea de despliegue; la nueva solo entra tras N5 sin regresión |
| B7 | **El CI de macOS** cambia de imagen (ya pasó a `macos-15`) y rompe la compilación de Darwin | media | bajo | fijar la versión de Xcode/SDK en el workflow; probar N4 con cada cambio de `runner` |
| B8 | **Los fallos de lectura `0x42`** (memoria de la GPU) podrían depender de la versión de Panfrost/Mesa | desconocida | alto | medir con 25.0.7 y 26.x **la misma carga**; no atribuir el fallo a Mesa sin esa comparación |
| B9 | **Licencia:** copia de ficheros MIT con sus cabeceras; el código propio de `gpu/mesa/` sigue **sin licencia declarada** | cierta | bajo-medio | declarar licencia del código propio (decisión del Director); conservar las cabeceras de Mesa (hecho: `SOURCES.sha256`) |
| B10 | **Divergencia de responsabilidad:** el fork se vuelve "de nadie" | media | medio | tarea periódica en el gobierno (revisión trimestral), `T-0037` propuesta abajo |
| B11 | **La aplicación de `integrate.py` y `patch-mesa.py` depende del orden** (se encontró un fallo de idempotencia al probar; corregido) | media | bajo | las pruebas de `test_integrate.py` y rechazar una segunda pasada (hecho) |

## Decisiones/trabajo sugeridos
1. Portar el gancho de `mmap` de Panfrost y compilar con Panfrost (N3) antes de afirmar que B2 sirve para el teléfono. 2. Asignar la vigilancia de seguridad. 3. Declarar la licencia del código propio. 4. Una revisión trimestral registrada. Ninguna es urgente para el primer arranque (la variante mínima no usa GL).

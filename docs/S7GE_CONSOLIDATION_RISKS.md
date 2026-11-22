# S7GE_CONSOLIDATION_RISKS — riesgos de consolidar la serie de parches de GPU (Fase 8, 2026-11-14)

**Análisis de riesgo; no se ha tocado ningún parche.** Completa `S7GE_PATCH_DEPENDENCIES.md`. La jefatura **no autoriza todavía** consolidar (espera a que el Director decida si antes o después del flasheo). Esta fase responde "qué podría salir mal y cómo se probaría" para poder decidir.

## 1. Qué es consolidar (y qué no)
Generar una **segunda serie** de ~10-15 parches cuya aplicación sobre la base dé **exactamente el mismo árbol** que la serie actual de los 63 parches que tocan `herolte_gpu.c` (y los de `SweetFramebuffer.cpp`, `HeroGPU.cpp`, `SweetSurface.cpp`). **No** consiste en quitar parches sueltos (rompería la cadena). La serie antigua **se conserva**.

## 2. Qué parches legacy "se podrían eliminar sin riesgo"
**Ninguno individualmente.** Lo que sí hay son **14 parches sustituidos casi por completo** (PATCH_DEPENDENCIES §2); en una serie consolidada **desaparecen sus líneas muertas** pero el árbol final no cambia. El riesgo de quitarlos de la serie actual es que los parches posteriores asumen su texto. Por eso la única vía sin riesgo es: aplicar todo, generar el árbol, regenerar parches por subsistema y **comprobar la igualdad**.

## 3. Tabla de riesgos
| # | Riesgo | Probabilidad | Impacto | Mitigación / prueba |
|---|---|---|---|---|
| R1 | La serie consolidada **no da el mismo árbol** (se pierde o se cambia una línea) | media | alto (kernel distinto sin saberlo) | `git write-tree` de ambos estados y **comparar hashes**; fallo = no se adopta |
| R2 | Pierde la trazabilidad con upstream (`origin/herolte` sigue añadiendo parches sobre los antiguos) | alta | alto (merge imposible o silencioso) | la consolidada es una **rama paralela** con rango propio (0400+, D-0007 propuesta); nunca sustituye la serie de `herolte` |
| R3 | Un parche nuevo de upstream (0335+) toca `herolte_gpu.c` y ya no aplica sobre la consolidada | alta | medio | decidir **cuándo congelar** la base; rebasar a mano con la regla de R1 |
| R4 | El CI **salta en silencio** un parche que no aplica (se vio con 0334) | media | alto | `ci_check.py` por **nombre completo** (T-0022) para cada parche nuevo; número de aplicados = número esperado |
| R5 | El kernel resultante **compila pero difiere en comportamiento** (orden de hilos, inicialización) | baja si R1 pasa | alto | comparar símbolos exportados y la salida de consola del arranque (variante mínima) antes y después |
| R6 | Consolidar **antes del primer arranque** cambia el kernel que se va a probar: se pierde la comparación con lo probado por upstream | media | medio | **consolidar después del flasheo N2** (o hacerlo y repetir N2); una variable a la vez |
| R7 | Mezclar la consolidación con la separación de `herolte_gpu.c` en el mismo paso | alta si no se vigila | alto | **dos pasos distintos**: primero consolidar (misma salida), luego separar (movimiento) |
| R8 | Los 14 parches "legacy" contienen **comentarios de diagnóstico** que explican fallos de hardware (0258, 0265, 0273, 0307) | cierta | medio | los comentarios sobreviven en el código final; anotar en `S7GE_INVENTORY.md` el origen de cada fallo antes de consolidar |
| R9 | El CI de macOS (runners) cambia (ya pasó a `macos-15`) y un kernel idéntico en fuente no es idéntico en binario | media | bajo | comparar **fuentes aplicadas**, no binarios, para R1; binario solo para R5 |
| R10 | No hay pruebas automáticas del kernel (solo compilación) | cierta | alto | las pruebas de host de DROP v2 y de herramientas **no** cubren `herolte_gpu.c`: añadir un banco con dobles (S7GE_ABI_V2 §9) antes de refactorizar a fondo |

## 4. Estrategia incremental propuesta (cuando se autorice)
1. **Congelar la base** (commit de `herolte-drop-v2` y de `origin/herolte` que se consolidan). 2. Generar el árbol resultante y su hash. 3. Consolidar **un subsistema por parche**, empezando por el de menor riesgo (audio y Wi-Fi: autocontenidos), comprobando R1 tras cada uno. 4. CI y `ci_check` por nombre. 5. **Después** separar ficheros (EXTRACTION_INTERFACES). 6. Repetir N2 solo si cambia el kernel que se prueba.

## 5. Lo que no se sabe
Cuánto de los 14 parches "sustituidos" tiene efecto en el árbol final distinto de cero (se midió por texto); si upstream va a seguir tocando `herolte_gpu.c` (sí lo ha hecho: 0333, 0334); si el Director prefiere un kernel conocido (el de upstream) para el primer arranque (hoy el flasheo planeado usa **ya** una serie fusionada y renumerada, probada solo en el PC).

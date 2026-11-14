# S7GE_OSMESA_TEST_PLAN — pruebas para validar el OSMesa propio (Fase 20, 2026-11-14)

**Plan; solo el nivel 1 está hecho.** Cada nivel dice **dónde** se ejecuta, **qué prueba** y **qué no**. Un nivel superior no se declara superado por pasar el inferior.

| Nivel | Dónde | Estado | Qué prueba | Qué NO prueba |
|---|---|---|---|---|
| **N0 · integración** | PC, sin compilar | **hecho** | `test_integrate.py`: 7 pruebas con un árbol sintético (aplica una vez, rechaza una segunda pasada, ancla ausente falla en alto, fuentes intactas por hash, el parche de postproceso se aplica) | que compile |
| **N1 · compilación + humo** | PC (Linux), Mesa 26.2.4, softpipe | **hecho** (E-0041) | 913/913 pasos; contexto, limpiar, leer el píxel | iOS, Panfrost, rendimiento |
| **N2 · API OSMesa** | PC (Linux), softpipe | **por hacer** | cada función exportada con casos válidos e inválidos (ver §1) | comportamiento de la GPU |
| **N3 · Panfrost + glue** | PC (necesita `libdrm` o el subproyecto) o CI | **por hacer** (bloqueado por `pan_kmod.h`) | que `osmesa_hero.inc` y `hero_hw.c` compilen contra 26.x; que el gancho de `mmap` funcione | iOS, hardware |
| **N4 · Darwin/iOS** | CI de macOS (`mesa-ios.yml`) | **por hacer** (publicar = D-0030) | que el árbol parcheado compile para iOS; los dylibs resultantes con hash | ejecutar en el teléfono |
| **N5 · teléfono** | S7 (acción roja para escribir en él) | **por hacer, mucho después** | `osmesa-test`, `eagl_ca_test`, los casos de regresión de §2 | — |

## 1. N2: batería de API (cuando se ejecute en el PC)
Programa de prueba en C (como `osm_smoke`) con: **creación de contexto** (`OSMesaCreateContext`, `…Ext` con varios formatos RGBA/BGRA/RGB y bits de profundidad/stencil, `…Attribs` con perfil y versión; el perfil ES `0x36` solo existe tras `patch-mesa.py`); `MakeCurrent` con cada formato de píxel y tamaños límite (0, 1, el máximo `OSMESA_MAX_WIDTH/HEIGHT`) y búfer nulo; **`OSMesaPixelStore` y `OSMesaGetIntegerv`** (`OSMESA_ROW_LENGTH`, `Y_UP`); `GetColorBuffer`/`GetDepthBuffer`; **`GetProcAddress`** de `glClear`, `glDrawArrays`, `glTexImage2D`, `glFramebufferTexture2D` y de una función inexistente (debe dar NULL); **varios contextos** en hilos distintos; **destruir** con el contexto actual; `OSMesaPostprocess` (debe avisar, no fallar); una **comparación de símbolos** con `osmesa.sym`. Salida esperada: sin cierres inesperados, sin fugas visibles bajo `valgrind` si está disponible (no lo está en este PC: **no verificado**).
**Pruebas de renderizado** (píxel conocido): limpiar color/profundidad; un triángulo con shader mínimo; una textura 2×2 con `NEAREST`; `glReadPixels` en `RGBA8`/`BGRA`; **FBO** con textura como adjunto; `glFinish` vs. `glFlush`; escalado y mezcla simple. Cada caso con **referencia calculada a mano**, no tomada de la salida.

## 2. Regresión para N5 (lo que ya funciona en el upstream y no debe romperse)
Fondo de pantalla original (`CollectionsPoster`, superficies `420f` de 512×512), galería de fondos (miniaturas 400×400), Safari (negro por caché de CPU: **no regresión**, ya estaba así), calendario/widgets, copia por GPU de render targets a IOSurface (`OSMesaSweetWrapTexture`), `eagl_ca_test`. Criterios: **mismos píxeles** que con Mesa 25.0.7 en las mismas pruebas, y **sin fallos de lectura `0x42` nuevos** (S7GE_EXECUTION_MODEL.md §5).

## 3. Qué comparar siempre contra la línea base 25.0.7
Hashes del dylib por prueba, símbolos exportados (`nm -D`), tamaño, tiempo de arranque de contexto y fotogramas por segundo con `HERO_PROF=1`. **Hoy no hay línea base compilada de 25.0.7 en el PC** (solo el CI de macOS la produce): primera tarea de N4.

## 4. Criterio de "el fork vale"
N1-N2 en verde en el PC; N3 compilando; N4 produce los mismos dylibs funcionales que 25.0.7; **N5 sin regresiones de píxel**. Hasta N5 **no se sustituye** Mesa 25.0.7 en el drop: B2 es una vía en paralelo.

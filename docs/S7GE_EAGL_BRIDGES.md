# S7GE_EAGL_BRIDGES — los dos puentes EAGL y cuál conservar (parte de la Fase 6, 2026-11-14)

**Comparación y propuesta; nada se implementa.** La jefatura (AMARILLO) pide: documentar diferencias, ver cuál está más mantenido y **proponer uno**. Nivel **L1**: cabeceras, `NOTICE.md`, `build-eagl.sh`, historial de git y las notas de `HEROLTE_PROGRESS.md`; **no he leído el cuerpo de `eagl.m` ni de `eagl.c` (1 130 y 4 606 líneas) ni comparado su cobertura de API función a función**, y nada se ha ejecutado.

## 1. Los dos puentes
| | **Shim de Bergamota** (`gpu/eagl/`) | **Puente de HakiOS** (`gpu/hakios-gl/`) |
|---|---|---|
| Qué es | `EAGLContext` sobre OSMesa; `macro_slots.c` (463 líneas) con los offsets de las entradas GL de CoreAnimation (derivados de iOS 18, comprobados contra el `OpenGLES.framework` de iOS 16: 457 entradas coinciden) | `eagl.c` (4 606 líneas) que expone `hakios.gl.h`; `gl_hero.c` (108, propio) lo implementa sobre nuestro OSMesa/Panfrost |
| Licencia | MIT (Bergamota, con cambios "Galaxy S7 port") | MIT (HakiOS, sin cambios + `gl_hero.c` propio) |
| Librería | `libheroeagl.dylib` (`gpu/eagl/build-eagl.sh`) | `libhakiosgl.dylib` (mismo script) |
| Cómo entra en iOS | el kernel inserta `/private/var/herolte/lib/libheroeagl.dylib` en backboardd (`herolte_gl.c`, parche 0245) | hay que **copiarla con ese nombre** (`herolte-drop.py … lib/libheroeagl.dylib=out/lib/libhakiosgl.dylib`, según `NOTICE.md`) |
| Fortalezas anotadas | "es lo que deja correr el renderizador GLES de CoreAnimation sobre Mesa"; hook de QuartzCore **no necesario** en iOS 16 | "censo" de dibujos de CoreAnimation, perfilado (`HERO_PROF`), limpieza de caché de superficies compartidas; es el que se usó en el **último drop probado por upstream** (`8c57e53`) |
| Historial (git, rutas `gpu/eagl` / `gpu/hakios-gl`) | 64 commits, último de upstream 2026-11-13 (el del 2026-11-14 es la fusión local) | 15 commits, último 2026-11-12 |
| Tamaño aproximado | ~2 200 líneas del shim + componentes `heroapp/herosb/hero_prof` | ~4 700 líneas |
Comparten `hero_log.c`, `hero_backboardd.c`, `hero_prof.c` (se enlazan en las dos librerías).

## 2. Lo que dicen los datos de actividad (no de calidad)
- `gpu/eagl` tiene más commits porque **aloja los componentes comunes** (`heroapp`, `herosb`, `hero_prof`, pruebas) además del shim de Bergamota; sus commits recientes son de `libheroapp` y fondos de pantalla, **no del shim**.
- El **diagnóstico gráfico reciente** (`HEROLTE_PROGRESS.md`: censo de superficies, fondo negro, sincronización de caché, "Drop final con hakios-gl `8c57e53`") se apoya en **hakios-gl**.
- El shim de Bergamota queda como **la ruta que el kernel carga por defecto** (el nombre `libheroeagl.dylib` está cableado en `herolte_gl.c`) y la de la que depende `osm.c`/`osmesa_hero.inc` (`OSMesaSweet*`, copia por GPU a IOSurface, MIT).

## 3. Propuesta (no implementada)
**Conservar hakios-gl como puente de producción y mantener el shim de Bergamota como respaldo documentado**, porque (1) es el último que se probó y en el que se está depurando la imagen (censo y perfilado dan observabilidad: principio 2.6 del macroinforme), (2) el nombre que carga el kernel puede apuntar a él sin cambiar el kernel (se copia con ese nombre), (3) la interfaz `hakios.gl.h` aísla la implementación de la API, lo que facilita sustituir el backend por S7GL/S7MCL más adelante.
**Salvedades honestas:** (a) la elección **no se ha medido**: no hay comparación de cobertura de API ni de rendimiento; (b) el shim tiene a su favor haber sido **verificado contra iOS 16** (457 entradas) y ser más pequeño; (c) hakios-gl trae **4 606 líneas ajenas** que hay que mantener; (d) la decisión sobre cuál se inyecta por defecto afecta al **kernel** (el nombre cableado) o al **drop** (renombrar): la segunda es reversible y no toca la serie de parches.
**Pasos previos a decidir:** una comparación de cobertura (¿qué entradas GL de `eagl_slots.txt` implementa `gl_hero.c` frente a las 457 del shim?), una medición de fotogramas con cada uno en el **mismo** drop, y que el Director o la jefatura fijen el criterio. Hasta entonces **no cambiar nada**.

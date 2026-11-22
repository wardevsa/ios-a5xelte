# S7GE_OSMESA_MESA26_COMPATIBILITY — el frontend OSMesa de Mesa 25.0.7 sobre Mesa 26.2.4 (Fase 19, 2026-11-14)

**Medido, no supuesto.** Con la Opción B2 confirmada por el Director (D-0032) se reinyectó el frontend OSMesa de Mesa 25.0.7 en un árbol limpio de **Mesa 26.2.4** (commit `3c479d6a…` del tag) con `gpu/mesa/osmesa-frontend/integrate.py` y se **compiló en Linux** (host del PC; softpipe, sin LLVM, sin Panfrost). Nivel de evidencia: **L1** (compilación) + una prueba funcional mínima en el host. **No** se compiló para iOS/Darwin, **no** con Panfrost y **no** se probó en el teléfono. Evidencia local: `~/HackiOS/builds/device-day/osmesa-b2-20261114/` (E-0041).

## 1. Resultado
| Pregunta | Resultado |
|---|---|
| ¿Compila `osmesa.c` de 25.0.7 con Mesa 26.2.4? | **Sí**, con **un parche mínimo** (quitar el uso del módulo `postprocess`, eliminado de Mesa) y **cuatro adaptaciones de Meson**; `osmesa.c`, `osmesa_target.c`, `osmesa.sym`, `osmesa.def.in` y `osmesa.h` quedan **sin tocar** salvo ese parche |
| Build | 913/913 pasos, rc=0, 0 errores (3 min 11 s con `nice`, 4 trabajos) |
| ¿Exporta la API OSMesa? | **13 símbolos** (`OSMesaCreateContext[Ext|Attribs]`, `MakeCurrent`, `GetCurrentContext`, `GetColorBuffer`, `GetDepthBuffer`, `GetIntegerv`, `GetProcAddress`, `PixelStore`, `ColorClamp`, `Postprocess`, `DestroyContext`) + 1 300 `gl*` |
| Prueba funcional | contexto RGBA 64×64 sobre softpipe: `GL_VERSION = 3.3 (Compatibility Profile) Mesa 26.2.4`, limpia a rojo y lee el píxel `255,0,0,255` (rc=0) |

## 2. Cambios necesarios (la lista completa de lo que rompió)
| # | Qué cambió en Mesa | Dónde se arregla | Tipo |
|---|---|---|---|
| 1 | Mesa 26.x exige **Meson ≥ 1.4** (el sistema trae 1.3.2) | `venv` con Meson 1.12.1 en el scratchpad (no se instaló nada en el sistema) | entorno |
| 2 | Opciones de Meson retiradas (`gallium-vdpau`, `gallium-xa`) | opciones de configuración (`meson-options.txt` de la evidencia) | configuración |
| 3 | `with_shared_glapi` ya no existe | `meson/frontend.build` y `meson/target.build` | Meson |
| 4 | `libglapi_static` ya no existe → `libglapi_bridge`; `src/mapi/` desapareció (el glapi está en `src/mesa/glapi/`) | `meson/target.build` | Meson |
| 5 | `glapi/glapi.h` ahora vive en `src/mesa/glapi/glapi/` | `include_directories('../../../mesa/glapi')` en `meson/frontend.build` (sin tocar `osmesa.c`) | Meson |
| 6 | **El módulo `postprocess` (filtros) fue eliminado** | `patches/0001-osmesa-no-postprocess.patch` (113 líneas); `OSMesaPostprocess()` se conserva y avisa; `osmesa.sym` no cambia | **código** |
| 7 | La opción `osmesa` y `with_osmesa` ya no existen en `meson.options`/`meson.build`, ni los subdirs de `src/gallium/meson.build` ni el `install_headers` | `integrate.py` (4 ediciones exactas) | Meson |
**Lo que NO cambió y es relevante:** las **18 funciones** de Mesa que llama `osmesa.c` (prefijos `_mesa_`, `st_`, `pipe_`, `util_`, `u_`, `cso_`) y los 12 tipos `struct st_*`/`pipe_*` que usa **existen con la misma declaración** (comprobado por texto y ahora **por compilación**). La interfaz con el state tracker de Mesa **sigue siendo compatible**.

## 3. La parte de Panfrost (no resuelta)
`gpu/mesa/patch-mesa.py` en un árbol 26.2.4 con el frontend ya integrado: **10 de sus 12 ediciones aplican y 2 fallan**, ambas en `src/panfrost/lib/kmod/pan_kmod.h` (el gancho `os_mmap` → `herodrm_mmap`, texto `host_addr = os_mmap(...)` / `mmap_offset + bo_offset);`). Es un **portado pendiente del gancho de mmap**. Además:
- el código propio `osmesa_hero.inc` y `hero_hw.c` usa **internos de Panfrost y de Gallium**; no se ha compilado contra 26.2.4 (la compilación con Panfrost no es posible en este PC sin `libdrm-dev`; haría falta el subproyecto de Meson o el CI);
- en 26.x el compilador Midgard se movió a `src/panfrost/compiler/midgard/` y el árbol de `genxml` cambió: las rutas de `patch-mesa.py` pueden quedarse cortas;
- la compilación **para iOS/Darwin** (SDK de Apple) solo la hace el CI de macOS (`mesa-ios.yml`); `gpu/mesa/build-mesa.sh` **sigue fijado a Mesa 25.0.7** y no se ha tocado.

## 4. Veredicto
**B2 es técnicamente viable en la parte de OSMesa** (el frontend "sin postproceso" compila y funciona sobre Mesa 26.2.4 con cambios pequeños y acotados). **Falta lo difícil**: portar el gancho de `mmap` de Panfrost y el glue (`osmesa_hero.inc`, `hero_hw.c`), y compilar para iOS. **Corrección de un dato anterior:** `S7GE_MESA_VERSION_ANALYSIS.md` decía que fallaban "al menos 3 ediciones (`meson.build` y dos de `pan_kmod.h`)": eso salió de una **segunda pasada sobre un árbol ya modificado**; en un árbol limpio con el frontend integrado fallan **2** (`pan_kmod.h`).

## 5. Qué no se midió
Panfrost/NIR/Midgard sobre 26.2.4 (compilación y funcionamiento); Darwin; rendimiento; comportamiento con el perfil ES `0x36` del proyecto; compatibilidad de ABI de `libglapi`/`libgallium` en iOS; ninguna prueba en el teléfono.

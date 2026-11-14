# S7GE_MESA_INTEGRATION — qué hay en `gpu/` y qué se reutiliza o se reemplaza (Fase 6, 2026-11-14)

**Solo lectura y análisis.** Nivel **L1** (código y cabeceras leídos en este repositorio; ni se compiló Mesa ni se ejecutó nada). Las licencias están en S7GE_LICENCIAS.md. Mesa (25.0.7) **no está en el PC**: lo que dice de ella `patch-mesa.py` es lo que el script espera encontrar.

## 1. Cadena actual de OpenGL ES (la ruta que existe hoy)
`CoreAnimation (backboardd)` → `EAGL` (shim) → `hakios-gl` (`gl_hero.c`) → **OSMesa con Panfrost** → `libdrm` falso (`herodrm.c`) → **`HeroGPU` (IOKit)** → `herolte_gpu.c` → Mali-T880.
Es **la ruta de OpenGL ES del macroinforme (S7GL)** ya funcionando en el teléfono del upstream; **no hay Metal**, ni S7GIR, ni compilador propio. S7GE añade encima, no reemplaza todo de golpe (principio 2.8 fallback seguro).

## 2. Componentes
| Componente | Tamaño | Qué hace | Origen / licencia | Veredicto S7GE |
|---|---|---|---|---|
| `gpu/mesa/herodrm.c` | 814 líneas | **libdrm de sustitución**: traduce los ioctl de panfrost (`create_bo`, `mmap_bo`, `submit`, `get_param`…) a los 8 selectores de `HeroGPU`; cola de envío en un hilo; "syncobj siempre señalizado" porque `Submit` es síncrono; tope del heap del tiler (`HERODRM_HEAP_MB`, el kernel cablea la memoria) | propio, **sin licencia declarada** | **Reutilizable como adaptador de transición.** Es el **consumidor principal** del ABI v1: cuando exista ABI v2 se migra aquí primero (S7GE_ABI_V2_PROPOSAL.md §6) |
| `gpu/mesa/hero_hw.c` | 222 | pegamento OSMesa↔HeroGPU: crea la pantalla Panfrost sobre `herodrm`, importa IOSurface como recurso | propio, sin licencia declarada | Reutilizable; **se reescribe** cuando S7IOS defina la importación (propiedad/derecho, ABI v2 `BO_IMPORT_SURFACE`) |
| `gpu/mesa/osmesa_hero.inc` | 253 | puntos de entrada `OSMesaSweet*` (de Bergamota, MIT): copia de render targets de CoreAnimation a IOSurface por GPU y muestreo de superficies "en sitio"; "el alias CPU escribible no está implementado" | Bergamota MIT | Reutilizable en la ruta GL; **no sirve para Metal** |
| `gpu/mesa/patch-mesa.py` | 114 | parchea el Mesa 25.0.x descargado (cada edición afirma que el texto aparece **una vez**: un cambio de Mesa falla en alto) | propio | Bien diseñado; **ata el proyecto a Mesa 25.0.x** |
| `gpu/mesa/build-mesa.sh` | 113 | clona Mesa 25.0.7 y libdrm 2.4.124 y compila `softpipe,panfrost`, `-Dllvm=disabled` | propio | Reutilizable. **Las licencias de Mesa/libdrm no se han verificado** |
| `gpu/mesa/osmesa-test.c` | 159 | prueba de humo de OSMesa | propio | Reutilizable como banco |
| `gpu/eagl/` | ~2 200 líneas (`eagl.m` 1 130; `macro_slots.c` 463; heroapp/herosb/hero_prof/…) | **shim EAGL de Bergamota (MIT)**: `EAGLContext` sobre OSMesa; hace que el renderizador GLES de CoreAnimation de iOS 16 funcione; offsets de macros derivados de iOS 18 y comprobados en iOS 16 (457 entradas) | Bergamota MIT + cambios "Galaxy S7 port" | **Ruta GL actual**; se mantiene mientras no haya S7MCL/S7COMP |
| `gpu/hakios-gl/` | `eagl.c` 4 606 + `gl_hero.c` 108 | puente EAGL de HakiOS (MIT) → `hakios.gl.h`; `gl_hero.c` lo implementa sobre nuestro OSMesa | HakiOS MIT (sin cambios) + `gl_hero.c` propio | Ruta alternativa a `gpu/eagl` (el kernel inserta `libheroeagl.dylib` en backboardd, `herolte_gl.c`); **dos puentes EAGL coexisten**: hay que **elegir uno** para S7GE |
| `gpu/hakios-audio/` | plugin AudioServer | plugin de audio de HakiOS; lo toca `herolte_gpu.c` (`heroaudio=3`) | HakiOS MIT | **No es gráfico**: sale del alcance S7GE (S7GE_SPLIT_PLAN.md: audio fuera de la GPU) |

## 3. Qué de esto sirve para S7GE y qué no
| Pieza S7GE (macroinforme) | ¿Qué hay hoy? | Reutilizable | A construir |
|---|---|---|---|
| S7GL (OpenGL ES) | sí: OSMesa+Panfrost sobre HeroGPU | **toda la cadena**, sin cambios de diseño | pruebas de regresión (sección 29 del macroinforme) |
| S7MCL (Metal) | no | — | todo; el macroinforme lo fija como interfaz principal |
| S7GIR/S7GTE | no | `S7GE_IR_DESIGN.md` (diseño) | validador y traductor |
| S7SHC (shaders) | usa el compilador de Mesa (NIR→Midgard dentro de Panfrost) | **el backend Midgard de Mesa/Panfrost** como base del S7SHC | AIR/SPIR-V→NIR (fuera de Mesa) |
| S7GPU kernel | `herolte_gpu.c` + `HeroGPU.cpp` | núcleo de arranque, quirks, recuperación (S7GE_INVENTORY.md §5) | módulo limpio con ABI v2 |
| S7IOS | `SweetSurface` + `hero_hw` | importación de IOSurface | propiedad y derechos |
| S7COMP/S7PRES | presentación por GPU en el kernel (0235, 0322) | la ruta de escalado | cola de cuadros y vsync (hoy mezclado con DECON en `herolte_gpu.c`) |

## 4. Riesgos de la integración actual
1. **Dependencia fuerte de la versión de Mesa** (25.0.x, texto exacto) y de una `libdrm` falsa: cualquier actualización de Mesa exige repasar `patch-mesa.py`.
2. **Todo el aislamiento entre clientes depende de que el kernel valide**, y hoy no lo hace (S7GE_ABI.md): Mesa construye las cadenas de jobs en el proceso del cliente y las pasa por `jc_va`.
3. **Dos puentes EAGL** (`gpu/eagl` y `gpu/hakios-gl`) y un tercer componente (`herolte_gl.c` en el kernel) que decide cuál se inyecta: falta una decisión.
4. **Sin licencia declarada** en `gpu/mesa/*` propio y sin verificar la de Mesa/libdrm (S7GE_LICENCIAS.md).
5. **Síncrono:** `herodrm` finge syncobjs señalizados; cualquier trabajo que dependa de fences reales no funcionará hasta S7FENCE.

## 5. No leído
`eagl.c` de HakiOS (4 606 líneas) más allá de la cabecera y de `NOTICE.md`; `eagl.m` y `heroapp.c` en detalle; `osmesa-test.c`; los cuerpos de `herodrm.c` más allá de la cabecera y los nombres de función; nada se ha ejecutado.

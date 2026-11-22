# S7GE — Estado real y auditoría de Fase 0 (2026-11-13)

Auditoría **de solo lectura** del árbol real, contrastada con `docs/S7GE_ARCHITECTURE.md` (el documento de dirección, nivel L0). Responde al Anexo C y a la Fase 0 de ese documento con código y parches concretos. Es el documento que manda sobre el **estado**; la arquitectura manda sobre la **dirección**.

**Fuentes leídas:** rama local `herolte-drop-v2` (parches `0001`-`0335`, `gpu/`, `tools/`, `HEROLTE_PROGRESS.md`, `docs/`), `origin/herolte` (upstream, 2026-11-13, commit `f19b73d`), y la red solo para verificar el repositorio A5XELTE citado (informe del subagente de lectura web; no releído por mí línea a línea).
**No he ejecutado nada en hardware, no he escrito registros, no he cambiado código.**

## 0. Aviso de procedencia de la evidencia
`HEROLTE_PROGRESS.md` y las notas de upstream relatan arranques, fotos y mediciones de **otro Galaxy S7 (herolte) del desarrollador upstream**. Es evidencia valiosa del *mismo SoC y la misma GPU*, pero **no es evidencia de esta unidad**: aquí todavía no se ha probado nada (BOOT original de Samsung, Android en USERDATA).
Por eso cada nivel se anota así: **L1** = compila/CI (cierto aquí), **L3h / L4h** = ejecución en GPU / integración con iOS **observada en el teléfono del upstream**, no replicada en esta unidad. Para esta unidad, hoy: L1 como máximo, y L2 en herramientas del PC.

## 1. Qué existe ya, mapeado a los componentes S7GE
| S7GE | Qué hay en el árbol real | Dónde | Nivel |
|---|---|---|---|
| **S7GPU** (identificar/encender) | Sonda de solo lectura y encendido del G3D: `GPU_ID=0x08802000` (T880 **r2p0**), 12 shader cores (`0xff0f`), 1 tiler, 1 L2; S-Boot deja dominio y relojes encendidos | `0225`, `0226` → `bsd/dev/herolte_gpu.c` | L1 + L3h |
| **S7GPU** (quirks T880) | `SC_LS_ALLOW_ATTR_TYPES`, `TC_CLOCK_GATE_OVERRIDE`, `JM_JOB_THROTTLE_LIMIT` (los de `panfrost_gpu_init_quirks`) | `0243` | L1 + L3h |
| **S7DVFS** (reloj/tensión/energía) | `herogpu_mhz` 338…650 con `vdd_g3d` de la tabla del teléfono; ciclo del dominio de potencia; bajada de reloj tras fallos de lectura; sensores TMU para límite térmico | `0264`-`0267`, `0331` | L1 + L3h |
| **S7MMU** | Una sola address space; tablas de la GPU propias; bloque de L3 propio para el pool de usuario (un bug de solapamiento con el nivel 0 de la GPU se corrigió); reutilización de VA y recuperación de fallos | `0226`, `0249`, `0307` | L1 + L3h |
| **S7JMQ / S7FENCE** | Un job a la vez, **síncrono y por sondeo acotado** (sin IRQ de GPU cableada); barrera entre jobs; recuperación de `JOB_READ_FAULT`; **0333/0334 (upstream)**: la espera pasa de girar en `delay(10)` a dormir en trozos de 50 µs | `0247`, `0258`, `0266`; upstream `0333`, `0334` | L1 + L3h |
| **S7MEM** | BOs cableados en kernel, mapeados sin caché en la GPU, escritura combinada en CPU (la Mali no es IO-coherente: `COHERENCY_FEATURES=0`) | `0239` | L1 + L3h |
| **S7IOS** | `SurfaceBO` (IOSurface id → handle/VA/stride/formato/planos) y `SyncBO` (limpiar+invalidar cachés); `0244`: el *wrap* rechaza tamaños truncados; upstream `0332`: envolver solo hasta donde llegan los píxeles | `0046`, `0244`, `0248`; upstream `0332` | L1 + L3h |
| **S7PRES** (copia a pantalla) | Puente `AppleCLCD`/IOMobileFramebuffer (`SwapBegin/End`), vsync a 60 Hz medido, doble buffer en el canal G1 de DECON_F (`0322`, para evitar los cortes horizontales que seguían con un solo buffer; el upstream anotó "funciona muy bien"), escalado por GPU del cuadro de iOS al panel (`sweetfb_gpu=1`, ~4,4 ms/cuadro). **Sin medición de tearing en esta unidad** | `0046`, `0222`, `0235`, `0296`-`0297`, `0320`-`0323` | L1 + L4h |
| **Cliente de usuario** (ABI actual) | `HeroGPU` (IOKit) con selectores `0 GetParam`, `1 CreateBO`, `2 FreeBO`, `3 MapBO`, `4 Submit [jc_va, js]`, `5 Log`, `6 SurfaceBO`, `7 SyncBO` | `0239`, `0248` → `iokit/Kernel/arm/HeroGPU.cpp` | L1 + L3h |
| **S7SHC** (compilador) | Solo **ensamblador a mano** de un shader Midgard (`tools/herolte-midgard-shader.py`) y el compilador de **Mesa Panfrost** dentro de OSMesa para shaders GLSL; **no hay** traductor AIR→SPIR-V→NIR | `gpu/mesa/`, `tools/` | L1/L3h (solo GL) |
| **S7GL** (OpenGL ES) | Mesa 25.0.7 Panfrost (Gallium + Midgard) en OSMesa compilado para iOS, con un `libdrm` que traduce los ioctl de Panfrost a HeroGPU (`gpu/mesa/herodrm.c`); `GL_RENDERER = Mali-T880 (Panfrost)`, **GL 2.1** (no ES 3.1); 256×256 a 159 fps con `glFinish`; puente EAGL para CoreAnimation (`gpu/hakios-gl`, MIT, de HakiOS) | `gpu/mesa/`, `gpu/hakios-gl/`, `gpu/eagl/` | L1 + L3h + L4h parcial |
| **S7MCL** (Metal) | **Nada.** No hay `MTLDevice` provider ni bundle Mali; `Metal` solo aparece como "el blur es de Metal" (fondo negro) | — | L0 |
| **IOAcceleratorES** | Existe un servicio **vacío** (`0260`) que solo evita una espera de 30 s de QuartzCore; sin user client; se apaga con `heroaccel=0` | `0260` | L1 (workaround) |
| **S7GIR / S7GTE / S7PPL / S7COMP / S7TRACE** | No existen. Hay trazas ad-hoc (`HEROGPU:` en el log del kernel, `hakios-gl` con censos de superficies y trazado de cuadros) | — | L0 |

## 2. Respuestas al Anexo C (preguntas críticas)
| Pregunta | Respuesta verificada | Evidencia |
|---|---|---|
| ¿Qué soporte de framebuffer existe? | Puente `AppleCLCD` completo sobre DECON_F; `a5fb_*`/`sweetfb_*` (nativo, escalado, GPU, doble buffer FB2, 60 Hz, tiempo de refresco) | `0046`, `0222`, `0235`, `0296`-`0297`, `0322` |
| ¿IOSurface funcional? | Sí: `IOCoreSurfaceRoot`/`IOSurfaceRootUserClient` en `SweetSurface.cpp` (create, lookup, limits, lookup-from-port, create-port, lock/unlock). En A5 las operaciones de *value/accelerator/shared-event* devolvían éxito sin hacer nada: **por reauditar en herolte** | `0046`; `docs/a5xelte-ios-gpu-integration.md` |
| ¿Información fiable del controlador de pantalla? | Sí, medida: canal G1 (`0x13952000`) de S-Boot, `BASE_ADDR_Y(0)=0xe2a00000`, relojes `MUX_DISP_PLL` (vclk 62,5 MHz → 59,7 Hz), registros de canales VG/G (de `decon_8890` de Samsung, GPL, copia local fuera del repo) | `HEROLTE_PROGRESS.md` (0296-0297, 0320-0323), `0292`, `0320` |
| ¿Qué Device Tree usa el 8890? | El **ADT** se genera con `tools/mkadt_herolte.py` a partir del `d22ap.adt` del IPSW público (iPhone X) más nodos propios (`/herolte-ufs`, `samsung,herolte-display`, bancos de RAM, MACs sintéticas, `/arm-io/wlan`…) | `tools/mkadt_herolte.py` |
| ¿Recursos GPU en ese ADT? | **Ninguno.** No hay nodo de GPU: las direcciones están **fijas en el código**: GPU `0x14ac0000`, CMU_G3D `0x14aa0000`, PMU `0x105c0000` (G3D conf `+0x4060`, estado `+0x4064`). Discrepa con la Fase A de S7GPU ("obtener recursos desde ADT") | `0225` (`HG_GPU_PA`, `HG_CMU_PA`, `HG_PMU_PA`) |
| ¿Controladores Linux de referencia? | `decon_8890` de Samsung (display), `panfrost` (quirks T880; ya aplicados), Mesa Panfrost 25.0.7 (compilador y descriptores). Falta la referencia Linux del `mali_kbase` de Samsung para el 8890 | `HEROLTE_PROGRESS.md`, `gpu/mesa/` |
| ¿Revisión exacta de la Mali-T880? | **r2p0, `GPU_ID=0x08802000`**, shaders `0xff0f` (12), 1 tiler, 1 L2, `COHERENCY_FEATURES=0` (datos del teléfono del upstream) | `0226`, `0231` |
| ¿Soporte de interrupciones GIC? | GICv2 operativo para IPIs/SMP (`0208`); **la GPU no usa IRQ**: se sondea `JOB_IRQ_RAWSTAT`/`MMU_IRQ_RAWSTAT`; sin cablear las IRQ de GPU/JM/MMU | `0208`, `0225`, `0226` |
| ¿Qué partes de IOKit reutilizar? | `HeroGPU.cpp` (servicio + user client), `SweetFramebuffer.cpp`, `SweetSurface.cpp`, `SweetPlatformExpert.cpp` | `0046`, `0239` |
| ¿Versión de Metal que espera nuestro userland? | La del root **iOS 16.7.16 (20H392), iPhone10,3 / D22AP (A11)**: `Metal.framework`, `IOGPU.framework`, `AGXMetalA11.bundle` (`AGXPrincipalDevice`); QuartzCore busca `IOAcceleratorES` e `IOGPUDeviceCreate`. Inspección hecha para A5XELTE sobre el mismo IPSW; **no la hemos repetido sobre nuestro root** | `docs/a5xelte-ios-gpu-integration.md` |
| ¿Qué usa hoy la CPU en QuartzCore? | Sin GPU: `CA::OGL::SW::scanline`, `vAlpha_Blend`/`image_sampler`. Con el puente EAGL: las capas pasan por OpenGL (Panfrost); **el blur (Metal) sigue sin dibujar**; los fondos ASTC y los formatos de 10 bits fallaron y se rodearon (ADT sRGB, ASTC por CPU) | `HEROLTE_PROGRESS.md` (0207, 0316-0317) |
| ¿Formatos que necesita BackBoard? | Superficies `'b3a8'` (BGRA8, 2 planos) 1440×2560 y 1125×2436; PosterBoard `'BGRA'`; WebKit `'w30r'`/`'b3a8'` de 10 bits | `HEROLTE_PROGRESS.md` (0209, 0317) |

## 3. Diferencias entre el documento S7GE y la realidad verificada
| # | El documento S7GE dice / supone | Realidad | Qué hacer |
|---|---|---|---|
| 1 | El árbol `herolte` no es visible; pide la URL de la rama | Está publicado en el fork `darkcloud9998/ios-a5xelte`, ramas **`herolte`**, **`herolte-drop-fixes`**, **`herolte-drop-v2`** (las tres contienen `0204-herolte-exynos-ufs.patch`), y en `origin` (`wardevsa/ios-a5xelte`, rama `herolte`). Mis commits locales posteriores a `99e80fd` **no están publicados** (sin push) | Decidir qué publicar; no hecho |
| 2 | Parches nuevos `0300`-`0309` | **Colisión:** `0300`-`0335` ya existen (`0301` audio, `0307` L3 de GPU, `0317` WebKit…). Además, upstream ya tiene sus propios `0332`, `0333`, `0334` (gráficos) que **chocan con nuestros** `0332` (marcador DROP), `0334` (DROP v2) y `0335` (splash) | Reservar un rango nuevo para S7GE (propongo `0400`+) y **renumerar DROP v2/splash antes de fusionar con `origin/herolte`** |
| 3 | Crear `xnu/iokit/Kernel/arm/S7GPU/…` con `S7GPU.cpp` etc. | Ya existen `bsd/dev/herolte_gpu.c` (hardware, MMU, jobs) y `iokit/Kernel/arm/HeroGPU.cpp` (IOKit + user client): son **S7GPU+S7MMU+S7JMQ en uno**. Crear carpetas nuevas duplicaría | Refactor **incremental** de lo existente, no un árbol paralelo |
| 4 | S7GPU Fase A: recursos desde el ADT | No hay nodo de GPU; direcciones fijas en código | Añadir `/arm-io/mali` (o `/herolte-gpu`) a `mkadt_herolte.py` y leerlo en el kernel; hasta entonces, constantes marcadas como tales |
| 5 | Esperar con IRQ reales, polling solo al principio | Hoy todo es sondeo; 0333/0334 (upstream) lo hicieron dormir, no por IRQ | Tarea S7JMQ: cablear IRQ de GPU/JM/MMU por GICv2 tras auditar el mapa de interrupciones |
| 6 | "Los clientes no proporcionan direcciones de GPU ni descriptores" (§2.5, §23) | `Submit [jc_va, js]` **recibe del cliente la VA de la cadena de jobs**, y Mesa construye los descriptores en BOs propios. En `0239`/`0248` **no encontré** comprobación de entitlement ni de rangos de `jc_va` (no auditado el resto del código) | Es una brecha frente al principio 2.5; hay que auditar y decidir entre validar la cadena o construir los jobs en kernel |
| 7 | "No basta con registrar `IOAcceleratorES`" | Exactamente lo que hace `0260`: un servicio vacío para terminar una espera de 30 s | Mantenerlo marcado como **workaround temporal** (L1, no S7GPU); sustituirlo cuando exista S7MCL |
| 8 | Metal es la API principal; GL es adicional | **Hoy lo que acelera la composición es OpenGL ES vía EAGL/OSMesa/Panfrost**, no Metal; el blur (Metal) es lo que falta. Mesa reporta **GL 2.1**, no ES 3.1 | Mantener la decisión como *dirección*, pero **no retirar la ruta GL** hasta que S7MCL ejecute en hardware; medir qué renderer elige CoreAnimation |
| 9 | Pipeline AIR→SPIR-V→NIR→Midgard "demostrado" en A5XELTE | Según el repo A5XELTE verificado por lectura web: es un **experimento en el host** (`userland/a5xelte-air-translation/`: `spirv_pair_midgard.c` con Mesa 26.2.4 y un `metal2vulkan` externo, ninguno vendorizado, **para GPU ID T720 `0x07201000`**) y su README dice que **no compila shaders Metal arbitrarios**; **no hay licencia por directorio** | Tratarlo como referencia de método; verificar licencias de Mesa y `metal2vulkan` antes de reutilizar nada |
| 10 | Descritos como existentes: `a5xelte-native-metal-runtime.md`, `a5xelte-shader-suite-results.md`, hitos 0150-0177 y "0200 en adelante: pipelines, recursos y compositor" | La lectura web **no encontró** `native-metal-runtime` ni vio `shader-suite-results` (no los abrió; listado truncado). Los documentos que sí se leyeron dicen: `metal-mali-layer.md` "**in progress**… no es soporte Metal completo", píxeles físicos de blend **"pending"**, "universal compositor support is **not achieved**"; `ios-metal-backend-boundary.md`: sin parser de command buffers de Metal, SpringBoard sigue produciéndose por CPU, el paso 3 (backend Metal para Mali) **no implementado** | No dar esos hitos por hechos; tratarlos como pendientes de verificación |
| 11 | "Mesa: T880 con OpenGL ES 3.1" | Lo que corre aquí es OSMesa (GL 2.1) | Anunciar solo lo que pasa pruebas |

### Hechos verificados sobre el repositorio de referencia A5XELTE
`github.com/Xpl0itU/ios-a5xelte-wardevsa`: fork de `orhunnx/ios-a5xelte` (a su vez de `dipa-studio/ios-sweet`), **licencia MIT** ("© 2026 orhunnx and A5XELTE contributors"); `xnu/patches/` bajo **APSL-2.0** (`NOTICE`); 573 commits; último visible 2026-11-03 (`003f32f`). README: "Mali-T720 executes real translated QuartzCore shader jobs" y "General iOS GPU rendering remains incomplete". Su auditoría Panfrost (2026-10-21, Linux v7.2.12) es **específica de T720** (errata `START_MMU` HW_ISSUE_10649, `GPU_SHADER_CONFIG`, teardown de AS1, IRQ enmascarada frente a RAW, ausencia de reset, sin IRQ reales).
**Lección aplicable a T880:** esa lista es un *checklist* de qué revisar en `herolte_gpu.c` (reset conocido, IRQ RAW/enmascarada, teardown de AS, `SHADER_CONFIG`), no un conjunto de correcciones para copiar.

## 4. Matriz de evidencia (L0-L4) de lo que ya hay
| Capacidad | Este PC | Teléfono del upstream |
|---|---|---|
| GPU_ID/topología | L1 | L3h |
| `WRITE_VALUE`, fragment clear, MFBD, triángulo (shader a mano), textura con escalado bilineal | L1 | L3h con oráculo de píxeles (256/256; pantalla completa en 3,26 ms con 12 cores; texels leídos = texels esperados) |
| Mesa/Panfrost: triángulo OpenGL a 159 fps, 8192 píxeles exactos | L1 | L3h |
| IOSurface import (`SurfaceBO`) y escalado GPU del cuadro de iOS | L1 | L4h (SpringBoard visible; 3-11 fps de CoreAnimation en `0235`, mejoras posteriores `0238`, `0323`, `0333`/`0334` según las notas del upstream) |
| Metal / S7MCL / S7GIR / S7SHC (AIR) | L0 | — |
| Estabilidad prolongada, recuperación de fallos (`JOB_READ_FAULT`: causa desconocida) | — | parcial, sin cierre |

## 5. Siguiente trabajo recomendado (todo en el PC, sin tocar hardware)
1. **S7GE_ABI.md:** documentar el ABI *real* actual de HeroGPU (selectores 0-7, semántica de errores, qué valida el kernel y qué no) y la brecha frente a §23 (handles con generación, validación de `jc_va`, entitlements, presupuesto). Es la base para decidir si los jobs se construyen en kernel.
2. **Plan de integración con `origin/herolte`:** reconciliar numeración (nuestros `0332`, `0334`, `0335`), comprobar que `0333`/`0334` upstream aplican sobre nuestra rama y qué cambia en el kernel candidato N2 (hoy basado en nuestro `0334` DROP v2; **no cambiar** sin repetir el verificador de BOOT).
3. **S7GE_HARDWARE.md:** mapa de registros y erratas T880 r2p0 con el checklist de la auditoría Panfrost de A5 (marcando "no verificado"), más el plan para añadir un nodo `/arm-io/mali` al ADT.
4. **Auditoría de licencias** de lo que se pretende reutilizar (Mesa, `metal2vulkan`, `hakios-gl` MIT, A5XELTE MIT/APSL).
5. **Medición** (solo cuando haya hardware autorizado): qué renderer de CoreAnimation se elige y por qué el blur no pasa por GL.

## 6. Lo que sigue sin verificar (y no se afirma)
Contenido exacto de `a5xelte-native-metal-runtime.md` y `a5xelte-shader-suite-results.md`; licencias de Mesa 26.2.4 y de `metal2vulkan`; si existen comprobaciones de entitlement en otras partes de `HeroGPU.cpp`; el comportamiento de `AppleCLCD`/IOSurface herolte frente a las operaciones que en A5 devolvían éxito vacío; cualquier resultado en **esta** unidad.

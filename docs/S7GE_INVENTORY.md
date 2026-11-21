# S7GE_INVENTORY — qué hay hoy en los parches de GPU (Fase 0, 2026-11-14)

**Solo lectura y análisis; no cambia ningún parche ni código.** Nivel de evidencia: **L1** (patches de `xnu/patches/` y el fichero final `bsd/dev/herolte_gpu.c`, 3 465 líneas, del árbol XNU con la serie 0332-0337 aplicada, el mismo que compiló el CI, E-0035/E-0037). **Nada de esto prueba comportamiento en el teléfono de esta unidad** (L3 no existe aún). Lo "vivo/legacy" es una **inferencia** de la lectura (qué función sigue en el fichero final y quién la llama), no una medida; lo no leído está marcado.

## 1. Corrección del alcance: no son 26 parches, y `herolte_gpu.c` no es solo de GPU
Barrido automático (parches que tocan `herolte_gpu.c`, `HeroGPU.cpp`, `SweetSurface*`, `SweetFramebuffer*`, `herolte_gl.c` o llevan "gpu/mali/surface" en el nombre): **86 parches**. El núcleo de GPU propiamente dicho son unos **40**; el resto comparte fichero porque el proyecto usó `herolte_gpu.c` como **cajón de sastre del "hardware Exynos sin driver"**. Reparto por funciones del fichero final (líneas aproximadas por prefijo de función; nombres de función leídos):
| Grupo (medido por funciones, ver S7GE_SPLIT_PLAN.md) | Qué es | Líneas | Primeros parches |
|---|---|---|---|
| GPU (`hg_*`, `hgp_*`, `hgu_*`, `herolte_gpu_*`, 52 funciones) | arranque, tablas, jobs, recuperación, cliente de usuario, presentación | **1 960** (57 %) | 0225-0235, 0239, 0243-0250, 0258, 0264-0267, 0273, 0307, 0333-0334 |
| audio (`ha_*`, `hg_audio_thread`, 18 funciones) | códec por SPI, I2S, tono | 457 | 0278-0283, 0300-0303 |
| Wi-Fi (`hw_*`, `hg_wifi_thread`, 7 funciones) | Wi-Fi por PCIe (firmware, sondeo) | 200 | 0304-0308, 0315 |
| relojes de CPU (`hc_*`, `hg_cpu_up`, 7 funciones) | subida del clúster Mongoose | 205 | 0270-0272, 0274 |
| hilos de energía y estado (`hg_power_thread`, `hg_thread`, `hg_pmic_dump`/`hp_*`, `hg_bus_thread`, `hg_twrp_thread`) | térmica por TMU, mediciones, bus/vsync, vuelta a TWRP | ~385 | 0277, 0330-0331 |
| display (`hfb_*` compartido con la presentación, `hg_decon_measure`) | DECON/DSIM e IDMA del panel | ~100 | 0292-0297, 0320, 0322 |
Total: **3 466 líneas; 3 307 dentro de funciones y 159 fuera** (macros, includes, variables). Los **no-GPU suman ~1 350 líneas (39 %)**.
**Consecuencia para S7GE:** el principio **2.4 (Aislamiento de subsistemas)** del macroinforme **no se cumple hoy**: audio, Wi-Fi, relojes de CPU y display viven en el mismo fichero y comparten el mutex y el hilo de arranque con la GPU. Un rediseño de S7GPU debe **empezar sacando** esas partes, no reescribiendo la GPU.
**Boot-args que lee `herolte_gpu.c`** (15): `herogpu`, `herogpu_flush`, `herogpu_mhz`, `herogpu_pdcycle`, `herogpu_sleep_present`, `herogpu_sleep_us`, `herofb2`, `herodisp`, `heroaudio`, `herocpu_mhz`, `herohot`, `heropower`, `herotmu`, `herotwrp`, `herowifi`. El límite de la línea de arranque es 607 caracteres (la de la candidata N2 usa 166, E-0038).

## 2. Núcleo de GPU, en el orden en que se apilan (todos modifican el mismo fichero: la serie es **estrictamente secuencial**)
| Parche | Aporta (por nombre y comentarios leídos) | Estado inferido |
|---|---|---|
| 0225 `mali-t880-probe` | **crea `herolte_gpu.c`**: lectura de GPU_ID y registros de identificación, alimentación del dominio | vivo (`hg_probe`) |
| 0226 `first-job` | primer job (`WRITE_VALUE`) y su espera | vivo como autoprueba (`hg_job_write_value`) |
| 0227-0229 | fragment clear; descriptor MFBD multi-target de Midgard v5 (el A5/T720 usaba otro: 0227 recibió `DATA_INVALID_FAULT 0x58`); tiler desactivado | vivo (`hg_job_fragment*`) |
| 0230-0231 | panel entero; copia por GPU | vivo (`hg_gpu_copy_test`) |
| 0232-0234 | primer triángulo, alfa, quad texturizado | vivo (`hg_draw`; **diagnóstico**, no para clientes) |
| 0235 `gpu-present` | presentación: la GPU escala el cuadro de IOSurface al panel | vivo (`herolte_gpu_present_*`) |
| 0237 `xr-canvas-gpu-bars` | barras de GPU en un canvas XR | no leído; probablemente legacy |
| **0239 `herogpu-user-client`** | **crea `HeroGPU.cpp`** (cliente de usuario IOKit) y `herolte_gpu_up/va_alloc/map/unmap/submit` | vivo: es el ABI de S7GE_ABI.md |
| 0240 | zona DROP y `Log` de HeroGPU | vivo (selector 5) |
| 0243 `t880-quirks` | quirks de T880 r2p0 (`SC_LS_ALLOW_ATTR_TYPES`, `TC_CLOCK_GATE_OVERRIDE`, throttle del JM) | vivo (`hg_quirks`), **específico T880** |
| 0247 `job-barrier` | `dsb sy` antes de arrancar el job: sin él ~4 % de las cadenas de backboardd daban `JOB_READ_FAULT` | vivo |
| 0248 `surface-bo` | selector `SurfaceBO` (importa un IOSurface como BO) | vivo |
| 0249 `va-reuse-fault-recovery` | reutiliza VAs liberadas (rango compacto) y recupera tras fallo: `HARD_STOP` + reset | vivo |
| 0250 `as-once-clock-report` | AS0 se programa una vez (`hg_as_ok`), informe de reloj | vivo |
| 0256 `clock-boot-arg` | `herogpu_mhz` | vivo |
| 0258 `read-fault-recovery` | `JOB_READ_FAULT (0x42)` sin fallo de MMU: reset con retroceso | vivo |
| 0260 | servicio `IOAcceleratorES` vacío (`heroaccel`) | vivo |
| 0261 | log de voltaje G3D al salir | vivo |
| 0264-0267 | 419 MHz; ciclo del dominio de energía; bajar reloj ante fallos de lectura; tabla de fábrica y tensión (`vdd_g3d`, ASV 11) | vivo, **sin cierre**: los fallos de lectura no tienen causa raíz demostrada (§4) |
| 0273 | sonda tras un fallo de lectura duro (¿mala cadena o GPU "perdida"?) | vivo (`hg_read_fault_probe`) |
| 0286-0287 | cuanto de flush, informe de bus/vsync | no leído |
| **0307 `l3-pool-own-block`** | **arregla un fallo de tablas**: la 176.ª tabla L3 de usuario pisaba la tabla de nivel 0 de la GPU y todos los jobs daban fallo de lectura sin cura | vivo, **corrige un fallo real; revela que las tablas viven junto a datos** (ver S7GE_HARDWARE.md §3) |
| 0333-0334 (upstream) | esperar el job y el escalado **durmiendo** en lugar de girar en `delay(10)` | vivo |
Superficies (IOSurface): 0046 (`SweetSurface` crea `IOSurface` e IOMFB), 0068, 0244, 0252, 0254, 0255, 0259, 0317, 0332: **vivos**, tocan `SweetSurface.cpp`, no la GPU; encajan con S7IOS.
Userland GL: 0245, 0246, 0253, 0275, 0288, 0289, 0316, 0318, 0319, 0325 (`herolte_gl.c`: hakios-gl dentro de backboardd, AMFI, `heronoexec`): **vivos**, ruta actual de OpenGL ES sobre Mesa/Panfrost (S7GL).

## 3. API que el resto del kernel usa hoy de `herolte_gpu.c` (12 símbolos no estáticos)
`herolte_gpu_probe`, `herolte_gpu_up`, `herolte_gpu_reg` (lectura de registro, con filtro), `herolte_gpu_va_alloc`, `herolte_gpu_map`, `herolte_gpu_unmap`, `herolte_gpu_submit(js, jc, &µs)`, y la ruta de presentación `herolte_gpu_present_slot/map/draw`, `herolte_fb_two_buffers`, `herolte_fb_primary`. Consumidores: `HeroGPU.cpp` (clientes), `SweetFramebuffer.cpp` (presentación al panel). **Es la superficie mínima que un S7GPU nuevo tendría que ofrecer para sustituirlo sin tocar a los consumidores.**

## 4. Lo que NO está resuelto (hallazgos de hardware que arrastra la serie)
- **Fallos de lectura de job (`0x42`) sin fallo de MMU:** aparecen con **más de 1 GiB de RAM**, y por encima de la frecuencia del bootloader tras minutos (0258, 0264-0267, 0273); la escalera de recuperación es: reinicio suave → duro (desde el 2.º seguido) → ciclo del dominio de energía (4.º). **La causa raíz no consta** (las notas apuntan a que "la GPU pierde su camino a memoria"). Sin cierre, S7GE hereda un riesgo de estabilidad.
- **Tablas de página escribibles desde un job:** S7GE_HARDWARE.md §3 (lectura de código; no probado).
- **Sin interrupciones:** todo es sondeo.
- **Una sola AS0** y `AS_PRESENT` leído pero no usado.

## 5. Reutilizable y por reescribir
| Reutilizable (con pruebas de host o de GPU) | A reescribir / separar |
|---|---|
| Secuencia de encendido y quirks T880 (0225, 0243, 0249) | Todo lo que no es GPU (audio, Wi-Fi, relojes de CPU, display) → módulos aparte |
| Descriptores MFBD de Midgard v5 y los jobs de autoprueba (0227-0234) como **banco de pruebas** | El modelo "una AS, el cliente aporta la cadena de jobs" (ABI actual) |
| Escalera de recuperación y su telemetría (0249, 0258, 0265, 0273) | Las tablas de página junto a datos en el mismo bloque (0307 lo parchea, no lo resuelve) |
| `SweetSurface` / IOSurface (S7IOS) y la ruta de presentación | Sondeo → IRQ (tras auditar el mapa de interrupciones) |
| DVFS fijo por boot-arg con tabla de fábrica (0267) como punto de partida de S7DVFS | `hg_thread` y los hilos de estado compartidos |

## 6. No leído (para no afirmar de más)
Cuerpo de `hg_clock_set`, `hg_power_thread`, `hg_thread`, `hc_*` y los hilos de audio/Wi-Fi; los parches 0237, 0286, 0287 y las series de audio/Wi-Fi/display más allá del nombre; qué usa de verdad cada boot-arg en un arranque normal.

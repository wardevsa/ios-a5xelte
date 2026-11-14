# S7GE_EXECUTION_MODEL — cómo ejecuta hoy un job la Mali-T880 en este proyecto (Fase 1, 2026-11-14)

**Solo lectura y documentación.** Fuente: `bsd/dev/herolte_gpu.c` final (3 465 líneas) y `HeroGPU.cpp`, y los comentarios de los parches 0225-0334. Nivel **L1**: código leído y compilado en el CI; **L3h/L4h en el teléfono del upstream, nunca en esta unidad**. Las comparaciones con Panfrost/kbase son **conocimiento general, no verificado contra el código fuente de esta versión**: se marcan *(no verificado)*.

## 1. Mapa de hardware usado
| Bloque | Dirección física | Uso |
|---|---|---|
| GPU Mali (regs) | `0x14ac0000` (0x5000) | todo el control |
| PMU (dominio G3D) | `0x105c0000` (`G3D_CONF 0x4060`, `STAT 0x4064`, `AUX 0x6104`) | encender/apagar el dominio |
| CMU | `0x14aa0000` | PLL y mux del G3D (`G3D_PLL`, CMU_TOP/CMU_G3D) |
| Tablas de página (`hg_mem`) | `0x8ffc0000` (128 KiB) | L0..L3 de AS0 y tablas del panel/superficie |
| Bloque de trabajo (`hgp_scr`) | `0x8fe00000` (2 MiB) | jobs de presentación, L3 de ranuras, L2 de usuario |
| Pool L3 de usuario | `0x8fc00000` (512 tablas) | L3 de los BO de clientes |
| Framebuffer del panel | `0xe2a00000` | destino de la presentación |

## 2. Encendido y estado de reposo
1. `hg_bringup` comprueba que el dominio G3D está alimentado (`hg_powered`, PMU); si no, aborta.
2. Fija el reloj (`hg_clock_set`: PLL y voltaje; valor por defecto el del bootloader, o `herogpu_mhz=338..650`) y enciende **L2, todos los shader (`SHADER_PRESENT`, 12 núcleos) y tiler** con `*_PWRON` + espera a `*_READY` (≤ 20 ms, sondeo cada 10 µs). Los núcleos **quedan encendidos para siempre**: no hay apagado dinámico (el primer cliente enciende la GPU, `HeroGPU::initWithTask`).
3. Reaplica los quirks T880 (§6). Programa las tablas de página y AS0.
**Energía/DVFS hoy:** frecuencia **fija** por boot-arg; la tensión (`vdd_g3d`) se sube a la tabla de este teléfono (ASV grupo 11) antes de bloquear el PLL (0267). No hay DVFS dinámico, ni *runtime PM*, ni control térmico de la GPU (hilos térmicos de CPU aparte, 0330-0331).

## 3. Address space y PTEs
- **Una sola AS0**, programada una vez (`hg_as_ok`) y de nuevo tras recuperarse o reconstruir tablas: `AS0+0x00/0x04` transtab = `HG_TEST_PA | 0x7`; `AS0+0x08` memattr = `0x888d88`; `AS0+0x0c` = 0; `AS0+0x18` comando `UPDATE (1)`; espera a `AS0+0x28` bit 0 (`AS_STATUS`) a 0 (≤ 100 ms). Flush del MMU: `LOCK (2)` con `LOCKADDR` en `AS0+0x10/0x14` y `FLUSH_PT (4)`.
- **Tablas LPAE de Mali de 4 niveles**; entrada de tabla = `PA | 3`; hoja = `PA | 0x2c1` (lectura/escritura, *outer shareable*, no cacheable). **No hay PTE de solo lectura ni sin ejecución en ningún mapa.**
- **Mapa de VA de GPU** (único para todos): `0x02000000` pruebas · `0x04000000` panel · `0x06000000` segundo panel · `0x08000000` superficie importada (presentación) · `0x0a000000` bloque de trabajo (2 MiB, **contiene L2 de usuario y L3 de ranuras**) · `0x10000000..0x3fffffff` ranuras de presentación (4×8 MiB) · `0x40000000..0x7fffffff` **BO de clientes**.
- **Asignación de VA de usuario:** bitmap de trozos de 64 KiB (`HGU_CHUNK`), el más bajo libre primero (rango compacto); L3 de 4 KiB por cada 2 MiB; pool de 512 tablas (`HGU_L3_MAX`). `herolte_gpu_map/unmap` escriben/limpian PTEs y hacen flush bajo `hg_mtx`.
- **Defecto conocido:** hasta 0307 la 176.ª tabla L3 de usuario caía sobre la L0 de la GPU y todos los jobs daban fallo de lectura sin cura.

## 4. Envío y finalización de un job
`herolte_gpu_submit(js, jc_va, &µs)` → bajo `hg_mtx` → `hg_run`:
1. Si el slot sigue `ACTIVE (0x08)` en `JS_STATUS` lo anota ("slot busy"); limpia `JOB_IRQ_CLEAR` y `MMU_IRQ_CLEAR`.
2. Programa AS0 si hace falta (§3). **`dsb sy`** (0247: sin él ~4 % de las cadenas daban `JOB_READ_FAULT`).
3. Slot `JS_BASE(n) = 0x1800 + n·0x80`: `HEAD_NEXT` (`+0x40/0x44`) = VA de la cadena; `AFFINITY_NEXT` (`+0x50`) = `hg_affinity` (por defecto 1: un núcleo); `CONFIG_NEXT` (`+0x58`) = `(8<<16) | flush_start | flush_end` (limpieza de caché de la GPU según `herogpu_flush`); `COMMAND_NEXT (+0x60) = START`.
4. **Espera por sondeo** de `JOB_IRQ_RAWSTAT`, `MMU_IRQ_RAWSTAT` y `GPU_IRQ_RAWSTAT`: 20 000 vueltas × 10 µs ≈ 200 ms (o durmiendo en trozos, 0333, solo para clientes IOKit). **No hay interrupciones**, ni fences, ni cola: **un job a la vez, síncrono, serializado con `hg_mtx`.**
5. Éxito = bit `1<<js` en `JOB_IRQ` sin su bit de fallo `1<<(js+16)`, sin IRQ de MMU y sin `GPU_IRQ & 0x81`. Salida: `JS_STATUS` crudo (`0` limpio; `0x42` read fault; `0x58` data invalid) y microsegundos.
6. Si falla: `hg_recover` (§5).
**Tipos de job vistos en el código:** `WRITE_VALUE`, *fragment* (MFBD multi-target de Midgard v5: Local Storage +0/32 B, Parameters +32/24 B, Tiler Context +56/40 B, Tiler Weights +96/32 B, Render Target +128/64 B) y *vertex/tiler* (`hg_draw`, diagnóstico). Los clientes (Mesa/Panfrost en userland) escriben **sus propias cadenas** (descriptores) en BO mapeados.

## 5. Recuperación
`hg_recover`: `HARD_STOP (3)` en los slots 0 y 1 si siguen activos; limpia IRQs; marca AS0 a reprogramar; si es `0x42` cuenta el fallo y: reinicio **suave** (`GPU_COMMAND 1`) los dos primeros, **duro (2)** desde el 2.º seguido, **ciclo del dominio de energía completo** en el 4.º (`hg_power_cycle`, restaura CMU_G3D); espera `RESET_COMPLETED` (`GPU_IRQ bit 0x100`, ≤ 100 ms), vuelve a encender núcleos, reaplica quirks y, hasta 6 veces, ejecuta la sonda del 0273. Con retroceso (`<=16` o cada 64.º) para no estancar todo. **La causa de fondo de los `0x42` no está demostrada.**

## 6. Diferencias T880 frente a T720 que constan en los parches
| Dónde | Hecho | Fuente |
|---|---|---|
| Descriptor de framebuffer | El del A5 (T720) con un solo render target da `DATA_INVALID_FAULT 0x58` en T880; el que funciona es el MFBD multi-target v5 de Mesa | 0227 |
| Quirks de `panfrost_gpu_init_quirks` para T880 r2p0 | `SHADER_CONFIG(0xf04) \|= 1<<16` (`SC_LS_ALLOW_ATTR_TYPES`: sin él todo vertex job de Mesa da `0x58`), `TILER_CONFIG(0xf08) \|= 1` (`TC_CLOCK_GATE_OVERRIDE`, "T76X_3953"), `JM_CONFIG(0xf00) = 0x3f<<3` (throttle); **un reset suave los borra** | 0243 (`hg_quirks`) |
| Núcleos | MP12: 12 shader; la A5XELTE es T720 (otro `GPU_ID`; el número de núcleos no consta en el PC) | S7GE_ARCHITECTURE §4.2 |
| Energía | Hay que tener el dominio G3D encendido en la PMU de Exynos 8890 y bloquear `G3D_PLL`; el rango de 88-650 MHz de Samsung exige subir la tensión con el reloj | 0264-0267 |
La lista oficial de erratas T880 r2p0 **no está** en el PC (S7GE_HARDWARE.md §4).

## 7. Comparación con Panfrost/kbase *(no verificado contra fuente)*
Panfrost/kbase usan IRQ de job/MMU/GPU, **un espacio de direcciones por contexto**, planificador con *fences* (drm_sched / dma-fence), gestión de energía con *runtime PM* y DVFS por *devfreq*, y validan o aíslan los BO por contexto. Este proyecto hoy: sondeo, AS0 única, cola de uno, frecuencia fija, el cliente aporta la cadena. Brechas ya recogidas en S7GE_ABI.md §4.

## 8. Lo no leído
`hg_clock_set` y `hc_*` en detalle, `hg_power_thread`, los hilos de audio/Wi-Fi/display, y qué hace `hg_bringup` con `AS_PRESENT`; ningún registro se ha medido en el teléfono de esta unidad.

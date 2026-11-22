# S7GE_EXTRACTION_INTERFACES — contratos para sacar los subsistemas de `herolte_gpu.c` (Fase 7, 2026-11-14)

**Diseño; no se ha movido código.** Desarrolla `S7GE_SPLIT_PLAN.md`. Orden fijado por la jefatura: **audio → Wi-Fi → relojes de CPU → display** (el display espera a S7PRES). Nivel **B** (cambia la serie de parches): nada de esto se implementa sin su revisión. Las firmas salen de los símbolos que el fichero ya usa o exporta (leídos en el fichero final).

## 1. Cabecera común `herolte_mmio.h` (primer paso, sin cambio de comportamiento)
`static inline` de las cuatro ayudantes de las que dependen todos los grupos no-GPU: `uint32_t hg_rd(vm_offset_t base, uint32_t off)`, `void hg_wr(vm_offset_t base, uint32_t off, uint32_t v)` (**con las barreras `dmb oshst`/`dsb osh`** del original: no pueden perderse), `void hg_msleep(unsigned ms)`, `void hg_usleep(unsigned us)`. Se renombran `herolte_rd/wr/msleep/usleep` en la cabecera y se dejan alias `hg_*` temporales para que el diff sea mínimo.
**Prueba de equivalencia:** compilar antes y después y comparar los **símbolos exportados** y el ensamblador de `hg_wr` (mismas barreras).

## 2. Audio (`herolte_audio.c`)
| Contrato | Valor |
|---|---|
| Se lleva | `ha_*` (18 funciones), `hg_audio_thread`, estáticos `ha_cdevsw/ha_i2c/ha_i2s/ha_ring/ha_serve/ha_wdt`, `/dev/hakios-audio` (parches 0301-0303) |
| Función pública | `void herolte_audio_start(int mode)` (solo la llama el probe si `heroaudio` ≠ 0) |
| Boot-args propios | `heroaudio` |
| Depende de | `herolte_mmio.h`; externos ya existentes: `herolte_apm_pmic_write` (PMIC LDO31, escribe `0x5b`), `kernel_thread_start_priority` |
| No toca | ninguna variable de GPU |
| Cuidado | escribe PMIC, pines y SPI: **no cambiar el orden de pasos** (0278-0283, 0300) |

## 3. Wi-Fi (`herolte_wifi.c`, ya existente)
| Contrato | Valor |
|---|---|
| Se lleva | `hw_*` (7 funciones), `hg_wifi_thread`, `hw_step` |
| Función pública | `void herolte_wifi_start(void)` (la llama el probe si `herowifi` ≠ 0) |
| Boot-args propios | `herowifi` |
| Ya exporta | `herolte_wifi_firmware(vm_offset_t cfg)`, `herolte_wifi_files_ready(void)` (las usa el hilo): **se conservan con el mismo nombre** |
| Depende de | `herolte_mmio.h`; zona DROP (`herolte_drop.c` instala el firmware antes de `launchd`) |
| Cuidado | el hilo espera hasta 120 s al firmware; mapea 10 regiones MMIO (`pins`, `cmu`, `pmu`, `elbi`, `phy`, `sys`, `dbi`, `pcs`, `cfg`, `top`); `herowifi=0` debe seguir evitando **todo** (incluidos los mapeos) |

## 4. Relojes de CPU y energía (`herolte_cpuclk.c`, `herolte_power.c`)
| Contrato | Valor |
|---|---|
| Se llevan | `hc_*` (7), `hg_cpu_up`, `hg_power_thread`, estado `hc`, tabla `hp_tmu_pa`, `hp_boot_mhz` |
| Funciones públicas | `void herolte_cpu_up(void)` (hoy `hg_cpu_up`: **no hace nada sin `herocpu_mhz`**), `void herolte_power_start(void)` (hilo; `heropower`, `herohot`, `herotmu`) |
| Externos que usa | `herolte_apm_mngs_voltage`, `herolte_apm_pmic_read/write`, `herolte_screen_off_at` y `herolte_fg_temp_dc` (de `herolte_battery.c`), `thread_bind`, `cpu_to_processor` |
| Orden | `herolte_cpu_up()` se llama desde el hilo principal (`hg_thread`, 30 veces cada 1 s) **y** el hilo de energía espera `hc.saved` hasta 300 s: la separación no debe cambiar ese acoplamiento |
| Cuidado | **cambia tensión y frecuencia** del Mongoose solo con `herocpu_mhz`; la extracción no puede cambiar el valor por defecto (no hacer nada) |

## 5. Sistema (`herolte_sysmon.c`)
`hg_pmic_dump`/PMIC, `hg_twrp_thread` (`herotwrp`: escribe `INFORM2` del PMU para volver a recuperación; **no tocar sin razón**), el hilo principal de medición (`hg_thread`, parte de CPU) y, si procede, el hilo de bus. Función pública: `void herolte_sysmon_start(void)`. `hg_thread` hoy mezcla medición de CPU y arranque de la GPU (`hg_probe`, `hg_jobs`): se **parte en dos** (medición de CPU a sysmon; `hg_probe/hg_jobs` se quedan en GPU).

## 6. Display (`herolte_display.c`): espera a S7PRES
`hfb_*` (IDMA/DECON, doble búfer), `hg_decon_measure`, `hg_bus_thread`. **No se extrae** hasta definir S7PRES porque `hfb_idma`, `hfb_state`, `hfb_flips` y `hgp_scr` los comparte la presentación por GPU (`herolte_gpu_present_*`). Interfaz tentativa: `bool herolte_present_frame(const struct present_req *)` con la cola de cuadros dentro de display y la GPU solo dibujando una superficie.

## 7. `herolte_platform_probe()` (sustituye a `herolte_gpu_probe`)
Conserva el **símbolo** `herolte_gpu_probe` (lo llama `IOKitBSDInit.cpp`) como envoltorio y arranca los módulos **en el mismo orden actual**: lectura de `herogpu_flush/sleep_us/sleep_present` → Wi-Fi → bus → TWRP → audio → energía → `herogpu`. **El orden de arranque de los hilos no puede cambiar** (nivel B: lo revisa la jefatura).

## 8. Criterio de aceptación común
Para cada paso: (1) el kernel compila en el CI con los **mismos símbolos exportados** que antes; (2) el árbol resultante de **aplicar la serie nueva sobre la base** es idéntico (byte a byte) al de la serie antigua salvo el reparto en ficheros (con tolerancia explícita solo para los movimientos); (3) un arranque de la variante mínima **da la misma salida** de consola; (4) el diff del paso es **solo movimiento**.

# S7GE_SPLIT_PLAN — cómo sacar de `herolte_gpu.c` lo que no es GPU (Fase 4, 2026-11-14)

**Solo análisis y propuesta; no se ha movido ni cambiado nada.** Dividir el fichero es un **cambio de la serie de parches** (nivel B, revisión de la jefatura); además cambiaría el contenido del kernel, así que obligaría a recompilar en el CI y a reconstruir y reverificar la candidata. Fuente: `bsd/dev/herolte_gpu.c` final (3 466 líneas, la del kernel del CI, E-0037). Los números salen de un barrido automático de definiciones de función y de referencias a identificadores; **no he compilado la división**.

## 1. Mapa medido
| Grupo | Funciones (primera → última línea) | Líneas | Ficheros propuestos |
|---|---|---|---|
| **GPU** | 52 funciones, 68 → 3 467 (repartidas) | 1 960 | `herolte_gpu.c` (queda) |
| audio | 18, 2 598 → 3 071 | 457 | `herolte_audio.c` |
| Wi-Fi | 7, 3 215 → 3 420 | 200 | `herolte_wifi.c` (ya existe, creado por 0308, con `herolte_wifi_firmware`; el resto debería ir ahí) |
| relojes de CPU | 7, 2 200 → 2 410 | 205 | `herolte_cpuclk.c` |
| hilo de energía/térmica | 1, 2 419 → 2 509 | 91 | `herolte_power.c` |
| hilo principal de medición | 1, 2 511 → 2 596 | 86 | junto a `herolte_cpuclk.c` o `herolte_sysmon.c` |
| PMIC (volcado) | 2, 168 → 2 417 | 96 | `herolte_sysmon.c` |
| bus/vsync | 1, 3 099 → 3 191 | 93 | `herolte_display.c` |
| `herolte_gpu_probe` | 3 422 → 3 466 | 45 | queda como `herolte_platform_probe()` que llama a cada módulo |
| TWRP temporizado | 1, 3 193 → 3 213 | 21 | `herolte_sysmon.c` |
| display (DECON) | 4, 1 709 → 3 097 | 98 | `herolte_display.c` |

## 2. Acoplamiento real (lo que hace fácil o difícil cada extracción)
- **Todos los grupos no-GPU dependen de un conjunto diminuto de ayudantes:** `hg_rd`, `hg_wr` (lecturas/escrituras MMIO con barreras), `hg_msleep`, `hg_usleep`. Se resuelve con una cabecera `herolte_mmio.h` (4 funciones `static inline`). **Cero dependencias de variables de estado de la GPU.**
- **Audio y Wi-Fi son autocontenidos:** sus estáticos (`ha_cdevsw`, `ha_i2c`, `ha_i2s`, `ha_ring`, `ha_serve`, `ha_wdt`) solo los usa el propio audio. **Son la extracción más barata y de menor riesgo.**
- **Relojes de CPU / energía:** `hc_*`, `hg_cpu_up`, `hg_power_thread` se llaman entre sí y con `hg_thread`; comparten el estado `hc` y `hp_tmu_pa`. Un módulo `cpuclk` con una función `herolte_cpu_up()` y otra `herolte_power_start()` basta.
- **Display ↔ presentación de la GPU: acoplamiento real.** Las variables `hfb_idma`, `hfb_state`, `hfb_flips` y `hgp_scr` las usan **a la vez** la presentación por GPU (`herolte_gpu_present_*`, `herolte_fb_two_buffers`) y el display. La frontera correcta es la del macroinforme (S7PRES): la **presentación** (cola de cuadros, IDMA, doble búfer) es de display; la GPU solo recibe "dibuja esta superficie en este destino". Hasta definir S7PRES, esa pieza se **queda** donde está.
- **Variables de la GPU:** 29 estáticos (`hg_*`, `hgp_*`, `hgu_*`) usados solo por la propia GPU: la parte GPU puede quedarse en el fichero sin tocar su estado.
- **Hilos arrancados por `herolte_gpu_probe`:** se crean aunque `herogpu=0` (Wi-Fi, bus, TWRP, audio, energía); solo `hg_thread` (medición y pruebas de GPU) depende de `herogpu`.

## 3. Qué hace por defecto el kernel al arrancar (importa para N2)
Hechos leídos en `herolte_gpu_probe` y los hilos, **sin boot-args extra** (la línea de N2 solo trae `ufsrw=0 herolog=0 herodrop=0` y los de depuración):
| Hilo | ¿Arranca? | Qué escribe/lee según lo leído |
|---|---|---|
| `hg_wifi_thread` | **sí** (`herowifi` por defecto 1) | espera hasta 120 s a que la zona DROP instale el firmware; **después escribe**: pines GPIO (WLAN_EN, PERST, CLKREQ de `gpj1`), una puerta de reloj de CMU (`fsys1`), registros del PMU (`+0x71c`) y el PHY/PCIe del chip (`hw_step`…); **no leído entero**. Es decir: en un N2 sin `herowifi=0` **se enciende el Wi-Fi y el enlace PCIe** |
| `hg_bus_thread` | **sí**, siempre | mide DECON/vsync y, según `herodisp` (por defecto no está claro: **no leído**), puede **cambiar el mux del reloj del display** (`vclk on DISP_PLL`: escribe `CMU_DISP+0x200` bit 12) |
| `hg_power_thread` | **sí** (`heropower` por defecto 1) | lee los 4 TMU y registra temperaturas; solo toca la frecuencia del Mongoose **si `herocpu_mhz` está puesto** (por defecto `hc.saved` es falso, imprime "left as it is" a los 300 s y termina) |
| `hg_thread` (GPU/medición) | **sí** (`herogpu` por defecto 1) | **mide** CPU con un bucle y lee PMIC `0x26/0x1d/0x1f` (lectura); `hg_cpu_up()` **no actúa** sin `herocpu_mhz`; con `herogpu` ≥ 2/3 hace volcados y jobs |
| `hg_audio_thread` | solo con `heroaudio` | escribe PMIC `0x5b` (LDO31), pines y SPI |
| `hg_twrp_thread` | solo con `herotwrp` | vuelta temporizada a recuperación |
**Conclusión:** la candidata N2 es **de solo lectura para el almacenamiento** (UFS), que es lo que `n2-readonly` verifica; **no** es "de solo lectura para el hardware": Wi-Fi arranca por defecto y **escribe GPIO, puertas de reloj, PMU y PCIe**, y el hilo de bus puede tocar un mux de reloj del display. **No he encontrado** escrituras de tensión ni de frecuencia de CPU en la configuración por defecto (`herocpu_mhz` no está puesto), pero Wi-Fi y bus **no están leídos a fondo** y todo esto está probado solo en el teléfono del upstream, no en esta unidad.
**Opción de menor huella para un primer arranque** (decisión del Director/jefatura, no la tomo yo): añadir `herowifi=0 heropower=0 herogpu=0` (la línea pasaría de 166 a unos 190 de 607 caracteres). Cambia el hash de la candidata: habría que reconstruirla y reverificarla (el constructor y el verificador ya existen; el perfil `n2-readonly` debe confirmar que acepta los argumentos extra). Contrapartida: se pierde información de arranque (no hay medición ni logs de GPU/energía en ese primer intento).

## 4. Orden de extracción propuesto (cuando se autorice implementar)
1. `herolte_mmio.h` con `hg_rd/hg_wr/hg_msleep/hg_usleep` (sin cambiar comportamiento). 2. **Audio** a `herolte_audio.c` (autocontenido). 3. **Wi-Fi** hacia `herolte_wifi.c`. 4. **Relojes de CPU y energía** a `herolte_cpuclk.c` + `herolte_power.c`. 5. PMIC/TWRP/bus a `herolte_sysmon.c`. 6. **Display/presentación**: solo después de definir S7PRES. 7. `herolte_platform_probe()`. Cada paso es **un parche nuevo** que mueve código sin cambiarlo (con prueba de equivalencia: el kernel resultante debe dar los mismos símbolos exportados y el mismo comportamiento de arranque en el log).
**Riesgos:** (a) los parches siguientes de la serie que tocan `herolte_gpu.c` (0225-0334) **se aplican sobre el fichero entero**: mover código exige o bien un único parche de reorganización al final (los parches antiguos siguen aplicando), o bien reescribir la historia (no recomendado, rompe la trazabilidad con upstream); recomiendo **un parche de reorganización posterior** (p. ej. `0400-…`, rango de D-0007). (b) `files.arm64` debe listar los ficheros nuevos. (c) El orden de arranque de los hilos no debe cambiar.

## 5. Lo que NO se hizo
No se compiló ninguna división; no se leyó a fondo `hg_wifi_thread`, `hg_bus_thread` ni los cuerpos de `hc_*`; no se probó nada en el teléfono.

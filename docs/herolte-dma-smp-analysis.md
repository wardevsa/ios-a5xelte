# HEROLTE: coherencia DMA del UFS y arranque SMP — análisis de solo lectura

Estado: análisis de código y del kernel ya compilado. **No se ha tocado el dispositivo.** Todo lo marcado "pendiente de
dispositivo" necesita la autorización del responsable. Kernel analizado: `xnu/out-drop-fixes/kernel.development.herolte`
(SHA-256 `e57f05be…`, compilación local del 2026-11-11).

Clasificación: **A** demostrado por el código o por el binario · **B** respaldado por evidencia de dispositivo ya
registrada en `HEROLTE_PROGRESS.md`, pero indirecta · **C** no demostrable con lo disponible.

## 1. Mantenimiento de caché del DMA del UFS

| Afirmación | Clase | Base |
|---|---|---|
| El mantenimiento de caché del DMA es **real**, no un no-op | A | `__ARM_COHERENT_IO__` (`caches.c:56,383`) y `APPLE_ARM64_ARCH_FAMILY` (`caches_asm.s`) solo los define `pexpert/arm64/apple_arm64_common.h:36,46`; el `A5XELTE.h` de HEROLTE (0085) no lo incluye. En el binario: `flush_dcache → phystokv_range → FlushPoC_DcacheRegion` ejecuta `dc civac` con paso de 64 B (`mov x9,#0x3f`, `lsr #6`, `add #0x40`); `CleanPoC_DcacheRegion_internal` usa `dc cvac` |
| `MMU_CLINE = 6` (64 B) es correcto para la caché de **datos** | A/B | Definido por la rama `SWEET` de `proc_reg.h` (0004). Un Mongoose real informa `CTR_EL0 = 0x84448005` (`HEROLTE_PROGRESS.md`): DminLine=4 → 64 B, CWG=4 → 64 B. El valor del A53 no está registrado (B) |
| La caché de **instrucciones** del Mongoose es de 128 B, y la config usa 64 B (`MMU_I_CLINE=6`) | A | IminLine=5 en ese mismo CTR. Operar con paso de 64 B sobre líneas de 128 B sobreinvalida, no deja nada sin invalidar |
| Modo por defecto del driver: flush (`DC CIVAC`) antes **y** después de cada DMA | A | `ufscache` no está en ninguna línea de arranque documentada (README, `HEROLTE_PROGRESS.md`); `dma_sync()` = `flush_dcache64`, `0204:150-158,203-265` |
| Ninguna línea de caché mezcla datos escritos por la CPU y por el dispositivo | A | Disposición `0204:96-114` (estructuras y `DMA_*`): UTRL +0x0000 (UTRD de 32 B, solo la ranura 0), UCD +0x1000 (`cmd[512]`, `resp[512]`, PRDT 4096: todo múltiplo de 64), bounce +0x4000 (1 MiB) |
| Orden: `dsb sy` tras preparar y antes del *doorbell* | A | `0204` (`__builtin_arm_dsb(0xf)`, `0204:222,255`) y `dsb sy` al final de `FlushPoC_DcacheRegion` |
| Direccionamiento de 64 bits disponible si el buffer cae sobre 4 GiB | B | `cap 0x383ff0f` (`HEROLTE_PROGRESS.md:76`): bit 24 (`64AS`) activo; el driver además rechaza ese caso si no lo tuviera (`0204:417`) |
| Lecturas y escrituras por DMA funcionan en el teléfono | B | GPT, montaje HFS, root de iOS 16 hasta `Early boot complete`, log persistente (0206) |
| Que lo anterior implique **coherencia** en todos los casos | C | No hay prueba de integridad bajo carga (lectura-comparación con 8 CPU) registrada, ni a favor ni en contra |
| Si el controlador UFS del Exynos 8890 es coherente (ACE-lite/CCI) o no | C | Irrelevante para la corrección con mantenimiento explícito, pero no está documentado |
| Qué ocurre con el DMA tras `ETIMEDOUT` | C | `ufs_scsi` escribe `UTRLCLR` y vuelve sin esperar ni reiniciar el controlador (`0204:227-242`); un volcado tardío podría pisar el comando siguiente |

**Conclusión DMA:** con la configuración actual el mantenimiento de caché es real y el driver sigue el patrón correcto
(limpiar+invalidar antes, invalidar después). El diagnóstico "no hay base para declarar seguro el camino DMA" sigue
siendo válido solo en el sentido de **falta de pruebas de integridad bajo carga**, no por una carencia visible en el código.

## 2. Orden de aplicación de parches (CI)

A. `build.sh` de darwin-xnu-build (commit fijado en `.github/workflows/xnu.yml`; el bucle está en las líneas 466-479 de ese `build.sh`): ejecuta primero `patches/*.sh` y luego
`patches/*.patch` en orden alfabético del *glob*. **Si `git apply --check` falla, solo avisa ("Skipping patch") y sigue.**
El paso de anotaciones de `xnu.yml` filtra esas líneas. Un parche roto no hace fallar la compilación.

## 3. Arranque de los ocho núcleos

| Afirmación | Clase | Base |
|---|---|---|
| Topología lógica: 0–3 = A53 (MPIDR `0x100..0x103`), 4–7 = Mongoose (`0x0..0x3`); límite 8 | A | `0218`, `mkadt_herolte.py`; `0208` fijaba 4 y `0218` lo sube a 8 |
| Antes de `CPU_ON`, el arrancador limpia hasta el PoC lo que lee el secundario con MMU y cachés apagadas | A | `0065:257-264`: `CleanPoC_DcacheRegion_Force` de `CpuDataEntries`, `cpu_data`, `ResetHandlerData`, `BootArgs`, `sysreg_restore`, `cpu_ttep`, `bootstrap_pagetables` + `dsb` |
| Un secundario que no llega provoca pánico con diagnóstico, no un cuelgue silencioso | A | `0065:136-143` (*timeout* de arranque) |
| **8/8 CPUs inicializadas en el dispositivo** | B | `HEROLTE_PROGRESS.md:235-239`: `8/8 CPUs initialized`; `0219`: contador común, retraso < 1 ms, temporizadores que despiertan en los 8 (21 ms sobre 20); Mongoose `MIDR 0x531f0011` |
| Una entrada de `CPU_ON` sobre 4 GiB no llega (CPU_ON devuelve 0) y 0223 lo rodea con un trampolín en `0x8fffe000` | B | `0223`, `HEROLTE_PROGRESS.md:259-261`; el trampolín se escribe vía `ml_io_map` (memoria de dispositivo, sin caché) |
| Coherencia entre los dos clústeres para las CPU | B | Un kernel SMP con atómicas sobre memoria cacheable entre clústeres solo funciona con coherencia por hardware; el sistema corre con 8 núcleos. Es una inferencia, no una medición |
| Estabilidad de larga duración con 8 núcleos | C | Sin registro de pruebas de resistencia |
| La página `0x8fffe000` no tiene alias cacheable en la memoria gestionada por XNU | C | Mezclar atributos sobre la misma página es indefinido en ARM; comprobar el mapa de memoria del ADT |

Corrección a un análisis previo: la lectura "el arranque efectivo de los ocho núcleos no está demostrado" se basaba solo en
el código. La evidencia de dispositivo ya registrada lo cubre (clase B).

## 4. Pruebas de dispositivo propuestas (NO realizadas; requieren la autorización del responsable)
1. Lectura-comparación del UFS bajo carga con 8 CPU y con `ufscache` por defecto (sin escribir particiones).
2. Registrar `CTR_EL0` y `MIDR_EL1` del A53 (el registro actual solo tiene los del Mongoose).
3. Comprobar en el ADT que `0x8fffe000` queda fuera de la memoria gestionada por XNU.
4. Medir si el UFS devuelve `ETIMEDOUT` alguna vez en el log persistente (buscar `HEROLTE UFS: command ... timed out`).

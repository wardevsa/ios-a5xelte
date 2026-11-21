# S7GE_HARDWARE — mapa de la GPU y auditoría de AS0 (T-0010, 2026-11-13)

**Informe de solo lectura; no cambia código ni toca el teléfono.** Nivel de evidencia: **L1** (código del árbol XNU parcheado hasta nuestro `0332` leído en este PC; el árbol está en el kit `buildtree-0332-fork-8d1cf43`, caduca el 2026-11-18). **Nada se ha probado en esta unidad** (sin L3/L4). Todo lo marcado "no verificado" necesita la plataforma real o documentación que no está en el PC.

## 1. Mapa físico y de registros (lo que el código usa)
| Elemento | Valor | Fuente (`bsd/dev/herolte_gpu.c`) |
|---|---|---|
| GPU (Mali-T880 MP12, regs) | PA `0x14ac0000`, 0x5000 bytes mapeados | `HG_GPU_PA` (l.46) |
| PMU / G3D | PA `0x105c0000`; conf `0x4060`, estado `0x4064` | l.41-44 |
| CMU | PA `0x14aa0000` (solo lectura del reloj) | l.45 |
| Registros GPU usados | `GPU_IRQ_RAWSTAT 0x020`, `GPU_COMMAND 0x030`, `AS_PRESENT 0x018`, `JOB_IRQ_RAWSTAT/CLEAR 0x1000/0x1004`, `MMU_IRQ_RAWSTAT/CLEAR 0x2000/0x2004`, `AS0` (transtab `+0x00`, memattr `+0x08`, lockaddr `+0x10`, command `+0x18`, status `+0x28`, transcfg `+0x30`), quirks `0xf00/0xf04/0xf08` | l.54-56, 249-253, 378-386 |
| Memoria de tablas de página (`hg_mem`) | PA `0x8ffc0000`, 0x20000 bytes | `HG_TEST_PA/BYTES` (l.212-213) |
| Bloque de trabajo (`hgp_scr`) | PA `0x8fe00000`, **2 MiB** | `HG_SCR_PA/BYTES` (l.1010-1011) |
| Pool de tablas L3 de usuario | PA `0x8fc00000`, 512 tablas | `HGU_POOL_PA` (l.1451) |
| Framebuffer del panel | PA `0xe2a00000` (1440×2560×4) | `HG_FB_PA` (l.235) |
| Transtab de AS0 | `HG_TEST_PA \| 0x7`; memattr `0x888d88`; formato LPAE de Mali | `hg_run` (l.750-757) |

## 2. AS0: qué hay mapeado hoy (la única address space)
`hg_bringup` documenta "one address space for everything". Mapa de **VA de GPU en AS0**:
| VA de GPU | Qué es | Acceso del job | Fuente |
|---|---|---|---|
| `0x02000000` | 12 páginas de datos de prueba (`hg_mem`+`0x4000`) | RW | `hg_tables`, l.327-330 |
| `0x04000000` | **framebuffer físico del panel** `0xe2a00000` (14,7 MB) | RW | l.331-340 |
| `0x06000000` | segundo búfer del panel (FB2) | RW | l.1700-1771 |
| `0x08000000` | páginas de una superficie IOSurface importada (presentación) | RW | l.341-349 |
| `0x0a000000` | **bloque de trabajo completo (2 MiB)**: 512 PTE a `HG_SCR_PA` | **RW** | l.1504-1514 |
| `0x10000000..0x3fffffff` | ranuras de presentación (4 × 8 MiB) | RW | `HGP_VA_*` |
| `0x40000000..0x7fffffff` | **búferes de usuario** (los BO de HeroGPU) | RW | `HGU_VA_*` |
Las PTE se escriben con `0x2c1` (lectura/escritura, *outer shareable*, no cacheable): **ninguna entrada es de solo lectura ni sin ejecución** y **no hay ningún campo por cliente**.

## 3. Hallazgo principal (código leído, **no probado**): las tablas de página de AS0 son escribibles desde un job
El bloque de trabajo de 2 MiB está **entero** mapeado RW en la VA `0x0a000000` y contiene, **dentro de ese mismo bloque**:
- la **tabla L2 de los búferes de usuario** (`HGU_L2_OFF = 0x110000`, l.1451/1516-1517);
- las **tablas L3 de las ranuras de presentación** (`HGP_L3_OFF = 0x100000`);
- las **tablas L3 del FB2** (`HGP_FB2_L3_OFF = 0x120000`).
`Submit` acepta una `jc_va` y una cadena de jobs construidas por el cliente (S7GE_ABI.md §2, selector 4), y un job de sombreado puede **escribir en cualquier VA mapeada**. Por tanto un cliente podría, en principio, escribir en `0x0a110000…` (su propia L2) y **hacer que cualquier VA de GPU apunte a cualquier dirección física**, con lo que leería y escribiría **memoria física arbitraria del kernel** sin pasar por ninguna comprobación de CPU. Mitigaciones que **no** he encontrado en lo leído: separación por cliente, PTE solo lectura para el bloque de tablas, validación de la cadena de jobs.
**Atenuantes y límites de esta conclusión:** (a) **no verificado en hardware**; (b) no comprobé si el SysMMU de Exynos (si existiera delante del G3D) restringe las direcciones físicas alcanzables — **no hay evidencia en el código de que se programe**; (c) el *pool* de tablas L3 de usuario (`0x8fc00000`) **no** aparece mapeado en AS0 en lo leído (solo se accede por la dirección virtual del kernel `hgu_pool`), así que los L3 de los BO de usuario no serían escribibles directamente, pero **sí la L2 que los referencia**; (d) esto requiere ejecutar software que envíe jobs arbitrarios: hoy solo lo hace el software del propio proyecto, y depende del perfil de sandbox de iOS (no verificado).
**Consecuencia (propuesta, no aplicada):** esto agrava **D-0015** (aislamiento de clientes): además de AS por cliente, hay que **sacar las tablas de página del bloque mapeado** (o mapearlas solo lectura) y **validar la cadena de jobs** antes de que `Submit` se considere una frontera de seguridad. Hasta entonces, la GPU no debe usarse con software no confiable. Cambio de nivel B (revisor: jefe técnico).

## 4. Checklist de la auditoría Panfrost del upstream (A5XELTE, T720) aplicado a T880
La lista viene de `S7GE_STATUS.md` (§ upstream; **es específica de T720**: sirve para saber qué mirar, no para copiar correcciones). Estado en `herolte_gpu.c`:
| Punto | Estado en herolte (T880) | Marca | Referencia |
|---|---|---|---|
| Reset conocido de GPU antes de usarla | `hg_recover` hace `GPU_COMMAND` 1 (soft) o 2 (hard, tras ≥2 fallos de lectura) y espera `RESET_COMPLETED` (bit `0x100` de `GPU_IRQ_RAWSTAT`, hasta 10000 sondeos) | **leído**; efectividad **no verificada** | l.678-721 |
| Quirks tras reset | `hg_quirks` reaplica `0xf04` (SC_LS_ALLOW_ATTR_TYPES), `0xf08` (TC_CLOCK_GATE_OVERRIDE), `0xf00` (throttle); el comentario dice que un soft reset los borra | **leído**; ¿se llaman tras *cada* `hg_recover`? **no verificado** | l.378-386 |
| IRQ crudas frente a enmascaradas | **No hay IRQ**: todo es sondeo de `*_IRQ_RAWSTAT` y `CLEAR` | **verificado en código** (no usa interrupciones) | l.787-789 |
| Teardown/limpieza de AS | Se hace `UPDATE` una vez (`hg_as_ok`); tras `hg_tables`/recuperación se reprograma; **no se desmonta AS0** | **leído**; sin equivalente del teardown de AS1 | l.757-763 |
| `START_MMU` (errata 10649, T720) | No aplicable por nombre; la secuencia usa `AS_COMMAND_UPDATE` (1) y flush (`LOCK` 2, `FLUSH_PT` 4) | **no verificado para T880 r2p0** (falta la lista de erratas oficial) | l.757, 1425-1433 |
| `GPU_SHADER_CONFIG` | Se toca `0xf04` (SHADER_CONFIG) con el bit 16; el resto del registro no se inicializa | **leído**; valor completo y errata **no verificados** | l.384 |
| `AS_PRESENT` | Se **lee y se imprime** (l.153) pero nunca se usa para decidir; el código usa solo AS0 | **leído**; cuántas AS hay realmente en esta unidad: **no verificado** (necesita el log del teléfono) | l.153 |
| Fallos de MMU/job: lectura de causa | `hg_run` lee `AS0+0x1c/0x20` y `JS_STATUS`; `Submit` devuelve el estado crudo | **leído** | l.819, S7GE_ABI.md |
| Erratas oficiales de T880 r2p0 | **No tengo la lista** (ARM no la publica abierta; Mesa/Linux nombran `HW_ISSUE_*` por versión) | **no verificado**; a completar con la tabla de `panfrost`/`kbase` de la versión exacta | — |
| Identificación (`GPU_ID`, `*_PRESENT`) | Se leen vía `GetParam` | **leído** | S7GE_ABI.md |

## 5. Propuesta de nodo de GPU en el ADT (solo documento; no implementado)
Hoy `HeroGPU::start` publica a mano `GPU = "Mali-T880 MP12"`; no hay nodo en el árbol de dispositivos. Propuesta mínima (a revisar por el jefe técnico, `architecture-change`, nivel B):
```
/arm-io/mali            compatible = "arm,mali-t880", "mali,midgard"
  reg        = <0x14ac0000 0x5000>            ; registros
  pmu-g3d    = <0x105c0000 0x8000>            ; dominio G3D (solo lectura por ahora)
  clocks/cmu = <0x14aa0000 …>                 ; solo lectura (no se cambia el reloj)
  interrupts = (job, mmu, gpu)                ; SPI del DTB de Linux: NO VERIFICADO
  mem-scratch= <0x8fe00000 0x200000>          ; hoy fijo en el código
  mem-tables = <0x8ffc0000 0x20000>
  mem-pool   = <0x8fc00000 0x200000>
```
Para qué: que el kernel obtenga direcciones del ADT en vez de constantes y que las regiones reservadas se declaren (hoy `0x8fc00000-0x90000000` son constantes del código; que no las ocupe nada más es una **suposición no verificada** — falta comprobar contra el mapa de memoria reservada del bootloader). Los números de interrupción (necesarios si algún día se usan IRQ en vez de sondeo) **no están verificados** y deben salir del DTB del kernel de Linux del propio teléfono.

## 6. Lo que NO se ha hecho
No se leyó el resto de `herolte_gpu.c` (arranque de energía, reloj, recuperación completa); no se ejecutó nada; no se probó que un job pueda escribir las tablas (la conclusión del §3 es por lectura del código); no se comprobó el SysMMU ni el sandbox de iOS; no hay lista oficial de erratas T880 r2p0.

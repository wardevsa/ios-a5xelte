# S7GE — `arm_vm_init` y el diseño de min6 (2026-11-14; L1: código leído, nada medido)

## 1. Hallazgo: desde la etapa 7 el texto y mis bloques estaban apagados
En la variante A5/herolte de `sweet_early_mark`, la marca **7** (`entering arm_vm_init`) pone `a5_active = 0`. Consecuencias: (a) los bloques de `0339` con slot ≥ 9 **nunca** se dibujan (el blanco); (b) las marcas que `0327` puso **dentro** de `arm_vm_init` (`rb: physmap tables`, `rb: prot_init`, `rb: physmap_init`, `rb: extra banks`…) **son código muerto** en este objetivo: ni texto ni bloque. Es decir, **no teníamos ninguna visibilidad de `arm_vm_init`**, justo donde está el sospechoso. El alias físico del framebuffer (TTBR0 bootstrap) **sigue vivo hasta** `set_mmu_ttb(invalid_ttep)` (`arm_vm_init.c` ~2234), así que se puede dibujar durante todo `arm_vm_init`.

## 2. Qué hace `arm_vm_init` (orden real del código)
| Fase | Qué hace | Riesgo conocido |
|---|---|---|
| inicio | tamaño de memoria (`hakios_ram_boot_memory_size`), VA de la physmap según `real_phys_size + bancos extra` | cuentas con 2 GiB + bancos extra (0326-0329) |
| tablas | `init_ptpages` de la physmap, tabla inválida (`alloc_ptpage`) | memoria de `topOfKernelData` |
| `arm_vm_prot_init` | permisos de TEXT/DATA/LINKEDIT, tablas finas | `arm_vm_page_granular_*` (0327 cambió su comprobación de bancos) |
| `arm_vm_physmap_init` | physmap de cada banco; bancos extra con VA congruente a su PA | upstream: "cuelgue mudo en la etapa 7", "`tt_entry_free` assert" (0326-0329) |
| `set_mmu_ttb_alternate(cpu_ttep)` | **TTBR1 pasa a la tabla final** | si falta un mapeo de código/datos en la tabla final, la siguiente captura de instrucción falla y, sin vectores, el reset es inmediato |
| `set_mmu_ttb(invalid_ttep)` | **TTBR0 se invalida**: desaparece el alias físico del framebuffer | a partir de aquí no hay pantalla hasta `serial_init` (stage 16-19) |
`KERNEL_INTEGRITY_KTRR/CTRR` no están definidos para herolte salvo que lo traiga la configuración; `arm_replace_identity_map` se compila solo con ellos.

## 3. Hipótesis sobre el reinicio de ~66 ms (ninguna comprobada)
1. Fallo (excepción) en `arm_vm_physmap_init`/`arm_vm_prot_init` con 2 GiB + bancos: sin manejador de excepciones válido (VBAR de bootstrap) el resultado es un reinicio inmediato. Coincide con el patrón "pantalla negra de dos fotogramas y `start.s` otra vez" y con el histórico del upstream.
2. Fallo justo tras `set_mmu_ttb_alternate`: mapeo ausente en la tabla final.
3. Tras `TTBR0 off`: sigue otro punto de C sin pantalla. Se verá si el último bloque es el 19.
**Lo que min6 distingue:** cada bloque marca una fase de las de arriba; el **último visible** acota el fallo. Esto reemplaza la lista de causas por una medida.

## 4. min6 = kernel con `0340` (sin cambiar ADT ni argumentos)
`0340`: (1) quita la desactivación en la marca 7 y llama a `sweet_early_disable()` justo antes del cambio de TTBR0 (`#if A5XELTE`); (2) bloques nuevos en la columna x=1300 (36×21 px, y = 88 + 32·slot):
| slot | y | color | punto |
|---|---|---|---|
| 9 | 376 | blanco | marca 7 (ahora sí se dibuja) |
| 10 | 408 | rosa fuerte `ff69b4` | tras la cadena `maxmem`/`hw.memsize` (6a→6b) |
| 11 | 440 | turquesa `40e0d0` | tras 6b (higiene) |
| 12 | 472 | marrón `a0522d` | tras `immediate_NMI` |
| 13 | 504 | rosa fuerte | inicio de `arm_vm_init` |
| 14 | 536 | turquesa | tablas de la physmap |
| 15 | 568 | marrón | antes de `arm_vm_prot_init` |
| 16 | 600 | rosa intenso `ff1493` | antes de `arm_vm_physmap_init` |
| 17 | 632 | turquesa oscuro `00ced1` | tras `arm_vm_physmap_init` |
| 18 | 664 | chocolate `d2691e` | tras `set_mmu_ttb_alternate` |
| 19 | 696 | blanco | justo antes de `set_mmu_ttb(invalid)` |
Las marcas de texto de `0327` también vuelven a pintar. **Los colores se repiten (rosa/turquesa/marrón)**: se lee por **posición** (de arriba abajo), no por color. El texto no puede borrar la columna (ver `S7GE_STARTS_ANALYSIS.md` §3 y `S7GE_MIN5_DESIGN.md`).
**Lectura:** último bloque = última fase alcanzada; ninguno nuevo (solo 0-8 como en min5) ⇒ el fallo está en 6a→6b→7 (slots 10-12 lo dirán); hasta el 19 ⇒ el reinicio es posterior al apagado de TTBR0 (siguiente: `serial_init`).

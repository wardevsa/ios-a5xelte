# S7GE — bisección con `herostop=N` (tanda D-0041, 2026-11-14)
**Qué es:** el kernel (0341) congela la CPU (`wfe` en bucle) justo después de dibujar el bloque N de la columna x≈1300. Con eso el resultado es una **imagen fija**, no unos fotogramas fugaces. Cada imagen = la misma que min2 más `herostop=N`.

## Slots (columna derecha; y = 88 + 32·slot) y **orden real de ejecución**
El número de slot **no es monotónico con la ejecución** (0340 añadió los 10-12 entre medias). Orden en que se dibujan:
`0` entrada a `arm_init` · `1` tras `PE_init_platform` · `2` tras `ml_parse_cpu_topology` · `3` tras `cpu_bootstrap` · `4` tras `kernel_startup_bootstrap` · `5` tras `cpu_init` · `6` tras 6a · **`10`** tras la cadena `maxmem` · `7` tras 6b · **`11`** · **`12`** tras `immediate_NMI` · `8` tras 6c · `9` marca 7 · `13`… dentro de `arm_vm_init` · `19` justo antes de apagar TTBR0.
Un freeze en `herostop=N` deja visibles **los bloques ya dibujados** (no 0..N). El slot 0 no puede congelar (va antes de leer la boot-arg); el 1 y siguientes sí (la boot-arg se lee antes de la marca 2).
| `herostop` | punto | bloques visibles al congelar (por slot) | cantidad |
|---|---|---|---|
| 2 | tras `ml_parse_cpu_topology` | 0,1,2 | 3 |
| 4 | tras `kernel_startup_bootstrap` | 0-4 | 5 |
| 6 | tras 6a | 0-6 | 7 |
| **8** | tras 6c | 0-8 y 10, 11, 12 (**falta el hueco del slot 9**) | **12** |
| 12 | tras `immediate_NMI` | 0-7 y 10, 11, 12 | 11 |
| 16 | antes de `arm_vm_physmap_init` | 0-16 salvo ninguno (12 ya dibujado) → 0-16 | 17 |
| 19 | justo antes de apagar TTBR0 | 0-19 | 20 |
Los bloques tienen **colores repetidos**; se cuentan por posición (y). El hueco del slot 9 (y=376) en h08 es normal.

## Cómo se interpreta cada intento
| Se ve | Significa |
|---|---|
| **Pantalla congelada** con N+1 bloques en la columna | el kernel **llegó** al bloque N; el reinicio es posterior |
| El reinicio de siempre (azul/cian/magenta + `XNU MMU ON`, sin columna) | el kernel **no llegó** al bloque N; el reinicio es anterior |
| Congelada pero con menos bloques de los esperados | revisar: algún bloque no se dibujó (mirar el vídeo) |
| Negro o algo nuevo | transcribir literal |

## Orden de la búsqueda (mínimo de escrituras)
1. **h08** (escrita, E-0059/0060). Si **congela** → siguiente **h12**; si **no** → **h04**.
2. Tras h12 congelada → **h16**, luego **h19**; si h19 también congela, el reinicio es **después** de apagar TTBR0: siguiente paso = marcas tras `serial_init` (kernel nuevo).
3. Tras h04 no congelada → **h02**; tras h04 congelada → **h06**.
Imágenes ya construidas y verificadas (E-0061…E-0066): h02, h04, h06, h12, h16, h19. La tanda permite 8 escrituras: h08 + 7.

## Resultado de h08 (E-0067, 2026-11-14)
**Congeló** con el texto de las marcas 1-6c y la columna derecha exactamente como se predijo (0-8, hueco del 9, 10-12). El kernel ejecuta `arm_init` **hasta la marca 6c** y la parada funciona: **el reinicio es POSTERIOR a la marca 6c.** Esto valida el método y cierra las preguntas anteriores (el texto sí se imprime; antes solo era fugaz).
Consecuencia: h02, h04, h06 y h12 **ya no aportan nada** (esos puntos se han pasado). Quedan, en **orden de ejecución**: `9` (tras la marca 7) → `13` (inicio de `arm_vm_init`) → `14` → `15` → `16` → `17` → `18` → `19` (justo antes de apagar TTBR0). 8 posibilidades ⇒ 3 escrituras bastan: **h16** primero; si congela → **h18** (luego 17 o 19); si no → **h14** (luego 13 o 15, y 9).
Imágenes listas y verificadas: h09, h13, h14, h15, h16, h17, h18, h19 (E-0068…E-0073 y E-0063…E-0066).

## Resultado de h16 (E-0075, 2026-11-14)
**Congeló.** Texto hasta `7: rb: physmap_init` y 17 bloques: 0-13, hueco en 14, 15 y 16. El hueco del slot 14 **es esperado**: el bloque y la marca `rb: physmap tables` están dentro de `#if defined(ARM_LARGE_MEMORY)`, que no se compila para herolte (comprobado en `arm_vm_init.c` ~2051-2060); tampoco aparece `rb: identity map` (KTRR/CTRR, no definido). El kernel llega al **bloque 16 = justo antes de `arm_vm_physmap_init`**. **El reinicio ocurre después**: dentro de `arm_vm_physmap_init`, tras ella o más tarde.
Quedan: `17` (tras `arm_vm_physmap_init`), `18` (tras `set_mmu_ttb_alternate`), `19` (antes de apagar TTBR0). Siguiente: **h17**. Si **no** congela ⇒ el reinicio está **dentro de `arm_vm_physmap_init`** (mapeo de los bancos de RAM; el sospechoso histórico, 0326-0329); si congela ⇒ h18, luego h19.

## Resultado de h17 (E-0077, 2026-11-14)
**Congeló** con `7: rb: extra banks` y `7: rb: extra banks mapped` y un bloque nuevo al final de la columna (slot 17). **`arm_vm_physmap_init` termina bien.** El reinicio es posterior al bloque 17: quedan `18` (tras `set_mmu_ttb_alternate`, el cambio de TTBR1 a la tabla final), `19` (justo antes de apagar TTBR0) y lo que viene después (sin pantalla: el alias del framebuffer desaparece). Siguiente: **h18**.

## Resultado de h18 (E-0079, E-0080, 2026-11-14)
**Congeló con el bloque 18 visible** (el Director aclaró: los dos últimos bloques eran cian y marrón chocolate). **`set_mmu_ttb_alternate` se supera**: el kernel ejecuta con la tabla TTBR1 final. El reinicio es posterior al bloque 18. Queda un punto con pantalla: **19** (justo antes de `set_mmu_ttb(invalid_ttep)`, que apaga TTBR0 y el alias del framebuffer). Siguiente: **h19**. Si h19 congela ⇒ el reinicio está **después de apagar TTBR0** (sin pantalla; hace falta un kernel nuevo con un alias del framebuffer en la tabla final); si no congela ⇒ está entre 18 y 19 (`ml_enable_monitor` y poco más).

## Resultado de h19 (E-0082, 2026-11-14) y siguiente paso
**Congeló con el bloque 19 (blanco).** El kernel llega **justo antes de `set_mmu_ttb(invalid_ttep)`**. **El reinicio ocurre después de apagar TTBR0** (en esa instrucción, en `flush_mmu_tlb`, en el reenlace de punteros de la physmap o en `pmap_bootstrap`/el código posterior). Con el alias físico del framebuffer ya no hay pantalla: se necesita un alias **virtual** en la tabla final. Parche **0343** (`xnu/patches/0343-herolte-min8-fb-alias-after-ttbr0.patch`): mapea el bloque de 32 MiB del framebuffer en la tabla final (como `sweet_early_map_final()` del donante), reapunta el dibujado temprano y añade los bloques 20-27 (TTBR0 off, punteros reenlazados, antes y después de `pmap_bootstrap`, E/S temprana, fin de `arm_vm_init`, antes y después de `serial_init`). Requiere kernel nuevo (CI) e imágenes nuevas: **decisión nueva** (D-0041 cubre solo el kernel `4e5f25a5…`).

## Resultado de min8h23 (E-0093, 2026-11-14): fallo de mi parche 0343, pánico visible
**No es el reinicio buscado.** `A5 XNU PANIC: arm_vm_init.c:1878 Assertion failed: (l1 & (VALID | TYPE_MASK)) == (VALID | TYPE_TABLE)`: en `a5_early_map_final()` (mi 0343) no existe la entrada L1 de `VM_MIN_KERNEL_ADDRESS` — sin `ARM_LARGE_MEMORY` nadie la crea (la physmap del donante sí). Coincide con lo visto: bloques hasta el 15 y sin las tres últimas líneas `rb:` (la función corre justo antes de `rb: physmap_init`).
**Corrección:** parche `0344` (`init_ptpages` crea la entrada antes de leerla). Nuevo CI y nuevo kernel ⇒ nueva autorización (D-0042 cubre solo `ac49a28e…`). **Aprendizaje:** el pánico temprano se dibuja y dice archivo, línea y condición: es un canal de diagnóstico muy barato.

## Resultado de min9h23 y min9 (E-0105, E-0107, 2026-11-14): colgado en el bloque 19
Con el kernel 0344, **tanto con `herostop=23` como sin `herostop`** la pantalla queda igual que en h19: texto hasta los cuatro `rb:` y bloques hasta el 19, sin pánico y sin bloques nuevos. Sin parada, con los kernels sin alias virtual, ese punto acababa en reinicio; ahora **se cuelga**. Lectura: tras `set_mmu_ttb(invalid_ttep)` algo falla (el fallo original de min2-min7), y como el dibujo temprano sigue activo por el alias, **el camino de pánico también falla** (bucle) o el alias no es utilizable. La L1 ya existe (la aserción no salta), pero el dibujo por el alias no se ha validado. Parche **0345**: antes de apagar TTBR0 escribe un píxel por el alias, lo lee por la dirección física y pinta el veredicto (bloque 20 verde = misma memoria, rojo = distinta), reapunta y dibuja el bloque 21 por el alias con TTBR0 aún válido; los bloques posteriores pasan a 22-29. Si el acceso por el alias falla, el pánico se verá por el alias físico.

## Kernel 0347: h24 (E-0133, 2026-11-14) — el kernel sobrevive a apagar TTBR0
Con el alias de 8 bloques (0347) la sonda da **verde (slot 20)** y **h24 congela con los bloques 19-24**: el kernel apaga TTBR0 (22), reenlaza punteros (23) y llega antes de `pmap_bootstrap` (24). **El reinicio ocurre después del bloque 24.** Candidatos: `pmap_bootstrap` (25), tablas de E/S tempranas (26), volver de `arm_vm_init` (27), `serial_init` (28/29) y lo que sigue en `arm_init`. Siguiente: **h26** (ya preparada, E-0129); si congela ⇒ h28; si no ⇒ h25 (por construir).

## Kernel 0347: h26 (E-0135, 2026-11-14) — pmap_bootstrap se supera
**Congeló con los bloques 25 (tras `pmap_bootstrap`) y 26 (tablas de E/S tempranas).** El reinicio es posterior al bloque 26. Quedan: 27 (`arm_vm_init` devolvió el control a `arm_init`), 28 (justo antes de `serial_init`) y 29 (justo después). Siguiente: **h28** (preparada, E-0130).

# S7GE — diseño de min5: bloques persistentes en C (parche 0339; 2026-11-14)
**No construida, no publicada.** `xnu/patches/0404-herolte-min5-persistent-c-blocks.patch` está en un commit local; aplica limpio sobre el árbol con 0332-0338. Depende de la **lectura de min4**: solo se construye si min4 deja claro que el ensamblador termina o si el texto no es observable.

## 1. Qué hace
`sweet_early_block(slot, argb)`: un bloque de 36×21 px en **x = 1300, y = 88 + 32·slot**, dibujado con el mismo alias físico y la misma puerta (`a5_active`) que el texto, y por tanto válido hasta que `arm_vm_init` cambia TTBR0. Está a la **derecha de la línea de texto más larga** (~1060 px), así que el texto de las etapas **no puede borrarlo** (ver `S7GE_STARTS_ANALYSIS.md` §3).

| slot | y | color (ARGB) | punto de `arm_init` |
|---|---|---|---|
| 0 | 88 | rojo `ffff0000` | etapa 1: entrada a `arm_init` |
| 1 | 120 | verde `ff00ff00` | 2: `PE_init_platform` |
| 2 | 152 | azul `ff0000ff` | 3: `ml_parse_cpu_topology` |
| 3 | 184 | amarillo `ffffff00` | 4: `cpu_bootstrap` |
| 4 | 216 | cian `ff00ffff` | 5: `kernel_startup_bootstrap` |
| 5 | 248 | magenta `ffff00ff` | 6: `cpu_init` |
| 6 | 280 | naranja `ffff8000` | 6a: `processor_bootstrap` |
| 7 | 312 | lima `ff80ff00` | 6b: `maxmem` e higiene |
| 8 | 344 | violeta `ff8000ff` | 6c: `boot-args` y PAN |
| 9 | 376 | blanco `ffffffff` | 7: antes de `arm_vm_init` |
Lectura: la columna de la derecha, de arriba abajo, **es el progreso**; el último bloque visible es la última etapa alcanzada. Cero bloques ⇒ C no llegó a `arm_init` (hipótesis B/C de `STARTS_ANALYSIS` §4).

## 2. Límites
- Solo cubre hasta la marca 7; después de `arm_vm_init` el alias físico desaparece. Para `kmem_range_init` y más allá haría falta un bloque con el alias del kernel (`sweet_early_relocate` está vacío en la variante A5) o el texto de consola: **min6**, sin diseñar aún.
- No toca el ADT ni los argumentos: min5 = min4 + 0339, con la misma línea de arranque que min2.
- Requiere kernel nuevo (CI, D-0030 cubre push de `herolte-drop-v2` a `mio`) y una autorización roja con imagen y hash propios.

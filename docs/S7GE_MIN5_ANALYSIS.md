# S7GE — candidata min5 (2026-11-14, construida y verificada en el PC; NO escrita)

## 1. Qué es
`xnu-boot-v2-s7-min5-20261114.img`, SHA-256 `4cb134c25ba32ddbf478ddb172d259656c3e2f624e1faf778c96d9dd86293bd5`, 18 618 384 B (E-0052). Respecto a **min4** cambia **solo el kernel**: CI 43596777961 (`842a4e5`, kernel `6693c690…5317fe`) con los parches `0338` y **`0339`** (`ci_check`: APLICADO). ADT de 2 GiB (`dc817436…`) y línea de arranque **idénticos a min2/min4**. 47 PASS (constructor) y 57 PASS (independiente), 0 FAIL.

## 2. Por qué esta y no la propuesta de jefatura (sin wifi/power/gpu ni `vm_compression_limit`)
- **min1 ya llevaba `herowifi=0 heropower=0 herogpu=0`**; min2 solo añadió `vm_compression_limit=98304 vm_compressor=2` (E-0045). La tabla "min1 con valores por defecto" era incorrecta.
- `start.s` (también `tunables_done`) **no lee la línea de arranque**: el ensamblador es idéntico en las cuatro imágenes y los argumentos solo se leen en C. Los argumentos no pueden explicar un cuelgue anterior a C.
- Con los mismos argumentos, min5 cambia **una variable** (la instrumentación), igual que se hizo hasta ahora. Variar argumentos queda para min6 con 0339 ya instalado.

## 3. Qué muestra el parche 0339
Columna de bloques de 36×21 px en **x = 1300**, y = 88 + 32·slot, que el texto no puede pisar (ver `S7GE_MIN5_DESIGN.md`): de arriba abajo, rojo (etapa 1, entrada a `arm_init`), verde (2), azul (3), amarillo (4), cian (5), magenta (6), naranja (6a), lima (6b), violeta (6c), blanco (7, antes de `arm_vm_init`). Más los bloques de 0338 (x=240) y los originales.
| Resultado | Lectura |
|---|---|
| ningún bloque en x=1300 | C no llegó a `arm_init` (etapa 1): el cuelgue está antes, entre `start.s` y `arm_init`; ya no es cuestión de observación del texto |
| hasta el bloque *n* | la etapa *n* terminó y la *n+1* no |
| los diez | `arm_vm_init` es lo siguiente (min6) |
**Observación:** captura la **columna derecha** (x ≈ 1300, borde derecho de la pantalla; la pantalla es de 1440 px de ancho) además de la izquierda. Ver `S7GE_MIN4_OBSERVATION_TEMPLATE.md` (añadir la columna).

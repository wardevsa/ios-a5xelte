# S7GE — candidata min6 (2026-11-14, construida y verificada en el PC; NO escrita)

## 1. Qué es
`xnu-boot-v2-s7-min6-20261114.img`, SHA-256 `4f412a5beb66d4b330c27f2c4680b22562cac6405722b7d1ea7a48ec55129b43`, 18 618 384 B (E-0055). Respecto a **min5** cambia **solo el kernel**: CI 43600631386 (`9847af4`, kernel `c1bc0e8f…f676`) con `0338`, `0339` y **`0340`** (`ci_check`: APLICADO). ADT de 2 GiB (`dc817436…`) y línea de arranque **idénticos a min2/min5**. 47 PASS (constructor), 57 PASS (independiente), 0 FAIL.

## 2. Qué añade 0340 (solo dibuja)
Mantiene la consola temprana viva hasta justo antes de invalidar TTBR0 y añade bloques en la columna x=1300 (36×21 px, y = 88 + 32·slot). Detalle y razones en `S7GE_ARM_VM_INIT_ANALYSIS.md` §4. De arriba abajo, tras los 9 de min5 (slots 0-8: rojo, verde, azul, amarillo, cian, magenta, naranja, lima, violeta):
9 blanco (marca 7) · 10 rosa fuerte (tras `maxmem`) · 11 turquesa (tras 6b) · 12 marrón (tras `immediate_NMI`) · 13 rosa (inicio de `arm_vm_init`) · 14 turquesa (tablas) · 15 marrón (antes de `prot_init`) · 16 rosa intenso (antes de `physmap_init`) · 17 turquesa oscuro (tras `physmap_init`) · 18 chocolate (tras TTBR1 final) · 19 blanco (antes de TTBR0 off).
**Se lee por posición, no por color** (se repiten). Hasta 20 bloques en total; el último visible acota dónde ocurre el reinicio.

## 3. Cómo observar
Misma plantilla (`S7GE_MIN4_OBSERVATION_TEMPLATE.md`) más la columna derecha: cuenta de arriba abajo cuántos bloques hay (de 20 posibles) y, a poder ser, una captura fija **antes** de que la pantalla pase a "azul, cian, magenta, XNU MMU ON". Una grabación en cámara lenta del tramo (~66 ms de negro entre los dos estados) ayuda a ver el último fotograma.

## 4. Riesgo
Solo dibujo; con la consola temprana viva dentro de `arm_vm_init` aparece también texto de las marcas de 0327. Si el reinicio ocurre antes que en min5 (menos bloques que los 9 de min5) hay regresión del parche: restaurar BOOT.

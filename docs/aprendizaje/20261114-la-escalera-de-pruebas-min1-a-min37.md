# Informe de aprendizaje: la escalera de pruebas, de min1 a min37

> *Informe retroactivo (D-0091), reconstruido a partir de `HEROLTE_PROGRESS.md`, el historial de Git y las evidencias de gobierno. Desde aquí el trabajo es del equipo de este repositorio.*

## 1. Qué hicimos y por qué
Arrancar XNU en este teléfono por primera vez exigió casi cuarenta imágenes de BOOT, cada una con **un solo cambio** respecto a la anterior. El método importa más que cada número: bloques de color en la pantalla, un log persistente y una hipótesis por prueba.

## 2. El concepto
- **Marcadores de progreso:** una columna de bloques de colores dibujados en el framebuffer por el propio kernel; el número de bloques visibles dice hasta dónde llegó antes de congelarse.
- **Log persistente (`herolog=1`):** el kernel escribe su registro en los últimos 4 MiB de USERDATA; se lee después desde TWRP.
- **Un cambio por prueba:** si se cambian dos cosas a la vez y falla, no se sabe cuál.
- **Hash de la imagen:** cada BOOT se identifica por su SHA-256 y se lee de vuelta tras escribirla.

## 3. La evidencia (medido)
- min7 (E-0067): se congela con las marcas 1-6c visibles; `herostop=8` detuvo la CPU en la marca 6c.
- min8 (E-0093): pánico `arm_vm_init.c:1878 Assertion failed (l1 & …) == …TYPE_TABLE`, causado por un parche mío (0343).
- min10 (E-0114): `Invalid kernel stack pointer` en `vm_fault_internal`; el primer fallo era mi sonda de alias. Parche 0346.
- min13 (E-0148): pantalla negra con la columna 30-40 completa: `arm_init` termina justo antes de `machine_startup`.
- min15v a min19: añadir `-v`, después `ufsrw=1 rootrw=1` (D-0049) y `herolog=1`.
- min24 (E-0208): las 9 superficies origen sondeadas eran **todo ceros**, también tras limpiar la caché: no era coherencia.
- **min33 (E-0244):** segundo arranque sin congelación; iOS con apps que cargan; el teléfono se presenta como iPhone X con 21 GB.
- min35 (E-0257): corrección de una premisa propia: la radio Wi-Fi **nunca se había iniciado** (`herowifi=0`), no estaba rota.
- Hipótesis anotada y no confirmada: que la fluidez dependiera de GPU; el análisis posterior la contradijo.

## 4. Cómo defenderlo
**Pregunta posible:** ¿Por qué un solo cambio por prueba?
**Respuesta modelo:** Porque el teléfono solo dice «arranca» o «no arranca»; con dos cambios no se puede atribuir el resultado. Cuando incumplí la regla (min56: cambié el kernel y quité `-noprogress`) dio pánico y no supe cuál lo causaba.

**Pregunta posible:** ¿Cómo sabías hasta dónde había llegado un kernel congelado?
**Respuesta modelo:** Por los bloques de colores que el propio kernel dibuja en el framebuffer: cada bloque es una marca en el código de arranque, y el último visible indica el punto del fallo.

**Pregunta posible:** ¿Para qué leer la imagen de vuelta tras escribirla?
**Respuesta modelo:** Para comprobar que la partición contiene exactamente el SHA-256 de la imagen preparada; sin eso, un error de escritura parecería un fallo del kernel.

## 5. Para profundizar
`tools/herolte-build-min.sh`, `tools/herolte-log-pull.py`, `tools/herolte-log-report.py`, `governance/data/evidence.toml` (E-0049 a E-0257).

# Informe a la Jefatura Técnica — cambios de método tras min6 (2026-11-14, Ingeniero Principal)

## 1. Qué decidió el Director (mensaje del 2026-11-14)
1. Observa **él mismo** desde min2/min3 (ya no una IA); hace lo que puede, y el método debe adaptarse a eso.
2. **Aprueba** el canal de migas en RAM leídas desde TWRP (D-0040, solo lectura, nodo temporal).
3. **Aprueba las autorizaciones por tandas** y me deja definirlas (ver §4).
4. Respecto a un BOOT que arranque: solo tenemos el BOOT **original de Android** (E-0009); no es una imagen que arranque iOS.
5. Acepta que **yo decida los detalles técnicos** y que la jefatura fije objetivos.

## 2. Cambios técnicos (todos en la rama `herolte-drop-v2`, publicados en `mio`, D-0030)
| Parche | Qué hace | Estado |
|---|---|---|
| 0338 | dos bloques en `start.s` entre magenta y amarillo; marcas 6a-6c en C | escrito en min4 (E-0051); sin utilidad nueva |
| 0339 | bloques persistentes en la columna x=1300 (el texto no los pisa) | min5 (E-0053): se vieron 7 bloques (hasta 6a) |
| 0340 | consola temprana viva dentro de `arm_vm_init`; bloques 9-19 | min6 (E-0056): el Director no vio nada |
| **0341** | boot-arg **`herostop=N`**: congela la CPU tras el bloque N; la pantalla queda fija | **nuevo**, en CI |
| **0342** | contador de entradas a `start_first_cpu` junto al marcador (`0x8ffff108`) | **nuevo**, en CI |
El cargador **no se toca**: su binario de la fecha 12-nov (16 192 B) **no se reproduce** desde las fuentes actuales (la fuente actual lleva el código de splash y da 18 704 B); recompilarlo cambiaría una segunda variable sin que lo hayamos probado. Queda como deuda: registrar de qué commit y con qué banderas salió el binario usado.

## 3. Método nuevo
- **Resultado estático en vez de fugaz:** `herostop=N` + imagen que solo cambia la línea de arranque. La bisección (`herostop=8`, `12`, `16`, `19`, sin parada) se hace regenerando la imagen en el PC (minutos, sin CI).
- **Medición sin ojos:** antes y después de cada intento, desde TWRP, leer la página `0x8ffff000` (D-0040): el contador de 0342 (`+0x108`) dice cuántas veces entró `start.s` (la diferencia entre antes y después), y el registro del cargador (`log[10]` = paso alcanzado, `log[15]`/`[17]` = entrada y `boot_args`) confirma que el cargador saltó.
- **Vídeo:** el Director grabará; yo extraeré los fotogramas con `ffmpeg` sin transcripción de IA.

## 4. Autorización por tandas (propuesta de redacción; se firmará con el hash del kernel)
Decisión **D-0041** (se crea cuando el kernel de 0341+0342 tenga hash y esté verificado):
- **Qué:** escribir en BOOT hasta **8 imágenes** distintas, todas con **el mismo kernel (hash X)**, **el mismo ADT y el mismo cargador**, y que **difieran solo** en `herostop=N` en la línea de arranque (N entre 1 y 19, o ausente).
- **Cómo:** cada imagen la construye `tools/herolte-build-n2.sh`, pasa 47 PASS (constructor) y 57 PASS (independiente), se registra su hash **antes** de escribirla y se escribe con `herolte-flash-boot.sh --execute` (lectura de vuelta y EFS antes/después).
- **Límites:** solo BOOT; caducidad 2026-11-16; vuelta atrás con E-0009; parada si una imagen no arranca o la lectura de vuelta falla; informe al Director en cada paso.
- **Fuera:** cambiar el kernel, el ADT, el cargador o cualquier otro argumento exige una decisión nueva.

## 5. Correcciones a la jefatura (hechos verificados en el código o en la documentación)
- min1 **ya llevaba** `herowifi=0 heropower=0 herogpu=0`; solo se añadió `vm_compression_limit`/`vm_compressor` en min2 (la hipótesis "reactivar wifi/power/gpu" no tenía base).
- `tunables_done` **no lee** argumentos de arranque; el ensamblador no depende de la línea de arranque.
- La autorización **no lleva el número de serie** del teléfono y el destino se nombra por `by-name`, no por `sda5`.
- Los 7 bloques de min5 eran las **etapas 1 a 6a**, no "etapa 3".
- **Punto abierto que contradice el enfoque en `arm_vm_init`:** la lectura de min1 decía que el pánico fue en `kmem_range_init`, que ocurre **después** de `arm_vm_init`. Si eso fue cierto, `arm_vm_init` terminó en min1 con el mismo kernel, y el reinicio de min2-min6 podría estar **más tarde** que `arm_vm_init` (con `vm_compression_limit`, donde min1 ya no entra en pánico). Mis bloques solo cubren hasta justo antes de apagar TTBR0 (slot 19): si los 20 aparecen, el siguiente paso son marcas tras `serial_init`.

## 6. Qué esperar de la próxima iteración (min7)
Kernel = 0338-0342 (CI en curso), mismo ADT y mismo cargador, línea de min2. Primero **sin** `herostop`, solo para ver qué pasa ahora y leer el contador; después la bisección. Cada imagen se anuncia con su hash.

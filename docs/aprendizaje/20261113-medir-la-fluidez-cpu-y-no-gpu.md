# Informe de aprendizaje: medir antes de optimizar, la fluidez era cosa de la CPU

> *Informe retroactivo (D-0091), reconstruido a partir de `HEROLTE_PROGRESS.md`, el historial de Git y las evidencias de gobierno. Desde aquí el trabajo es del equipo de este repositorio.*

## 1. Qué hicimos y por qué
La interfaz iba lenta y la sospecha natural era la GPU. Se perfiló el sistema y la medida contradijo esa idea. A la vez se encontró por qué el fondo original de iOS salía negro.

## 2. El concepto
- **Perfilado por muestreo:** parar un proceso a intervalos y anotar dónde está su pila; los porcentajes dicen dónde se pierde el tiempo.
- **Espera activa frente a dormir:** girar en un bucle consume CPU y calor; dormir entre sondeos los reduce con un coste pequeño de latencia.
- **Decodificador HEVC/HEIC:** iOS guarda fondos en HEIC; sin decodificador por hardware ni de reserva por software, la imagen sale vacía **sin error**.

## 3. La evidencia (medido)
- Con movimiento, la Mali estaba ocupada **22-29 %**; backboardd tardaba **18-20 ms de CPU por cuadro** (~30 trabajos de GPU por cuadro, ~1100 por segundo) y SpringBoard usaba 120-160 %. En el perfilador: `mach_msg2_trap` 32,7 %, `surface_changed` 12,5 %, Mesa entero 13,9 %.
- Parche 0333: el kernel esperaba cada trabajo girando en `delay(10)`; ahora tras 4 sondeos duerme de 50 µs. CPU de backboardd por cuadro: de ~88 ms a ~60 ms (**muestra pequeña**, a repetir con el mismo uso).
- Parche 0334: el escalado de cada cuadro también se espera durmiendo. El Director lo nota **más fluido y que calienta menos**.
- Fondo original: dentro de `CollectionsPoster`, `Background.HEIC` abre bien con ImageIO pero al dibujarlo da **0 de 2500560 píxeles distintos de cero**: la decodificación sale vacía sin error. Arreglo aplicado: convertirlos a PNG al armar la raíz (`sips` en macOS).
- Hipótesis descartada con medida: «el kernel o hakios-gl copiaban mal» (el censo mostraba cero porque la memoria estaba realmente vacía).

## 4. Cómo defenderlo
**Pregunta posible:** ¿Por qué no se optimizó la GPU si es lo gráfico?
**Respuesta modelo:** Porque lo medimos: la GPU estaba ocupada una cuarta parte del tiempo y el tiempo de CPU de backboardd por cuadro era el límite; optimizar la GPU no habría movido el resultado.

**Pregunta posible:** ¿Por qué dormir entre sondeos reduce el calor?
**Respuesta modelo:** Porque el bucle de espera activa mantiene un núcleo trabajando al máximo mientras no hace nada útil; al dormir, el núcleo entra en reposo y gasta menos.

**Pregunta posible:** ¿Cómo se supo que el fondo no era un problema del kernel?
**Respuesta modelo:** Se pintó la imagen dentro del propio proceso con ImageIO y ya salía vacía; eso aísla el fallo en el decodificador HEIC, antes de llegar al kernel o a la GPU.

## 5. Para profundizar
Parches `0333`, `0334`, `tools/herolte-wallpaper-png.sh`, `gpu/hakios-gl`, `HEROLTE_PROGRESS.md` (sección 12-13 nov).

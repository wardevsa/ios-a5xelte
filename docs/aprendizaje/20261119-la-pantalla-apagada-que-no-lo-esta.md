# Informe de aprendizaje: la pantalla «apagada» que seguía gastando 140 mA

Política D-0091. Fecha 2026-11-19. Evidencias: E-0301 y E-0302. Decisiones: D-0093 (alcance de la prueba) y D-0092 (cupo).

## 1. Qué hicimos y por qué
Con el A/B de la prueba anterior sabíamos que apagar núcleos no ahorra nada medible y que los núcleos están ociosos casi todo el tiempo. Había que buscar el consumo en otro sitio. En lugar de adivinar, hicimos una **respuesta a escalón**: con la pantalla apagada, apagar un grupo de dominios de energía cada 45 segundos y mirar la corriente tras cada paso, todo en el mismo arranque.

## 2. El concepto
- **Dominio de energía (power domain):** un bloque del SoC que se puede cortar entero (cámaras, ISP, GPU, pantalla, audio…). El PMU lo apaga escribiendo su registro de configuración y comprobando después su registro de estado.
- **Respuesta a escalón:** cambiar una sola cosa de golpe y ver cómo reacciona una medida. Si cambia en la primera muestra tras el evento, el cambio es del evento; si baja poco a poco, puede ser deriva (el sistema que se asienta).
- **Pantalla «apagada» ≠ controlador de pantalla apagado:** iOS puede poner el panel en negro mientras el controlador (DECON) y el enlace con el panel siguen enviando fotogramas negros, y eso consume corriente y ancho de banda de memoria.
- **Estado intermedio de un dominio:** un dominio que no completa el apagado queda en un estado a medias; no es «encendido» ni «apagado».

## 3. La evidencia (medido)
| Tras apagar… | Mediana con pantalla apagada | Cambio frente a la ventana anterior |
|---|---|---|
| (antes) | 529 mA (n=2) | |
| seis dominios pequeños (cámaras, ISP, MFC, mscl) | 472 mA (±11, n=9) | |
| audio | 467 mA (±10, n=9) | −5 mA, intervalo 95 % [−36, +34]: sin efecto |
| GPU | 432 mA (±12, n=9) | −35 mA, intervalo [−74, −4] |
| **intento de apagar la pantalla (disp0)** | **290 mA (±6, n=135)** | **−142 mA, intervalo [−158, −101]** |

- El dominio de la pantalla **no llegó a apagarse** en 10 ms: quedó en un estado a medias (`0x9000e`), se volvió a pedir encendido y su estado siguió igual. Aun así la corriente cayó a 290 mA en la primera muestra tras el evento y se mantuvo unos 11 minutos.
- El sistema siguió vivo todo ese tiempo, pero la pantalla y los botones no respondieron después (esperable: ni la GPU ni la pantalla se restauran).
- Reservas: es una sola prueba; la ventana «antes» tiene solo 2 muestras limpias; hasta la GPU la corriente baja también por la deriva con el tiempo desde el arranque (E-0301), pero el escalón de −142 mA no puede ser deriva porque aparece de golpe.
- **Hipótesis, no medida:** el controlador de pantalla y el tráfico de memoria que genera con la pantalla «apagada» son el consumo dominante. No sabemos todavía qué parte del bloque se detuvo.

## 4. Cómo defenderlo
**Pregunta posible:** ¿Por qué un escalón es mejor que comparar pruebas distintas?
**Respuesta modelo:** Porque cambia una sola cosa en un instante conocido y dentro del mismo arranque; si la corriente salta en la primera muestra posterior, el cambio es atribuible al evento y no a que el sistema se asiente con el tiempo.

**Pregunta posible:** ¿Qué descubrió la prueba por pasos?
**Respuesta modelo:** Que apagar audio no cambia nada medible, la GPU quita unos 35 mA y el bloque de la pantalla quita unos 142 mA de golpe, aunque ni siquiera llegó a apagarse del todo; con la pantalla apagada el consumo estaba en el subsistema de pantalla y no en los núcleos.

**Pregunta posible:** ¿Por qué una pantalla apagada puede seguir gastando?
**Respuesta modelo:** Porque «apagada» suele significar que el panel muestra negro; el controlador de pantalla puede seguir enviando fotogramas y leyendo memoria, y esa actividad sigue costando energía aunque no se vea nada.

**Pregunta posible:** ¿Cuál es el siguiente paso y por qué no se deja el apagado de dominios tal cual?
**Respuesta modelo:** Hay que separar qué parte del bloque de pantalla produce el ahorro y apagarla de forma reversible (que se pueda despertar la pantalla). Apagar el dominio entero es de un solo sentido y deja el teléfono sin pantalla hasta reiniciar.

**Dato honesto, para que conste:** antes de esta prueba habíamos buscado el consumo en los núcleos durante muchas horas. La respuesta estaba en la pantalla, y la encontramos al dejar de suponer y diseñar una prueba que aislara cada bloque.

## 5. Para profundizar
Parche `0455`, `docs/aprendizaje/20261119-apagar-un-cluster-y-medir-bien.md`, evidencias E-0301 y E-0302, y el controlador de pantalla de Samsung (`decon_8890`) como referencia de cómo se para y se arranca sin perder el estado.

# Informe de aprendizaje: parar lo que nadie está mirando (pantalla y dominios de energía)

Política D-0091. Fecha 2026-11-19. Evidencias: E-0302, E-0304, E-0307, E-0308, E-0311, E-0312 y E-0310.

## 1. Qué hicimos y por qué
Con la pantalla apagada el teléfono consumía unos 520-535 mA, y Linux en TWRP solo 25-35 mA. Los núcleos estaban ociosos al 97-99 %, así que el consumo estaba en otro sitio. Fuimos apagando, uno a uno y con medición, lo que nadie usa mientras la pantalla está apagada, y lo dejamos **activado por defecto**.

## 2. El concepto
- **Dominio de energía:** una zona del chip con su propio interruptor en el controlador de energía (PMU). Apagarlo corta su alimentación, no solo su reloj.
- **DECON:** el controlador que lee la memoria de la pantalla y la envía al panel. Con un panel en modo comando, el panel guarda la imagen y el DECON puede pararse sin que se vea nada.
- **Escalera:** apagar los consumidores de uno en uno, con un tiempo entre pasos, para atribuir cada bajada de corriente a su causa.
- **Restauración:** todo lo que se apaga debe volver a encender y recuperar su estado. Se guarda la configuración antes de apagar y se vuelve a escribir al despertar, esperando la confirmación del hardware.
- **Instrumento de medida:** `herocycle` apaga y enciende la pantalla solo para repetir la prueba sin dedos ni errores.

## 3. La evidencia (medido)
- DECON parado: de 519-535 mA a **355-368 mA** (E-0304, E-0307), con 0 píxeles no negros en la memoria (E-0306, E-0307).
- Escalera completa (seis dominios pequeños, audio, GPU): **280 mA** en min91 (E-0308).
- Repetición automática y por defecto: tres ciclos, 24 restauraciones sin fallo, el códec de audio contestó `0x6364` antes y después (E-0311, E-0312). Suelo: **284 mA, IC95 [276, 293], n=48**. Reducción del 46 % frente a la línea base.
- **Errores míos, para que consten:** (1) sesgo de etiquetado de la pantalla en análisis anteriores (E-0303); (2) afirmé que `-noprogress` era un no-op sin mirar qué rama del código se compilaba, y su ausencia provocó un panic en el arranque (E-0310); (3) en dos ocasiones actualicé el relevo antes de confirmar la escritura.

## 4. Cómo defenderlo
**Pregunta posible:** ¿Cómo sabes que apagar un bloque no rompe nada?
**Respuesta modelo:** Cada apagado se guarda y se restaura al despertar, y el registro lo confirma línea a línea: 24 restauraciones en tres ciclos, todas con la configuración y el estado originales. Además el códec de audio sigue contestando después de restaurar su dominio.

**Pregunta posible:** ¿Por qué no se ve nada en la pantalla con el DECON parado?
**Respuesta modelo:** El panel es de modo comando: guarda la última imagen y se refresca solo, así que el controlador puede dejar de enviarla. Antes de pararlo, el kernel espera a que el desvanecido a negro termine y cuenta los píxeles: 0 de 3,7 millones no son negros.

**Pregunta posible:** ¿Cuánto queda por ahorrar?
**Respuesta modelo:** Con la pantalla apagada estamos en unos 284 mA frente a los 25-35 mA de Linux. Quedan unos 250 mA en núcleos, memoria, almacenamiento, radios y reguladores, que aún no se han tocado.

**Pregunta posible:** ¿Qué limita la conclusión?
**Respuesta modelo:** La corriente la mide el propio teléfono, no un instrumento externo; el suelo es sólido (48 muestras en tres ciclos), pero cada escalón intermedio tiene solo 2-4 muestras. El apagado automático no pasa por iOS, así que la pantalla puede quedar negra al terminar.

## 5. Para profundizar
`bsd/dev/herolte_gpu.c` (parches 0456, 0457, 0458, 0459, 0460, 0461) y `docs/aprendizaje/20261119-la-pantalla-apagada-que-no-lo-esta.md`.

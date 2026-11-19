# Informe de aprendizaje: construir un laboratorio para no engañarnos con nuestras propias medidas

Política D-0091. Fecha 2026-11-19. Evidencias: E-0301, E-0302 y E-0303.

## 1. Qué hicimos y por qué
Durante días analicé las pruebas con scripts sueltos que tú no veías. Al convertirlos en una herramienta (un laboratorio dentro de la biblioteca) descubrí que **mi propio método tenía un sesgo**. Este informe cuenta cómo: instrumentar el análisis, no solo el dispositivo, es lo que permite encontrar errores del analista.

## 2. El concepto
- **Serie temporal con eventos:** una medida (corriente, cada 5 s) junto a los momentos en que el sistema cambia de estado (pantalla apagada, apagado de clúster, un dominio de energía que se corta). Sin los eventos, una curva no se puede interpretar.
- **Reloj de la medida:** los registros no llevan hora por línea; solo un latido cada minuto («alive N s») y una muestra cada 5 s. Se reconstruye el tiempo anclando en los latidos e interpolando.
- **Sesgo por etiquetado:** si clasificas las muestras («pantalla apagada» o «encendida») con una señal que llega tarde, las muestras del cambio caen en el grupo equivocado. Aquí el estado de la pantalla venía de una línea que sale **una vez por minuto**.
- **Bootstrap:** remuestrear los datos miles de veces para estimar cuánto puede variar una diferencia solo por azar y dar un intervalo de confianza sin suponer una distribución.
- **Superposición alineada:** dibujar varias pruebas en la misma gráfica, alineadas por un evento común (el apagado de la pantalla), quita la variable «cuánto llevaba encendido el sistema».

## 3. La evidencia (medido)
- El laboratorio analiza 34 pruebas con corriente de las 77 registradas, en menos de un segundo, y marca la pantalla con el **evento exacto** de apagado.
- **El sesgo existía:** con el etiquetado exacto, la mediana de min83 con la pantalla apagada pasa de 460 mA (n=35) a **474 mA (n=42)**. Las otras cuatro pruebas clave cambian menos de 2 mA (min80 506, min82 503, min84 492, min85 467).
- Por tanto, el «ahorro» del apagado de clúster en min83 respecto a la línea base se reduce de unos 45 mA a unos **32 mA**, y el A/B dentro de un mismo arranque (E-0301) ya decía que no era demostrable.
- Alineadas por el apagado de la pantalla, las curvas de min80 (sin reposo profundo), min83 (clúster siempre) y min85 (A/B) **se superponen dentro del ruido**: se ve a simple vista que el apagado de clúster no cambia la corriente.
- La escalera de dominios de min86 se **reproduce** con el etiquetado exacto: el escalón de la pantalla sigue en **−142 mA, intervalo [−158, −101]**; la ventana «antes», que tenía 2 muestras, ahora tiene 6.

## 4. Cómo defenderlo
**Pregunta posible:** ¿Qué error detectaste en tu propio análisis y cómo?
**Respuesta modelo:** Etiquetaba la pantalla como apagada con una línea del registro que se imprime solo una vez por minuto, así que las primeras muestras tras el apagado se contaban como «encendida» y la mediana de min83 salía unos 14 mA más baja. Lo descubrí al construir una herramienta que usa el evento exacto, y lo corregí con una evidencia nueva.

**Pregunta posible:** ¿Por qué alinear las curvas por el instante de apagado?
**Respuesta modelo:** Porque entre pruebas cambia cuánto llevaba encendido iOS; alinear por el apagado compara todas las curvas en la misma situación, y si se superponen, la diferencia entre configuraciones no es real.

**Pregunta posible:** ¿Qué conclusiones se mantienen y cuáles cambian tras la corrección?
**Respuesta modelo:** Se mantienen que los núcleos están ociosos, que el apagado de clúster no ahorra de forma demostrable y que el subsistema de pantalla es el consumo dominante (−142 mA). Cambia la cifra de min83, que se reduce de unos 45 a unos 32 mA frente a la línea base y deja de usarse como argumento.

**Pregunta posible:** ¿Por qué el análisis debe ser una herramienta y no un script suelto?
**Respuesta modelo:** Porque una herramienta con pruebas automáticas aplica siempre el mismo método, deja ver los datos a cualquiera y expone los fallos del método; un script de una sola vez los oculta.

**Error mío, para que conste:** usé una señal de baja frecuencia para etiquetar muestras de alta frecuencia durante varios análisis seguidos. Lección: antes de calcular, comprobar que la señal con la que se clasifica tiene la resolución temporal de lo que se clasifica.

## 5. Para profundizar
`app/lab.py` y `tests/test_lab.py` de la biblioteca, la página `/lab`, E-0303 y `docs/aprendizaje/20261119-apagar-un-cluster-y-medir-bien.md`.

# Informe de aprendizaje: el primer arranque de iOS y por qué no salía nada en pantalla

> *Informe retroactivo (D-0091), reconstruido a partir de `HEROLTE_PROGRESS.md` y del historial de Git. Este trabajo de octubre lo hizo el proyecto upstream y es la base heredada; las medidas son las que ese registro anota.*

## 1. Qué hicimos y por qué
Con la raíz de iOS en USERDATA se arrancó launchd por primera vez. Llegó al final del arranque temprano pero la pantalla no se actualizaba. Seguir el rastro llevó a tres causas distintas: un nombre en el ADT, falta de núcleos y un tamaño de pantalla incorrecto.

## 2. El concepto
- **launchd:** el proceso 1 de iOS; lanza el resto (SpringBoard, backboardd…). Si llega a «Early boot complete» el sistema de archivos y el kernel van bien.
- **Coincidencia por compatible:** el kernel empareja un controlador con un nodo del ADT por el texto de `compatible`. Un nombre distinto = driver sin hardware.
- **SMP por PSCI CPU_ON:** los núcleos secundarios se encienden pidiéndolo al firmware con una llamada estándar (PSCI) y una dirección de entrada.
- **Muestreo de hilos:** parar un proceso, leer la pila de cada hilo y simbolizarla con la caché de librerías, para saber dónde está esperando.

## 3. La evidencia (medido)
- **Causa 1:** SpringBoard abortaba en bucle (24 veces) con `bounds {0,0},{0,0}`. El nodo `disp0` decía `samsung,herolte-display` y AppleCLCD busca `samsung,a5xelte-display`. Corregido el ADT, backboardd configuró `1440x2560` y el aborto desapareció.
- **Causa 2:** el muestreo mostró el renderizado por CPU de QuartzCore (`CA::OGL::SW::scanline`) sin terminar el primer cuadro con un solo núcleo. Con los 4 A53 (`cpus=4`, parche 0208) el arranque fue notablemente más rápido.
- **Causa 3 (la última):** backboardd creaba superficies de 1440x2560 pero el tamaño mostrado era 1125x2436. Con el tamaño real del panel (`sweetfb_native=1`) aparecieron el logo y la pantalla «Hola» (2026-10-22).
- Medido: tras ajustar la raíz (sin migración ni CommCenter) hubo el primer `SwapEnd` de backboardd.
- No medido entonces: rendimiento. Todo iba muy lento.

## 4. Cómo defenderlo
**Pregunta posible:** ¿Cómo diagnosticaste que faltaba un núcleo y no un driver?
**Respuesta modelo:** Muestreé los hilos de backboardd y vi el rasterizador por CPU sin acabar el primer cuadro, y el latido del log seguía vivo, así que no estaba colgado. Con cuatro núcleos el mismo código avanzó.

**Pregunta posible:** ¿Por qué un cambio de una palabra en el ADT arregló SpringBoard?
**Respuesta modelo:** Porque iOS decide qué driver controla cada dispositivo por el texto `compatible`; sin coincidencia no había pantalla principal y SpringBoard abortaba al no tener límites de pantalla.

**Pregunta posible:** ¿Cómo se distingue un sistema colgado de uno lento?
**Respuesta modelo:** Con un latido periódico en el log persistente (`HEROLTE LOG: alive N s`): si sigue creciendo, el sistema corre.

## 5. Para profundizar
Parches `0206`-`0209`, `sweet_sample.c`, `tools/herolte-tune-ios-root.sh` y `tools/herolte-log-report.py`.

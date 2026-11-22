# Informe de aprendizaje: la pantalla a 60 Hz de verdad y el sonido

> *Informe retroactivo (D-0091), reconstruido a partir de `HEROLTE_PROGRESS.md` y del historial de Git. Este trabajo de octubre y principios de noviembre lo hizo el proyecto upstream y es la base heredada; las medidas son las que ese registro anota.*

## 1. Qué hicimos y por qué
iOS dibujaba 40-50 fotogramas por segundo pero la pantalla mostraba solo 20. Y el teléfono no tenía sonido. Se midió cada cosa hasta dar con su causa de reloj o de reset.

## 2. El concepto
- **DECON:** el controlador de pantalla del SoC; lee la memoria y envía las líneas al panel con un reloj de píxel (*vclk*).
- **Mux de reloj:** un selector que elige la fuente de un reloj. Si S-Boot lo deja en el oscilador de 26 MHz en vez del PLL de pantalla, el panel recibe datos muy lentos.
- **Resolución interna:** iOS se hizo dibujar a 750x1334 (iPhone 8) y la GPU escala al panel de 1440x2560; menos píxeles por CPU = más fluidez.
- **I2S y reset:** el bloque de audio digital arranca en reset; escribir en él sin quitar el reset **traba un núcleo**.
- **Gobernador y límites térmicos:** con la pantalla apagada se baja el clúster Mongoose a 728 MHz / 675 mV; con ≥ 80 C también.

## 3. La evidencia (medido)
- Con el vclk en el oscilador de 26 MHz: 363 ciclos por línea, **35,8 ms por cuadro**, un TE de cada tres, 20 Hz. Con el vclk en DISP_PLL (62,5 MHz): **14,88 ms por cuadro, período 16,74 ms (59,7 Hz)**, medido con el contador de líneas.
- No relacionados con el problema: eclk, relojes de bus y MULTI_PKT_CNT.
- Con 750x1334 la fluidez «mejora mucho». Mongoose a 2598 MHz / 1075 mV y GPU a 650 MHz medidos.
- Audio (`heroaudio=3`): el I2S necesita `CON_RSTCLR` (bit 31) antes de cualquier escritura. Probado: tono de llamada, teclado y barra de volumen.
- Térmico: cuatro sensores TMU; 31 C al arrancar, 45 C de pico. Sin pantalla: «Mongoose to 728 MHz».
- Sin resolver entonces: los cortes horizontales (un solo cuadro en memoria reescrito mientras DECON lo lee).

## 4. Cómo defenderlo
**Pregunta posible:** ¿Por qué 20 Hz si iOS dibujaba 40-50 fps?
**Respuesta modelo:** Porque el cuello de botella era el reloj de la pantalla: el multiplexor del vclk estaba en el oscilador de 26 MHz y cada cuadro tardaba 35,8 ms en enviarse. Con el PLL de pantalla bajó a 14,88 ms y salió 59,7 Hz.

**Pregunta posible:** ¿Cómo se midió el período de refresco?
**Respuesta modelo:** Con el contador de líneas de DECON (+0x8c) y el contador de tiempo del sistema, no con estimaciones.

**Pregunta posible:** ¿Por qué al tocar el I2S se trababa un núcleo?
**Respuesta modelo:** Porque el bloque está en reset hasta que se escribe el bit CON_RSTCLR; una escritura a un bloque en reset no completa el bus y el núcleo se queda esperando.

## 5. Para profundizar
Parches `0296`-`0303`, `0330`, `0331`, `gpu/hakios-audio`, `docs/S7GE_ENERGIA_TERMICA_ARQUITECTURA_20261117.md`.

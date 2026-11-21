# Informe de aprendizaje: dónde se gasta la batería de verdad

> *Informe retroactivo (D-0091), reconstruido a partir de `HEROLTE_PROGRESS.md`, el historial de Git y las evidencias de gobierno. Desde aquí el trabajo es del equipo de este repositorio.*

## 1. Qué hicimos y por qué
El teléfono se calentaba y la batería caía. En vez de suponer, se añadieron instrumentos al kernel (corriente, tensión, temperatura cada 5 s) y se probaron las palancas una por una.

## 2. El concepto
- **Potencia dinámica y estática:** P ≈ C·V²·f más las fugas; las fugas suben con la temperatura.
- **Governor (`herogov`):** política que baja la frecuencia y la tensión del clúster grande cuando casi no hay carga.
- **Dominios de energía:** bloques del SoC (cámaras, ISP, MFC…) que se pueden apagar si nada los usa.
- **Límite de entrada de un puerto USB:** ~500 mA; si el teléfono consume más, la batería baja aunque esté enchufado.

## 3. La evidencia (medido)
- 2288 frente a 2600 MHz de CPU y GPU 419 frente a 650: casi no cambian el consumo en uso (E-0285, E-0286).
- Con la pantalla encendida y la CPU casi ociosa: ~850 mA con el clúster a 1976-2288 MHz y ~480 mA a 728 MHz / 675 mV: **los núcleos ociosos fugan a tensión alta**.
- `herogov=1` funciona (41 cambios 728↔2288 MHz sin fallos) y ahorra ~150 mA en reposo.
- Los 9 dominios estaban encendidos; apagar seis (D-0088) ahorra solo **20-40 mA**. El Wi-Fi: ~120 mA con pantalla encendida; la pantalla ~45 mA.
- **Suelo de ~540 mA con la pantalla apagada** frente a 25-35 mA de Linux (TWRP) en el mismo teléfono (E-0288).
- Carga: cargador MAX77854 en 0x69; un puerto USB de PC entrega ~500 mA y con iOS el consumo los supera.
- No probado entonces: la carga inalámbrica con base.

## 4. Cómo defenderlo
**Pregunta posible:** ¿Por qué subir la frecuencia no mejoraba la batería ni la fluidez?
**Respuesta modelo:** Porque en reposo los núcleos ociosos a tensión alta fugan corriente, y en uso el cuello de botella no era la frecuencia de CPU. La medida lo mostró: 2288 y 2600 MHz casi no cambiaban el consumo.

**Pregunta posible:** ¿Qué demuestra que la diferencia con Linux es software?
**Respuesta modelo:** Que el mismo teléfono con Linux (TWRP) gasta 25-35 mA con la pantalla apagada y con iOS ~540 mA; el hardware es idéntico.

**Pregunta posible:** ¿Por qué no basta con apagar dominios?
**Respuesta modelo:** Porque se probó y solo ahorró 20-40 mA; la mayor parte del consumo está en la memoria, los relojes y la interconexión.

## 5. Para profundizar
Parches `0431`-`0436`, `docs/S7GE_ENERGIA_TERMICA_ARQUITECTURA_20261117.md`, evidencias E-0284 a E-0288.

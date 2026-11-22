# Informe de aprendizaje: botones, táctil y el coprocesador que enciende un sensor

> *Informe retroactivo (D-0091), reconstruido a partir de `HEROLTE_PROGRESS.md` y del historial de Git. Este trabajo de octubre lo hizo el proyecto upstream y es la base heredada; las medidas son las que ese registro anota.*

## 1. Qué hicimos y por qué
iOS estaba en pantalla pero sin entradas. Los botones eran fáciles (GPIO). El táctil no respondía porque su chip no tenía alimentación: encenderlo exigió hablar con un **coprocesador Cortex-M3** (APM) del SoC.

## 2. El concepto
- **GPIO activo en bajo:** un pin que vale 0 cuando el botón está pulsado; se lee con antirrebote.
- **I2C (HSI2C):** bus de dos hilos; el táctil `sec_ts` está en la dirección 0x48.
- **PMIC (S2MPS16):** el chip que genera las tensiones. Las LDO 32 y 33 alimentan el táctil.
- **APM (Cortex-M3):** un microcontrolador dentro del SoC con su propio firmware que S-Boot deja cargado pero detenido. Se libera y se le piden tareas por un **mailbox** (buzón de mensajes en registros).

## 3. La evidencia (medido)
- Botones: los cuatro llegan a iOS (`SWEET HID: key 0xe9/0xea/0x40/0x30`) tras el parche 0210.
- Táctil, primer intento: SDA/SCL e INT en bajo, el HSI2C quedaba en `trans=0x2000c`: el chip **sin alimentación**.
- Dos intentos de hablar con el PMIC directamente (0213, 0214) **congelaron el teléfono**.
- Sondeo de solo lectura (0215): APM `config=0x1 status=0x10000` (alimentado pero detenido), mailbox en 0 y la SRAM `0x11200000` con una tabla de vectores Cortex-M válida.
- Con el APM liberado (0216) respondió por mailbox: S2MPS16 `id=0x2`, escrituras en LDO32/33 con readback correcto, SDA/SCL suben y llegan toques de 0 a 4095.
- Con reintentos de lectura (0217): `moves=835 i2c_retries=6 lost_reads=0`.

## 4. Cómo defenderlo
**Pregunta posible:** ¿Por qué no encendiste el táctil escribiendo directamente en el PMIC?
**Respuesta modelo:** Lo intenté (parches 0213 y 0214) y congelaron el teléfono; Linux no lo hace así en este SoC, sino a través del APM. El sondeo de solo lectura mostró que el firmware del APM ya estaba en memoria.

**Pregunta posible:** ¿Qué es un mailbox y por qué hace falta?
**Respuesta modelo:** Es un conjunto de registros compartidos entre la CPU y el microcontrolador para pasarse mensajes. Hace falta porque el control del PMIC lo posee el APM, no el procesador principal.

**Pregunta posible:** ¿Cómo sabes que el táctil estaba sin alimentación y no mal programado?
**Respuesta modelo:** Los pines SDA/SCL e INT estaban en bajo y la FIFO del HSI2C no avanzaba; tras encender las LDO subieron a alto y el chip contestó con su identificador.

## 5. Para profundizar
Parches `0210`-`0217`, `bsd/dev/herolte_touch.c`, `docs/S7GE_APM_TOUCH_ARRANQUE_FRIO_20261117.md`.

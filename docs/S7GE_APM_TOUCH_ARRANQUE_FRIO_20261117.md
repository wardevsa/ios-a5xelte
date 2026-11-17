# Táctil muerto tras un apagado real (herohalt=3): el APM sin firmware (17-nov-2026)

Observación del Director (L0): con min50 (`herohalt=3`) el teléfono se apaga de verdad; al encenderlo en frío, el táctil no funciona; arrancando desde TWRP sí.

Log (L2, `phase1-20261114/min50c-herolog.txt` frente a `min50-herolog.txt`):

| | arranque desde TWRP (bueno) | arranque en frío tras apagado real (malo) |
|---|---|---|
| SRAM del APM | `00004000 0000009d 000001b9 …` (tabla ordenada) | `5488fa06 78b680e8 9416a3a7 …` (aleatorio) |
| mensaje al PMIC | `S2MPS16 id=0x2 L32CTRL=0x2e L33CTRL=0x3c` | `APM: no answer: tx=0x1 rxirq=0` y `S2MPS16 read failed` |
| táctil | alimentado (LDO32/33) | `TOUCH: no supply; stopping` |

Lectura: el microcontrolador de energía (Cortex-M3, «APM») recibe su firmware de quien arranca antes; Linux (TWRP) lo carga en su SRAM. En un arranque en frío la SRAM no está inicializada y el M3 no responde, de modo que el kernel de iOS no puede encender las alimentaciones del táctil por el buzón (APM) que usa. Es una hipótesis con buen respaldo, no una demostración: no se ha leído el código de S-Boot.

Consecuencias:
- `herohalt=1` (apagar = reiniciar a TWRP) es el valor seguro; `herohalt=3` rompe el táctil hasta pasar por TWRP. min51 vuelve a `herohalt` por defecto.
- Para un apagado real utilizable hace falta que el kernel cargue el firmware del APM él mismo (origen probable: la partición VENDOR/firmware de Android, como el de Wi-Fi; falta localizarlo) o encontrar otro camino a las alimentaciones del táctil (S2MPS16 por I2C directo, sin el APM).
- Aviso: cualquier arranque en frío (batería agotada, apagado a la fuerza) deja el táctil muerto hasta que se pase por TWRP.

# Informe de aprendizaje: ocho núcleos, una dirección MAC y por qué iOS se quedaba en el logo

> *Informe retroactivo (D-0091), reconstruido a partir de `HEROLTE_PROGRESS.md` y del historial de Git. Este trabajo de octubre lo hizo el proyecto upstream y es la base heredada; las medidas son las que ese registro anota.*

## 1. Qué hicimos y por qué
Con la pantalla de inicio funcionando faltaba lo que la hacía usable: los ocho núcleos, las apps y la batería. Un fallo sutil (una dirección MAC ausente) dejaba el sistema en el logo.

## 2. El concepto
- **big.LITTLE:** cuatro Cortex-A53 (clúster de arranque, MPIDR 0x100-0x103) y cuatro Mongoose (MPIDR 0x0-0x3). Los Mongoose son los lógicos 4 a 7.
- **Contador común:** para sincronizar temporizadores hace falta un contador de tiempo compartido entre clústeres.
- **UDID y MobileGestalt:** iOS calcula un identificador único a partir de datos del hardware; si falta una MAC espera sin límite.
- **Compresor de memoria:** XNU reserva espacio proporcional a la RAM; el límite se ajusta con `vm_compression_limit`.
- **Páginas de 16 KiB sobre 4 KiB:** el XNU de iOS espera páginas grandes; el shim del S7 pagina en 4 KiB y eso causa errores de alineación.

## 3. La evidencia (medido)
- `8/8 CPUs initialized`; contador común con diferencia < 1 ms y temporizadores que despiertan en los 8 (21 ms sobre 20).
- Los Mongoose reportan `midr=0x531f0011` y línea de caché de instrucciones de 128 B frente a 64 B en los A53.
- Con todas las apps el arranque se quedaba en el logo: `lsd` no terminaba la base de LaunchServices porque MobileGestalt esperaba para siempre `mac-address-bluetooth0`. Con MACs sintéticas en el ADT (`02:48:45:52:4f:0x`) aparecieron los iconos.
- Batería: fuel gauge MAX77854 en `0x36`; lecturas reales 100 %, 4339 mV (+114 mA con cargador) y 4043 mV (−749 mA sin él).
- RAM: segundo banco de DRAM en `0x880000000`. Con 2 GiB, pánico en `kmem_range_init`; con 1 GiB arrancaba; con `--bank2-mb 1536` y `vm_compression_limit=98304`, **1,5 GiB estable**. Los secundarios no llegaban con entrada sobre 4 GiB y se resolvió con un trampolín en `0x8fffe000`.

## 4. Cómo defenderlo
**Pregunta posible:** ¿Por qué un nodo ausente del ADT dejaba el sistema en el logo?
**Respuesta modelo:** Porque MobileGestalt calcula el UDID con la MAC de Bluetooth y esperaba para siempre un dato que no estaba en `/chosen`; `lsd` dependía de eso para sembrar la base de apps. Con MACs sintéticas el cálculo terminó.

**Pregunta posible:** ¿Por qué los núcleos secundarios no arrancaban con RAM sobre 4 GiB?
**Respuesta modelo:** CPU_ON recibía una dirección de entrada de 64 bits que el firmware no manejaba; se resolvió con un trampolín por debajo de 4 GiB (0x8fffe000).

**Pregunta posible:** ¿Qué es lo que impidió usar los 2 GiB del segundo banco?
**Respuesta modelo:** Dos cosas: el compresor de XNU reserva 16 veces la RAM y no cabía en el rango virtual, y después aparecían PTE sin alinear al paginar a 4 KiB lo que XNU espera a 16 KiB.

## 5. Para profundizar
Parches `0218`-`0224`, `tools/mkadt_herolte.py`, `bsd/dev/herolte_battery.c`.

# Informe de aprendizaje: la cadena de arranque y el primer XNU en el S7

> *Informe retroactivo (D-0091), reconstruido a partir de `HEROLTE_PROGRESS.md` y del historial de Git. Este trabajo de octubre lo hizo el proyecto upstream y es la base heredada; las medidas son las que ese registro anota.*

## 1. Qué hicimos y por qué
Antes de portar nada había que saber si el cargador de Samsung (S-Boot) ejecutaría código nuestro. Primero se escribió un programa mínimo (*probe*) que dibuja texto y reinicia; después un cargador (`xnu_boot`) que entrega el kernel de Apple con su árbol de dispositivo. El primer XNU llegó a arrancar y se detuvo con un pánico instructivo.

## 2. El concepto
- **Cadena de arranque:** BootROM → S-Boot (cargador de Samsung) → nuestra imagen en la partición BOOT → XNU. Cada eslabón solo confía en el anterior y se salta nada: por eso el kernel de Apple no arranca solo.
- **Imagen arm64:** un archivo con una cabecera (`text_offset` 0x80000) que dice dónde cargarlo. S-Boot espera el formato de imagen de arranque de Android con una tabla de árboles de dispositivo (DTBH, tres DTB para distintas revisiones de placa).
- **Árbol de dispositivo (ADT):** XNU no descubre el hardware; se lo describe una tabla. Apple usa su ADT, no el DTB de Linux, así que `mkadt_herolte.py` fabrica uno para el S7.
- **MPIDR:** el identificador de cada núcleo. El A5 arrancaba con 0x0 y el S7 con 0x100 (clúster 1, núcleo 0); el kernel suponía lo primero.
- **Atómicas LSE:** instrucciones de Armv8.1 que los Cortex-A53 de este chip no tienen. Si el kernel contuviera una, fallaría.

## 3. La evidencia (medido)
- El *probe* mostró texto sobre el logo y reinició a recuperación: S-Boot ejecutó nuestra imagen y el reinicio por PMU funciona.
- Foto del *probe*: EL1, MMU apagada, MIDR 0x410fd034 (Cortex-A53), MPIDR 0x80000100, sin LSE, CNTFRQ 0 (la frecuencia, 26 MHz, viene del ADT).
- El primer kernel compilado en CI (61 MB) pasó el chequeo de LSE: la única coincidencia estaba en `K256`, constantes de SHA-256, es decir, datos.
- Primer arranque de XNU: consola en pantalla, `platform expert iniciado` y pánico `unsupported topology cpu=0 mpidr=0x100`. Se arregló con un parámetro de placa (parche 0203).
- Hipótesis, no medida entonces: que el resto del kernel no dependiera de más suposiciones del A5.

## 4. Cómo defenderlo
**Pregunta posible:** ¿Cómo sabes que S-Boot ejecutó código vuestro y no uno suyo?
**Respuesta modelo:** Porque el programa mínimo dibujó su propio texto sobre el logo, mostró registros que solo podía leer código en ejecución (EL1, MPIDR, MIDR) y reinició a recuperación escribiendo en el PMU, algo que S-Boot no hace por sí solo.

**Pregunta posible:** ¿Por qué no puede haber instrucciones LSE en el kernel?
**Respuesta modelo:** Porque los Cortex-A53 de este SoC implementan Armv8.0 sin LSE; una de esas instrucciones produciría una excepción de instrucción no definida. Por eso el CI inspecciona el binario y solo admite coincidencias que sean datos.

**Pregunta posible:** ¿Por qué entró en pánico el primer XNU?
**Respuesta modelo:** El código de arranque comprobaba que el núcleo inicial tuviera MPIDR 0x0, valor del A5, y en el S7 es 0x100. Se convirtió en constante de placa.

## 5. Para profundizar
`shim/herolte/probe.S`, `tools/herolte-pack-boot.py`, `tools/mkadt_herolte.py`, `docs/herolte-bringup.md` y el parche `0203-herolte-boot-mpidr`.

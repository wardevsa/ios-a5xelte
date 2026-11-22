# Informe de aprendizaje: cómo se instala software en el teléfono sin poder romperlo

> *Informe retroactivo (D-0091), reconstruido a partir de `HEROLTE_PROGRESS.md`, el historial de Git y las evidencias de gobierno. Desde aquí el trabajo es del equipo de este repositorio.*

## 1. Qué hicimos y por qué
El primer paso del proyecto propio no fue arrancar nada: fue asegurar que un fallo no pudiera dejar el teléfono inservible. Dos piezas: copias verificadas de las particiones críticas y un mecanismo de instalación que sobrevive a un corte de corriente (DROP v2).

## 2. El concepto
- **Particiones críticas:** BOOT (lo que arranca), EFS (datos del módem, incluido el IMEI, irrecuperables si se pierden), RECOVERY y los cargadores. Tocar mal EFS puede dejar el teléfono sin red para siempre.
- **Zona DROP:** una carpeta en USERDATA donde se dejan paquetes (hero-run, librerías, fondos) que el kernel instala en el siguiente arranque.
- **Atomicidad:** una operación que o se completa entera o no cambia nada. Se consigue escribiendo en una zona temporal (*staging*), marcando que está completa con un estado duradero y haciendo el cambio final con `rename`.
- **`fsync` en HFS+:** no vacía el journal ni la caché del disco, y HFS pierde el error de `DKIOCSYNCHRONIZE`; por eso un `fsync` simple no da durabilidad.
- **Escalera de riesgo:** N1 solo el *probe*; N2 XNU arranca en solo lectura; N3 instalación completa (USERDATA y Android se pierden).

## 3. La evidencia (medido)
- Copias verificadas fuera del repositorio de BOOT, EFS, CPEFS, PERSISTENT, PARAM, PERSDATA, RECOVERY, BOTA0 y BOTA1.
- El teléfono de pruebas (SM-G930F, bootloader `G930FXXU8EVG3`, TWRP 3.7.0) tenía BOOT con el Android original de Samsung y USERDATA en ext4.
- DROP v2: paquete con SHA-256 y generación, estado atómico, `STAGED` duradero antes de tocar destinos, recuperación hacia delante y 3 intentos. Probado **en el ordenador** con cortes de corriente simulados, fallo de cada barrera y doble fallo.
- **Sin compilar en CI y sin probar en el teléfono** cuando se redactó este informe: la afirmación es del modelo y de las pruebas de anfitrión, no del dispositivo.

## 4. Cómo defenderlo
**Pregunta posible:** ¿Por qué no basta con `fsync` al instalar un paquete?
**Respuesta modelo:** Porque en HFS+ no vacía el journal ni la caché del dispositivo y el error de sincronización se pierde; un corte podría dejar el archivo a medias sin que nadie se entere.

**Pregunta posible:** ¿Qué hace que la instalación sea atómica?
**Respuesta modelo:** Se prepara todo en una zona temporal, se marca el paquete como preparado de forma duradera y el cambio real se hace con `rename`, que es todo o nada; si hay un corte, la recuperación avanza hacia delante desde el estado guardado.

**Pregunta posible:** ¿Por qué se copió EFS y qué pasa si se pierde?
**Respuesta modelo:** Contiene datos del módem como el IMEI y no se puede regenerar; por eso se verificó la copia y la regla del proyecto es no escribir nunca en EFS.

## 5. Para profundizar
`xnu/drop-v2/`, `tools/herolte-drop.py`, `docs/estado-y-camino-a-flashear.md`, `docs/herolte-dma-smp-analysis.md`.

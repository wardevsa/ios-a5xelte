# Análisis de min35 (kernel 0359): valores por defecto, perfil de backboardd y estado real del Wi-Fi

Log: `~/HackiOS/builds/device-day/phase1-20261114/min35-herolog.txt` (privado, 394 962 B, 5 914 líneas, 300 s de vida). Evidencia E-0256. Observación del Director: «el Wi-Fi se enciende pero no detecta redes, y puse mi red escribiéndola y nada; por lo demás bien».

## 1. ¿Funcionan los valores por defecto de 0359? Sí (L2)
Con una línea de 536 caracteres (69 menos que min34) el sistema se comportó igual que min34: `HEROLTE GPU PRESENT` y fps medio 10,3 (min34: 11,2) con muestreo cada 2 s activo, Mongoose 2600 MHz, GPU 650 MHz, SoC máx. 45 °C, `hfs: set hardlink` = 8 líneas, `FBP` = 384 líneas, capa GL en `backboardd` y `libherosb` en `SpringBoard`. No aparece ningún anillo de texto (el Director no lo menciona). Memoria libre mínima 412 MB.

## 2. Wi-Fi: la premisa «herowifi=1 funciona» no es correcta
La directiva de análisis recibida parte de que `herowifi=1` está activo. **No lo está y nunca lo ha estado en ninguna de las imágenes de hoy**: min17-min34 llevaban `herowifi=0` y, desde el parche 0359, el valor por defecto es 0 (`bsd/dev/herolte_gpu.c`, `int wifi = 0`). Lo que el log muestra:

| Línea del log | Significado |
|---|---|
| `HEROLTE WIFI: en0 made, its address the ADT's mac-address-wifi0; the radio comes later` | existe la interfaz `en0` pero **la radio no se ha iniciado** (L2) |
| `apple80211: wifid gets 19 (POWER) … answered` ×12 | el interruptor de Wi-Fi «se enciende» porque nuestro stand-in `HakiosWLAN` (`iokit/Kernel/arm/SweetWLAN.cpp`) contesta que sí |
| `gets 254 (HW_SUPPORTED_CHANNELS)` y `27 (SUPPORTED_CHANNELS)` → `error 6`; `gets 103 (CURRENT_NETWORK)` y `1 (SSID)` → `error 6`; `gets 51 (COUNTRY_CODE)`, `sets 383`, `gets 115` → `REFUSED` | no hay lista de canales, ni país, ni red actual: **iOS no tiene nada que escanear** |
| `HakiosWLAN: a user client of type 0 is asked for: there is none` ×4 | wifid pide un cliente de usuario que no existe |
| `exec wifip2pd` ×28 | wifip2pd se relanza en bucle (mismo origen) |
| `wifid` ~5 % de CPU de media | wifid sigue intentándolo |

Por tanto **las hipótesis H1-H5 de la directiva (firmware, NVRAM, país, alimentación, driver) son prematuras**: ninguna de esas piezas llegó a ejecutarse. Lo que falta es lo siguiente, y el código ya existe en el kernel:

1. **Los ficheros del firmware, que no están en la zona DROP** (`wifi/fw.bin`, `wifi/clm.blob`, `wifi/nvram.txt` y `wifi/network.txt`). El hilo `hg_wifi_thread` (herolte_gpu.c) espera hasta 120 s a `herolte_wifi_files_ready()`, luego levanta el BCM4359 por PCIe (canal 0, FSYS1, como Linux `pci-exynos.c`), carga el firmware (`bsd/dev/herolte_wifi.c`) y arranca la pila.
2. **`herowifi=1`** en la línea de arranque (hoy es 0).
Evidencia externa (upstream, L4h, no medida aquí): «0315 en el teléfono: Wi-Fi a 1 s de tener los archivos, conecta en 1,6 s» (`HEROLTE_PROGRESS.md`).
Riesgos reales: el hilo toca GPIO, relojes, PMU y PCIe por primera vez en esta unidad; el firmware es del propio teléfono (partición VENDOR) y `network.txt` lleva la contraseña de la red del Director (nunca va a git ni al log).

## 3. Perfil de backboardd: el muestreador del kernel no sirve para esto
| Medida | Resultado |
|---|---|
| TOP (61 muestras de 5 s) | backboardd **128 % de media**, máx. 615 %; SpringBoard 29 % (máx. 431 %); Preferences 13 %; kernel_task 8 % |
| Muestras densas (40, una cada ~2 s) | 809 muestras de hilos de backboardd: **13 fuera de las esperas del kernel** (1,6 %) |
| Correlación | incluso donde TOP dice 183-385 % de backboardd, el muestreo ve 0-1 hilos ejecutando |
Conclusión (L2 medido, causa en hipótesis): el muestreador lee el contexto **guardado** de cada hilo; en un hilo que está ejecutando en ese momento ese contexto es el de su última entrada al kernel (viejo), así que la CPU de los hilos activos no aparece. **No hay hotspots que reportar; no se debe inventar ninguno.** Dos medidas posibles: (a) el parche `0360` (`xnu/patches/0360-herolte-top-system-time.patch`, sin CI aún) añade a cada línea TOP el tiempo de **sistema**: si la mayoría del tiempo de backboardd es sistema, se gasta en llamadas al kernel (la espera por sondeo de HeroGPU), no en código de dibujo; (b) un muestreador con IPI a los núcleos que ejecutan (más trabajo).

## 4. Experimentos de fluidez (a partir de esta medida)
| # | Cambio | Qué prueba |
|---|---|---|
| 0360 | TOP con tiempo de sistema | si el cuello es kernel (HeroGPU/IOKit) o espacio de usuario |
| E1 | `a5fb_hz=30` | menos trabajo desperdiciado si el sistema da ~10 fps |
| E2 | `heroquantum=500` | rodajas más cortas |
| E3 | `heronoexec += wifid,identityservicesd` (sin radio, wifid no sirve de nada) | -5 % de CPU y picos de 30 % |
| E4 | `herocpu_mhz=2288` | calor frente a rendimiento |
Cabida en la línea de arranque: 536 caracteres hoy; E1-E3 suman ~60. Orden: **min36 = 0360 + E1-E3 en un lote con rollback a min34/min35**; Wi-Fi en una imagen aparte (min37) para no mezclar variables.

## 5. Plan de Wi-Fi (cada paso rojo con su firma, ya sin la precondición de la copia, D-0076)
1. **Extraer el firmware del propio teléfono** (TWRP, VENDOR en solo lectura): `tools/herolte-wifi-extract.sh adb DIR --execute` (prueba en seco: sin `--execute`; probado con un `adb` falso, `tools/test_wifi_extract.py`, 3 pruebas OK). Monta `by-name/VENDOR` con `-o ro`, comprueba que es de solo lectura, copia 3 ficheros, desmonta; `DIR` con modo 700, ficheros 600, sin git.
2. **`network.txt`** (nombre de la red en la 1.ª línea, contraseña WPA2 en la 2.ª): lo escribe el Director en su PC; el ingeniero no la ve ni la registra.
3. **Paquete DROP con `wifi/`** (zona de USERDATA, firma con hash) y **min37 con `herowifi=1`** (BOOT, firma con hash).
4. Prueba: `HEROLTE WIFI: …` en el log (enlace PCIe, `chip id`, firmware cargado) y detección de redes en Ajustes.

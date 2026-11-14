# HEROLTE: periféricos — qué funciona, qué hay en el hardware y qué es viable

Análisis del 2026-11-12. **No se ha escrito nada en el teléfono.** Fuentes: el registro del proyecto (`HEROLTE_PROGRESS.md`), el
árbol de dispositivos *vivo* de un S7 (SM-G930F, leído en TWRP: `/sys/firmware/devicetree`), el listado de firmware de su partición
VENDOR (solo nombres), el kernel Linux de LineageOS para el 8890 (`LineageOS/android_kernel_samsung_universal8890`, `lineage-18.1`) y el
README público de `ios-flame` (Pixel 4). Lo que es hipótesis se marca como tal.

## 1. Estado de lo que ya está en el proyecto
| Función | Estado | Evidencia |
|---|---|---|
| Pantalla, GPU (Mali-T880), 8 núcleos, UFS, RAM (2–3 GiB) | funciona | `HEROLTE_PROGRESS.md`, `docs/herolte-howto.md` |
| Táctil (`sec_ts` 0x48), botones, batería (MAX77854) | funciona | parches 0210–0220 |
| Altavoz (MAX98506 por I²S) | funciona | `heroaudio=3`, 0278–0303 |
| **Wi-Fi** | **funciona de extremo a extremo** | 0304–0315: firmware en TCM, **WPA2 con supplicant propio en el kernel**, `en0`, DHCP, `wifid`; `en0 so far 9391 frames sent, 11076 received`; conecta en 1,6 s |
| Micrófono / auricular | sin evidencia | el codec Cirrus `cs47l91` solo tiene un sondeo SPI (0278) |
| Bluetooth, cámaras, sensores, módem, reposo, Metal (desenfoques) | **no funcionan** (según la guía) | `docs/herolte-howto.md` |
| GPS, NFC, huella, vibración, USB de datos | no mencionados | no hay parches |

Límites conocidos del Wi-Fi: una red fija (`network.txt`), solo WPA2, y el firmware de Samsung no trae supplicant. No he podido
comprobar si Ajustes → Wi-Fi permite elegir redes ni 5 GHz en uso real (el escaneo sí vio redes de 5 GHz).
**Aviso de variante de módulo:** este teléfono trae dos juegos de ficheros (`nvram.txt_c0_plus` y `nvram.txt_murata_c0_plus`,
`bcm4359C0_semco.hcd` y `bcm4359C0_murata.hcd`). Hay dos módulos Wi-Fi/BT posibles según la unidad y la guía fija el primero.
Si la unidad es Murata, el `nvram` correcto es el otro. Comprobarlo antes de dar un fallo de Wi-Fi por bueno.

## 2. Hardware real de este teléfono (árbol de dispositivos vivo)
| Bloque | Dispositivo | Dónde |
|---|---|---|
| Cámara trasera | **Sony IMX260** o **Samsung S5K2L1** (dos variantes según unidad), enfoque `af@0c`, estabilizador `rumba,ois@24` | I²C `0x34` / `0x5A`; ISP FIMC-IS `0x14370000`; PHY CSI `0x144F1040`, `0x145F1050` |
| Cámara frontal | Samsung **S5K4E6** (+ EEPROM) | I²C `0x6A` |
| Alimentación de cámara (probable) | `s2mpb02`, `max77838` | HSI2C `0x13680000`, `0x13690000` |
| Bluetooth / GNSS | **BCM4359** (BT; por UART, probable) y **BCM4753** (GPS) | nodos `bluetooth`, `gps` |
| Sensores | hub **BCM4773** (`ssp`) en SPI `0x14d30000`; HRM `max86900`, `adpd143`; `sx9310` (agarre); sensor Hall | I²C `0x13670000`, `0x14E60000` |
| Audio | codec **Cirrus cs47l91** (SPI `0x14d20000`), amplificador `max98506` | — |
| USB | **DWC3** USB3 DRD en `0x15400000`, PHY `0x15500000` (`exynos8890-usbdrd-phy`) y USB2 host `0x15510000` | — |
| Otros | NFC `sec-nfc@27`, eSE, huella `vfs7xxx` o `et320` (según unidad), carga inalámbrica `p9220`, teclas táctiles `abov`/`cypress` | — |
Los dos táctiles `sec_ts@48` y `stm,fts_touch@49` aparecen en el árbol: el proyecto usa el primero.

Firmware presente en la VENDOR de la unidad (solo nombres): `bcm4359C0_{semco,murata}.hcd` (parche del BT), `fimc_is_fw2_{2l1,imx260}.bin`,
`companion_fw_*`, `setfile_*`, `ois_fw_*` (cámara), `mfc_fw.bin` (códec de vídeo), `seiren_fw_*` (DSP de audio). **No hay** firmware del
hub de sensores BCM4773 ni del codec `cs47l91` en VENDOR.

## 2b. Qué trae el kernel real de Apple (kernelcache de iPhone10,3, iOS 16.7.16 — hechos, 2026-11-12)
Leído de las cadenas del kernelcache público del IPSW (el binario de Apple se queda fuera de git). Muestra qué clases de IOKit espera el
userland de iOS que existan en el kernel; este proyecto **no carga los kexts de Apple**, así que cualquier función que dependa de ellos
tiene que reimplementarse como servicio propio.
| Función | Clases en el kernelcache de Apple | Lectura |
|---|---|---|
| Cámara | `AppleH10CamIn` (≈750 referencias), `AppleH10CamInUserClient`, `AppleH10CamInFrameReceiver`, `AppleH10CamInFirmwareWorkProcessorRPCRequest`, `AppleH10CameraInterface` | la captura de iOS es la ISP del A11 con un RPC a su propio firmware: **incompatible** con una ISP de Samsung. Descartada como función del sistema |
| Movimiento / luz | `AppleSPU`, `AppleSPUHIDDriver`, `AppleSPUAppDriver`, `AppleSPUALSColorDriver`, `AppleSPUSphere*`, `AppleSPUFirmwareService` | los sensores llegan por el procesador siempre activo (SPU) como servicios HID. Un servicio HID sintético alimentado desde el hub BCM4773 es una vía plausible (**el formato exacto de los informes HID está por confirmar**) |
| Bluetooth | `AppleBluetooth`, `AppleBluetoothModule`, `AppleBluetoothDebug`, `AppleBluetoothVoice`; **sin** clases `IOBluetooth*` | el kernel solo aporta el transporte; la pila está en `bluetoothd`. Hace falta un servicio propio con ese nombre y un cliente de usuario compatible (selectores por confirmar leyendo `bluetoothd`) |
| USB en modo dispositivo | `IOUSBDeviceFamily`, `IOUSBDeviceController`, `AppleSynopsysOTGDevice`, `AppleUSBDeviceNCM`, `AppleUSBDeviceMux` | iOS trae su propia pila (incluido NCM y `usbmuxd`), pero depende de esos kexts; la vía realista sigue siendo el ECM propio del donante (`docs/herolte-usb-plan.md`) |
Con esto las tres hipótesis anteriores quedan resueltas: cámara = descartar, sensores = servicio HID sintético, Bluetooth = servicio propio fino (la opción
más abordable de las tres).

## 3. Viabilidad y prioridad (criterio: valor / esfuerzo / riesgo)
| # | Función | Veredicto | Por qué |
|---|---|---|---|
| 1 | **USB en modo dispositivo (red ECM + log en vivo)** | **hacer primero** | multiplicador de productividad: hoy cada prueba exige volver a TWRP para leer el log. Ya existe una pila completa heredada de SWEET (parches **0072–0081**: DWC3 en modo dispositivo, EP0, CDC-ECM, interfaz `ue0`, log en vivo por UDP 5140) que NOTES.md documenta funcionando en el Redmi. Está dentro de `#if ARM64_BOARD_CONFIG_SWEET`, que HEROLTE no define, así que **hoy no se compila**. Cambia lo específico de Qualcomm: anulación de VBUS (`QSCRATCH`) y relojes, por la PHY `usbdrd` del Exynos (`phy-exynos-usbdrd.c`, ~970 líneas en Linux: relojes `aclk/sclk/phyclock`, aislamiento por PMU, `PHYCLKRST`, referencia de reloj) y la detección de cable (probablemente el MUIC del MAX77854; por confirmar en el DT). `ios-flame` ya hizo lo mismo (USB Ethernet + SSH + servidor de ficheros). |
| 2 | Wi-Fi: elección de red y WPA3 | opcional | funciona; mejoras de comodidad, no bloqueantes |
| 3 | **Micrófono / auriculares** | medio | el codec `cs47l91` (Madera) por SPI; sin firmware en VENDOR (hay que ver si se carga desde otra parte); necesario para Siri/notas de voz |
| 4 | **Bluetooth** | medio | lado hardware abordable: HCI por UART + parche `bcm4359C0_*.hcd` (hay dos variantes). El obstáculo está en iOS: `bluetoothd` espera el servicio `AppleBluetooth` que este kernel no tiene (**confirmado** en el kernelcache; falta el contrato exacto del cliente de usuario). Es la más abordable de las tres |
| 5 | **Sensores (acelerómetro, giroscopio, proximidad, luz)** | difícil | todo pasa por el hub BCM4773 (protocolo SSP, código GPL en `drivers/sensorhub/brcm`) y no hay firmware en VENDOR; en iOS el movimiento llega por servicios HID del SPU (`AppleSPUHIDDriver`, **confirmado**; formato de informes por confirmar) |
| 6 | Reposo | medio | sin PSCI de suspensión ni gestión de PMIC; hay un reposo parcial (0330) |
| 7 | Vibración | fácil-medio | motor por el PMIC; sin interfaz iOS claro |
| 8 | **Cámara** | **muy difícil, no priorizar** | cadena ISP propietaria (FIMC-IS + companion + OIS + setfiles) con firmware de Samsung, y iOS necesita `AppleH10CamIn`, la ISP del A11 con su propio firmware (**confirmado**). `ios-flame` tampoco la tiene. Una vía realista sería una app propia que lea fotogramas crudos por un cliente IOKit propio, no la app Cámara |
| 9 | Módem, GPS, NFC, huella | inviable / no | módem Shannon con interfaz propietaria; la huella necesita el SEP de Apple |

## 4. Trabajo de bajo riesgo que se puede hacer sin tocar el teléfono
1. Escribir `bsd/dev/herolte_usb.c` reutilizando 0073/0075/0076/0077 y la PHY de Exynos (se compila y se prueba contra cabeceras simuladas,
   como se hizo con DROP v2; el arranque real necesita una prueba en el dispositivo, con el jefe).
2. ~~Leer el kernelcache~~ **hecho** (§2b). Siguiente: leer `bluetoothd` y el kext `AppleBluetooth` para sacar el contrato del cliente de usuario
   (selectores y colas HCI/ACL), que es lo que falta para estimar el Bluetooth. Los binarios de Apple se quedan fuera de git.
3. Anotar en la guía de instalación la variante de módulo Wi-Fi/BT y cómo reconocerla.

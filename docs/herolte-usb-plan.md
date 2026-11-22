# HEROLTE: USB en modo dispositivo (red + log en vivo) — plan

Estado: **solo investigación, sin código ni pruebas.** Objetivo: acabar con el ciclo "probar → TWRP → leer el log" haciendo que el
teléfono publique su consola del kernel por UDP sobre USB-Ethernet, como ya hace el donante SWEET y como hace `ios-flame` (Pixel 4).

## Lo que ya existe
Parches heredados `0072`–`0081` → `bsd/dev/sweet_usb.c` (≈930 líneas finales): DWC3 en modo dispositivo con cola de eventos propia (sin
interrupción), EP0 (máquina de control como Linux `ep0.c`), CDC-ECM (bulk 0x01/0x81 + interrupción 0x82), interfaz `ue0` con IP fija
`192.168.7.2/24` creada desde el kernel, y un hilo que envía la consola cada 100 ms por UDP a `192.168.7.1:5140`. Cliente en el PC:
`tools/sweet-usbnet.sh`. NOTES.md documenta que funcionó en el Redmi (ping ~1 ms, 0 % de pérdidas).
**Hoy no se compila para el S7:** todo va dentro de `#if defined(ARM64_BOARD_CONFIG_SWEET)`, que HEROLTE no define.

## Hechos verificados del S7 (árbol de dispositivos vivo de una unidad, en TWRP)
| Dato | Valor |
|---|---|
| Núcleo | `usb@15400000`, `samsung,exynos8890-dwusb3` + hijo `synopsys,dwc3`, `reg 0x15400000 / 0x10000` |
| Modo / velocidad | `dr_mode = otg`, **`maximum-speed = high-speed`** (basta alta velocidad: no hace falta USB 3) |
| Interrupción | SPI 213 (el donante sondea eventos: no hace falta) |
| PHY | `phy@15500000` (`samsung,exynos8890-usbdrd-phy`, `reg 0x15500000 / 0x100`), `samsung,pmu-syscon`, `use_additional_tuning` |
| Relojes (CMU FSYS0) | `aclk`=700, `sclk`=703, `phyclock`=708, `pipe_pclk`=709 (índices de `exynos8890.h`), más `ext_xtal` para la PHY |
| Aislamiento PHY | PMU `0x105c0000` + `USBDRD_PHY_CONTROL` `0x704` (en Linux `EXYNOS5_USBDRD_PHY_CONTROL`) |
| Código de referencia | Linux (LineageOS `android_kernel_samsung_universal8890`, `lineage-18.1`): `drivers/phy/phy-exynos-usbdrd.c` (≈970 líneas), `phy-samsung-usb3-cal.c` (≈740; `samsung_exynos_cal_usb3phy_enable`, ≈240 líneas, depende de la **versión** del IP), `drivers/usb/dwc3/dwc3-exynos.c` |

## Estado de un DWC3 funcionando en este teléfono (volcado de `debugfs` del kernel de TWRP, solo lectura)
Medido con el teléfono en recovery y el cable conectado (el `adb` de TWRP usa este mismo controlador): `mode = device`, `link_state = U0`.
| Registro | Valor | Lectura |
|---|---|---|
| `GSNPSID` | `0x5533280a` | **DWC_usb3 v2.80a** (el donante SWEET era v3.20a, `0x5533320a`: mismo mapa, pero hay que revisar diferencias de versión) |
| `GCTL` | `0x80e92004` | modo dispositivo (PRTCAPDIR = 2) |
| `DCFG` / `DCTL` / `DSTS` | `0x00480808` / `0x8c000a00` / `0x0083db70` | alta velocidad (DEVSPD = 0, CONNECTSPD = 0), `RUN_STOP = 1`, dirección USB asignada |
| `GUSB2PHYCFG(0)` | `0x40002540` | interfaz UTMI+ 16 bits (USBTRDTIM = 9) |
| `GUSB3PIPECTL(0)` | `0x110e0002` | configuración de la PHY SuperSpeed |
| `GUCTL` / `GSBUSCFG0` / `GSBUSCFG1` | `0x0202c010` / `0x22220009` / `0x00000300` | ajustes de bus que habría que reproducir |
| `GEVNTADRHI:LO(0)` | `0x8:0xfea03000` | el buffer de eventos de Linux está **en el segundo banco de DRAM (> 4 GiB)**: el DWC3 direcciona 64 bits |
Volcado completo en la carpeta privada de copias (`hwinfo/dwc3-regdump.txt`). Esto da los valores objetivo a los que llegar con la
inicialización de la PHY y del núcleo.

## Qué reutilizar y qué cambiar
| Reutilizar tal cual | Sustituir |
|---|---|
| registros DWC3 estándar (`GCTL 0xc110`, `DCFG 0xc700`, `DCTL 0xc704`, `DEPCMD*`), TRBs, EP0, ECM, `ue0`, hilo de log | `GCC_*`/`CBCR` (relojes y GDSC de Qualcomm) → relojes de CMU FSYS0 |
| | `QUSB2` (PHY) → inicialización de la PHY de Samsung (CAL) + liberar el aislamiento por PMU |
| | `QSCRATCH` (anular VBUS) → señal de sesión válida del Exynos (registros de la PHY/`PHYUTMI`) y detección de cable |

## Pasos propuestos
0. *(PC, sin teléfono)* Hacer `bsd/dev/herolte_usb.c` con la parte reutilizable y huecos explícitos para clocks/PHY/VBUS; comprobar
   sintaxis contra cabeceras simuladas, como con DROP v2. Apagado por defecto (`herousb=0`).
1. *(teléfono; con el jefe)* **Sonda de solo lectura** como la `0072`: informar del estado en que S-Boot deja USB sin escribir nada.
   **Riesgo:** leer `0x15400000` o `0x15500000` con el reloj apagado cuelga la CPU. Hace falta saber antes en qué registro de CMU
   FSYS0 mirar el estado de las puertas de reloj.
2. Encender relojes, liberar el aislamiento, inicializar la PHY, reiniciar el DWC3 y enumerar (equivalente a 0073/0074).
3. ECM + `ue0` + log en vivo (0075–0077). Cliente: `tools/sweet-usbnet.sh` adaptado.

## Lo que falta saber (bloqueante para el paso 1)
- **Registros de las puertas de reloj de USB en CMU FSYS0** (`0x10E90000`?). En el 8890 los relojes salen de tablas propietarias de Samsung
  (CAL, "VCLK" en `clk-exynos8890.c`) y no encontré los desplazamientos en el árbol de Lineage ya consultado. Opciones: buscarlos en otros
  ficheros del árbol de Samsung (código fuente oficial de la G930F), o leer el estado desde el propio TWRP con el teléfono en recovery, **solo lectura**
  (`debugfs` expone el DWC3, pero no hay `/sys/kernel/debug/clk` en este kernel).
- Versión del IP de la PHY (decide qué rama de la CAL aplica) y valores de ajuste de la placa (`use_additional_tuning`).
- Cómo detecta el cable este teléfono (probablemente el MUIC del MAX77854; por confirmar).

## Decisión pendiente del jefe
Autorizar el paso 1 (una imagen BOOT de prueba con la sonda; escribir BOOT, no USERDATA). Hasta entonces, solo el paso 0 y la búsqueda de registros.

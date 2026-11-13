# Arquitectura global de IOS S7

Mapa de **qué es cada pieza, dónde está su documentación y su código, y en qué estado está**. No duplica los documentos técnicos: los enlaza. El estado de cada pieza se anota con el nivel de evidencia de la Constitución (L0 diseño · L1 compila · L2 prueba en el PC · L3 hardware · L4 iOS+pantalla); la letra `h` = observado en el teléfono del upstream, **no en esta unidad** (I-3). **En esta unidad no hay ninguna prueba en hardware.**

## 1. Cadena de arranque (de abajo arriba)
```
S-Boot (Samsung, bootloader desbloqueado)  ──lee──►  partición BOOT (40 MiB, sda5)
   BOOT = cabecera Android + cargador `xnu_boot` (shim) + payload SWEETXNU (kernel XNU + ADT + línea de arranque ≤607 car.)
   cargador ──► XNU 8796.141.3 parcheado (≈260 parches de xnu/patches, serie 0001-0335 con huecos)
   XNU ──► driver UFS propio (herolte_ufs) ──► raíz `rd=ufsroot0 ufsroot=USERDATA` (volumen HFSX al inicio de USERDATA, sda18)
   launchd (iOS 16.7.16, root del IPSW iPhone10,3 / D22AP, build 20H392) ──► SpringBoard, backboardd…
```
Referencias: `docs/herolte-bringup.md`, `docs/herolte-howto.md`, `docs/estado-y-camino-a-flashear.md`, `docs/herolte-preparacion-pruebas.md`, `shim/herolte/`, `tools/mkpayload.py`, `tools/herolte-pack-boot.py`.

## 2. Subsistemas
| Subsistema | Documentación autoritativa | Código principal | Estado (esta unidad / upstream) | Notas |
|---|---|---|---|---|
| **Cargador y empaquetado BOOT** | `docs/herolte-howto.md`, `docs/herolte-preparacion-pruebas.md` | `shim/herolte/`, `tools/herolte-pack-boot.py`, `tools/mkpayload.py`, `tools/herolte-verify-boot.py`, `tools/herolte-build-n2.sh` | L2 (verificador, 22 pruebas) / L3h | Candidata N2 de solo lectura verificada en el PC (E-0001). Cargador de clang; el validado es el de GCC (T-0013) |
| **ADT** (lista de hardware de iOS) | `docs/herolte-bringup.md` | `tools/mkadt_herolte.py`, `tools/herolte-adt-ram-banks.py` | L1-L2 / L3h | Parte del `d22ap.adt` del IPSW (iPhone X). Sin nodo de GPU (direcciones fijas en código) |
| **Almacenamiento: UFS** | `docs/herolte-dma-smp-analysis.md` | `0204-herolte-exynos-ufs.patch` y posteriores, `bsd/dev/herolte_ufs.c` | L1 / L3h | Escritura solo con `ufsrw` distinto de 0 (`writable = (rw != 0)`) |
| **Root HFS+** | `docs/herolte-root-linux.md`, `docs/herolte-unicode-hfsplus.md` | `tools/a5xelte-stage-ios-root.sh`, `tools/herolte-tune-ios-root.sh`, `tools/plutil_lite.py`, `tools/ios-root-portable.sh`, `tools/hfsplus-names/`, `tools/herolte-flash-root.py` | L2 / L3h | Imagen de laboratorio poblada pero **verificación FAILED** (32 nombres Unicode, T-0003). Pipeline T04-R en `E-0014` |
| **DROP v2** (zona de ficheros extra con recuperación) | `xnu/drop-v2/README.md`, `DECISIONES.md`, `deviceday/RUNBOOK.md` | `xnu/drop-v2/herolte_drop_core.c`, `0334-herolte-drop-v2.patch`, `tools/herolte-drop.py` | L2 (36/36) / sin prueba en dispositivo | Decisiones D1-D12 sin ratificar (D-0009) |
| **Pantalla** (DECON_F, `AppleCLCD`/IOMobileFramebuffer) | `HEROLTE_PROGRESS.md`, `docs/S7GE_STATUS.md` | `SweetFramebuffer.cpp`, `0046`, `0222`, `0296-0297`, `0320-0323` | L1 / L4h | Doble buffer y 60 Hz medidos en el teléfono del upstream |
| **GPU** (Mali-T880 MP12) y **S7GE** | `docs/S7GE_ARCHITECTURE.md` (dirección, D-0003), `docs/S7GE_STATUS.md` (estado) | `bsd/dev/herolte_gpu.c`, `iokit/Kernel/arm/HeroGPU.cpp`, `gpu/mesa`, `gpu/hakios-gl`, `gpu/eagl` | L1 / L3h-L4h parcial | Hoy acelera OpenGL ES vía EAGL/OSMesa/Panfrost; **no hay proveedor de Metal**; `IOAcceleratorES` es un servicio vacío (0260) |
| **Entrada** (táctil, botones) | `HEROLTE_PROGRESS.md` | `herolte_touch.c`, 0210-0217 | L1 / L4h | `sec_ts` por I2C con alimentación por el APM |
| **Energía, relojes, térmica** | `HEROLTE_PROGRESS.md`, `docs/herolte-peripherals.md` | 0264-0267, 0330-0331 | L1 / L3h | TMU como límite térmico |
| **Wi-Fi, audio, Bluetooth, USB** | `docs/herolte-peripherals.md`, `docs/herolte-usb-plan.md` | `herolte_wifi.c`, `gpu/hakios-audio` | L1 / L3h (Wi-Fi, audio) | USB en modo dispositivo: solo plan |
| **CI y artefactos** | `.github/workflows/`, `docs/herolte-howto.md` | `xnu.yml`, `mesa-ios.yml`, `ios-root.yml` | L1 | Publicar o lanzar CI es nivel C |

## 3. Pipeline del root de iOS (20 GiB)
`IPSW público (hash SHA-384 de Apple)` → `7z` extrae os/systemos/appos → manifiestos de propietarios, modos, enlaces y tiempos → relink de enlaces duros → **stage** (copia selectiva, cryptexes, enlaces de la caché dyld) → **tune** (migración, CommCenter, autorun, Setup) → **populate** (imagen HFSX + `rsync` + metadatos; **requiere sudo y montaje**) → **verify** (catálogo, `fsck_hfs`, metadatos, hash) → comprimir en partes de 1900 MB → escribir en USERDATA (**borra Android**, nivel C).
Estado: extracción, manifiestos, stage y tune portables a Linux **L2**; población con sudo hecha una vez por el Director; verificación **FAILED**; resto pendiente.

## 4. Pipeline de pruebas en hardware (escalera de menor a mayor riesgo)
| Peldaño | Escribe | Pregunta que responde | Estado |
|---|---|---|---|
| N1 sonda | solo BOOT | ¿es el mismo hardware? (MIDR, FDT, RAM) | candidata en el kit; sin autorización |
| N2 XNU solo lectura | solo BOOT, `ufsrw=0` | ¿arrancan cargador, kernel y ADT? ¿8 núcleos, GPT del UFS? | candidata verificada en el PC (E-0001) |
| N3 instalación completa | BOOT + USERDATA | ¿arranca iOS? | pendiente del root verificable; borra Android |
| N4 DROP v2 | zona DROP | ¿funciona el protocolo con cortes reales? | pendiente |

## 5. Verificación y gobierno
- **Pruebas:** `data/regression.toml` (suites con línea base); herramientas de verificación de BOOT, del root y de nombres.
- **Gobierno:** esta carpeta; fuente de verdad en `data/*.toml`; vistas generadas; `tools/governance.py`.
- **Evidencias fuera del repositorio:** kit del día del dispositivo (`~/HackiOS/builds/device-day`), copias del teléfono (`~/HackiOS/backups/device-herolte`), archivo en el NTFS (`IOS-S7-archive`), indexadas en `EVIDENCE.md`.

## 6. Principios de arquitectura que ya están decididos
D-0003 (S7GE: Metal arriba, S7GIR en medio, backend Midgard T880 abajo, OpenGL ES como API adicional) · D-0004 (N2 inequívocamente de solo lectura) · D-0002 (almacenamiento) · D-0006 (el generador del root no cambia hasta decidir el bloqueo Unicode). Las propuestas pendientes están en `DECISIONS.md` (`PROPOSED`).

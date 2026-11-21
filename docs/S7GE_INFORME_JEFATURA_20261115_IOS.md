# Informe a la Jefatura Técnica — 15 de noviembre de 2026 (tarde): iOS en pantalla en el Galaxy S7

**Estado al cierre:** iOS 16.7.16 arranca en el Galaxy S7 (SM-G930F, Exynos 8890) hasta la pantalla de inicio, con táctil, botones, CPU a 2600 MHz, GPU a 650 MHz, composición de `backboardd` por OpenGL ES sobre la Mali (capa GL de upstream), DROP v2 probado y apagado que reinicia en TWRP. Todo medido con el log persistente del kernel (L2) y la observación del Director (L1). **Lag residual notable (~11 fps medios), apps con fallos, fondo de pantalla sin resolver, sin Wi-Fi ni audio.**

Este informe continúa `docs/S7GE_INFORME_JEFATURA_20261115.md` (que acaba en min16). Cubre min17 → min34.

## 0. Dónde leer (otra terminal)
| Qué | Ruta |
|---|---|
| Repositorio del ingeniero (worktree) | `~/HackiOS/repos/wardevsa-ios-a5xelte-v2`, rama `herolte-drop-v2` (HEAD al escribir: ver `git log -1`) |
| Publicado | remoto `mio` = `darkcloud9998/ios-a5xelte`, solo la rama `herolte-drop-v2` (nunca `origin`) |
| **Empezar aquí** | `governance/HANDOFF.md` (relevo vigente H-0108, los anteriores debajo) y `governance/STATE.md` |
| Evidencias / decisiones / tareas | `governance/EVIDENCE.md` (E-0001…E-0248), `governance/DECISIONS.md` (D-0001…D-0074), `governance/TASKS.md`; datos en `governance/data/*.toml` |
| Este informe y los anteriores | `docs/S7GE_INFORME_JEFATURA_20261114.md`, `…20261115.md`, **`…20261115_IOS.md`** |
| Hito de hoy | `docs/S7GE_HITO_IOS_EN_PANTALLA.md` |
| Por qué la pantalla estaba a cero | `docs/S7GE_BACKBOARDD_WAIT.md` |
| Fallos de userland y qué se puede arreglar | `docs/S7GE_USERLAND_FALLOS.md` |
| Plan/guía de DROP y paquete | `docs/herolte-howto.md` §5, `xnu/drop-v2/README.md`, `~/HackiOS/builds/device-day/RUNBOOK.md` |
| Parches nuevos de hoy | `xnu/patches/0352`…`0358` (ver §3) |
| Herramientas nuevas de hoy | `tools/herolte-log-report.py`, `tools/herolte-smp-images.py`, `tools/herolte-flash-boot.sh` (ya existía), `tools/herolte-write-userdata.py` |
| Imágenes de BOOT (no están en git) | `~/HackiOS/builds/device-day/boot-candidates-n3-run{1..18}-min{17..34}/` (cada una con `.img`, `.cmdline.txt`, `.verify-independent.txt`) |
| Kernels del CI | `~/HackiOS/builds/device-day/artifacts/kernel-03{51,52,53,54,55,58}-ci-*/` y `mesa-ios-0ad027b-43718791230/` (hero-run y librerías) |
| Logs del teléfono (privados, no en git) | `~/HackiOS/builds/device-day/phase1-20261114/min{19..34}-herolog.txt` y `flash-min*-out.txt` |
| Paquetes DROP | `~/HackiOS/builds/device-day/selftest-a-min32/`, `…/drop-real-1/` (`command.txt`, `manifest.txt`) |
| Copias de seguridad | `/media/pioxi/F20C31440C31055F/IOS-S7-backup/2026-11-14-engineer-full/` (RECOVERY, SYSTEM, USERDATA Android) y `~/HackiOS/backups/device-herolte/2026-11-12/BOOT.img` (BOOT original) |
| Resumen de un log en una pantalla | `python3 -I tools/herolte-log-report.py RUTA/minNN-herolog.txt` |

## 1. Qué ha pasado, por hitos (con evidencia)
| Imagen | Cambio de la línea de arranque / acción | Resultado medido | Evidencia |
|---|---|---|---|
| (USERDATA) | **Raíz iOS escrita en USERDATA** (borra Android; copias verificadas antes) con `herolte-write-userdata.py` | Escritura y relectura correctas | D-0048, E-0179, E-0180 |
| min17 | `ufsrw=1 rootrw=1` | La raíz monta; `launchd` muere por `CS_KILLED` | E-0181…E-0184 |
| min18 | `unentitled_ios_sim_launch=1 ignition_level=1 launchd_unsecure_cache=1` | `launchd` vivo; ejecuta procesos | E-0185…E-0187 |
| min19 | `herolog=1` | **Primer log completo**: `Early boot complete`, `SpringBoard`, `backboardd` lanzados (lo que parecía bucle era un arranque normal) | E-0188…E-0190 |
| min20 | `herogpu=1` | La Mali arranca (T880 r2p0) sin fallos, pero nadie la usa | E-0191…E-0193 |
| min21-min25 | `heroring=0`, `a5fb_keep_on`, `a5fb_noconsole`, `sweetfb_native=1`; sondas del panel (0353 FBPROBE, 0354 FBSRC, 0355 FBCALL) | Superficies que `backboardd` entrega: **todo ceros** durante 12 min; iOS pide 750x1334 y el kernel anunciaba 1440x2560 | E-0194…E-0217 |
| **min27** | `sweetfb_scale=1 sweetfb_lw=750 sweetfb_lh=1334` | **Logo de Apple, pantalla de bloqueo, inicio y táctil.** Hito. | D-0064, E-0218…E-0220 |
| min28 | `sweetfb_gpu=1` | Copia de cuadro 88 → 6 ms; fps medios 2,8 → 10 | E-0221…E-0223 |
| min29 | `heropower=1 herocpu_mhz=1976` | Mongoose de ~242 MHz (bootloader) a 1976 MHz; SoC 34-43 C | E-0224…E-0226 |
| min30 | `herocpu_mhz=2600` | 1075 mV, SoC 38-41 C, sin fallos | E-0227…E-0230 |
| min31 | `herogpu_mhz=650` | GPU a 649 MHz, `vdd_g3d 0x40`, sin `JOB_READ_FAULT` | E-0228, E-0231, E-0232 |
| min32 | `herodrop=1` + paquete de autoprueba en la zona DROP | **DROP v2 funciona en el teléfono** (5 ficheros verificados) | D-0068, E-0233…E-0237 |
| **min33** | línea de uso diario de upstream (`herogl=1 sweettop=1 glsb3=1 herosb=1 a5fb_perf=1 a5fb_hz=60 heronoexec=…`) + **paquete real 1** (hero-run, Mesa/GL, libherosb…) | `EAGL shim inserted` en `backboardd`; apps ya no en blanco; "iPhone X, 21 GB"; 1.er arranque se congeló con `lsd` reconstruyendo LaunchServices, el 2.º no | D-0070, E-0238…E-0244 |
| min34 | `herohalt=1` (parche 0356) + 0357 + 0358 | **Apagar desde iOS reinicia en TWRP**; log 3x más limpio | D-0074, E-0245…E-0248 |

Escrituras en el teléfono hoy: solo **BOOT** (min17…min34) y **USERDATA**: la raíz (D-0048) y la zona DROP (selftest y paquete real, bytes ≥ 23 293 374 464, fuera del volumen HFS). EFS, RECOVERY y bootloaders: **no se han tocado** (EFS comprobado antes/después en cada escritura; el hash impreso cambia entre sesiones porque el propio teléfono lo modifica).

## 2. Rendimiento medido
| Imagen | fps medio / máx | Copia por cuadro | Relojes | SoC máx |
|---|---|---|---|---|
| min27 | 2,8 / 12,9 | 88 ms (CPU) | Mongoose ~242 MHz | – |
| min28 | 10,2 / 27 | 6,3 ms (Mali) | idem | – |
| min29 | 12,2 / 46 | 5,5 ms | 1976 MHz | 43 C |
| min30 / min31 | 8,0 / 7,8 (sesiones cortas) | 5,1 / 4,4 ms | 2600 MHz, GPU 650 | 41 C |
| min33 (2.º arranque) | 8,5 / 20 | 6,1 ms | 2600 / 650 | 47 C |
| min34 | 11,2 / 28 | 6,1 ms | 2600 / 650 | 41 C |
`backboardd` llega a ~300-410 % de un núcleo (de 800 %) y `SpringBoard` a ~370 %: la composición con la capa GL es el cuello. Memoria libre baja a 50-180 MB con uso.

## 3. Cambios de código de hoy (todos en `xnu/patches/`, en CI)
| Parche | Qué | Estado |
|---|---|---|
| 0352 | `heroring=0` apaga el anillo de `kprintf` (pintaba sobre la UI) | CI OK |
| 0353 / 0354 / 0355 | Diagnóstico de pantalla: miniatura (FBPROBE), escaneo de la superficie origen (FBSRC), argumentos de llamadas IOMFB (FBCALL) | CI OK; 0358 los recorta |
| 0356 | `herohalt=N`: apagar/reiniciar reinicia por SWRESET del PMU (recovery o normal) | CI OK, probado en min34 |
| 0357 | Limita a 8 las notas de HFS en el S7 (eran la mitad del log) | CI OK |
| 0358 | Menos sondas | CI OK |
El diff de cada uno es pequeño y está en `xnu/patches/`. 0352-0358 **no están fusionados con `origin/herolte`** (ver `docs/herolte-integracion-origin-herolte.md`).

## 4. Correcciones de método y errores míos de hoy (para que no se repitan)
- **E-0187 («bucle de exits») era una lectura equivocada**: solo veíamos cadenas de formato. El log completo (E-0190) mostró un arranque normal.
- **min21 y min22 usaron `sweetfb_noconsole`**, que bajo A5XELTE no se lee (el nombre correcto es `a5fb_noconsole`); no tuvo efecto.
- **Hice un push antes de que el `gate` pasara** (D-0053) por un fallo de declaración en la tarea; la firma del Director lo cubría, pero lo registré como lapso y lo corregí.
- **Describí `hero-run` de forma incompleta**: además de lo que dije, borra una vez las bases `.csstore` de LaunchServices y la caché de MobileGestalt. Se lo avisé al Director antes del primer arranque con el paquete.
- **Dos CI fallaron por errores de compilación míos** (0355: cast de puntero; 0356: `kPERestartCPU` no visible en C). Corregidos con firma nueva cada vez.
- **`STATE.md` estaba obsoleto** y un test de gobierno usaba el id `D-0050`, que ya era una decisión real; ambos corregidos (`98 + 6` pruebas OK).
- «Autorizo» sin texto: lo he **estrechado** a lo descrito en mi mensaje y lo he registrado como tal (D-0069, D-0071). Las acciones rojas siguen con firma del Director con imagen/commit y SHA-256.

## 5. Gobierno de hoy (todo con firma del Director)
Imágenes de BOOT: D-0049 (min17), D-0050, D-0051 (min19), D-0052 (min20), D-0054, D-0056, D-0057, D-0059, D-0060, D-0063, D-0064, D-0065, D-0066, **D-0067 (lote min30/min31/min29, máx. 3 escrituras)**, D-0068 (min32 + zona DROP), D-0070 (min33 + paquete real), D-0074 (min34). CI (push a `mio` + workflow): D-0053, D-0055, D-0058, D-0061, D-0062, D-0069 (mesa-ios), D-0072, D-0073. Delegación acotada durante una ausencia: D-0071 (solo trabajo verde).

## 6. Estado de lo que falla o falta
| Tema | Estado | Qué haría falta |
|---|---|---|
| Lag (≈11 fps) | `backboardd` ~300 % de CPU; composición GL de upstream | perfilar `backboardd`; quitar más servicios; probar 2288 MHz por temperatura; scheduler (`heroquantum`) |
| Fondo de pantalla | negro/sin resolver (iOS 16 usa Metal; upstream pone imagen fija con `herosb`) | mirar los 9 bundles de fondos y `wallpaper.off`; probar la imagen de `herosb` |
| Messages / CoreImage | cierra: puntero de función nulo en CoreImage (falta Metal) | **S7GE** (Metal/IR/Midgard) |
| Fotos (`assetsd`, PhotosFileProvider) | abortan: excepción sin capturar | ver el texto de la excepción con `hero-run`/log de NSException |
| Ajustes se queda pillado a veces | sin crash en el log | perfilar con el muestreador |
| Wi-Fi, audio | apagados a propósito (sin ficheros del teléfono en el paquete) | extraer firmware de VENDOR en TWRP (solo lectura) |
| Apagado real | reinicia en TWRP; `PS_HOLD_CONTROL = 0x5300` | parche 0359: `herohalt=3` con valor 0x5200 (opcional) |
| Seguridad | `cs_enforcement_disable=1`; AS0 única y `Submit` sin validar (`docs/S7GE_ABI.md`) | no ejecutar software no confiable; decisión sobre D-0015 |
| Copias | un solo disco; USERDATA Android borrado por la raíz iOS | copia en otro disco |
| Gobierno | ratificaciones pendientes: D-0007, D-0009, D-0011..D-0013, D-0015 | jefatura técnica |

## 7. Preguntas a la Jefatura
1. **Prioridad:** ¿fluidez (rendimiento de `backboardd`) o arrancar S7GE (Metal) para Messages y el resto?
2. ¿Aprueba fusionar 0352-0358 con la serie de upstream (`origin/herolte`) y renumerar los conflictos (T-0016)?
3. ¿Quiere que el siguiente hito sea Wi-Fi (necesita firmware de VENDOR del propio teléfono) o audio?
4. ¿Ratifica D-0007/D-0009 y las demás pendientes de §6?
5. ¿Se hace una copia de EFS/USERDATA en un segundo disco antes de seguir?

## 8. Reproducir lo mínimo (sin tocar el teléfono)
```
cd ~/HackiOS/repos/wardevsa-ios-a5xelte-v2
python3 -I tools/governance.py check && python3 -I tools/governance.py status
sed -n 1,60p governance/HANDOFF.md
python3 -I tools/herolte-log-report.py ~/HackiOS/builds/device-day/phase1-20261114/min34-herolog.txt
cat ~/HackiOS/builds/device-day/boot-candidates-n3-run18-min34/xnu-boot-v2-s7-min34-20261115.cmdline.txt
```
La línea de arranque de `min34` (605 de 607 caracteres): `debug=0xc keepsyms=1 -noprogress cpus=8 rd=ufsroot0 ufsroot=USERDATA cs_enforcement_disable=1 wdt=-1 -wdt_no_pmu wdt_test=no_user_checkin ufsrw=1 rootrw=1 herolog=1 herowifi=0 vm_compression_limit=98304 vm_compressor=2 unentitled_ios_sim_launch=1 ignition_level=1 launchd_unsecure_cache=1 heroring=0 a5fb_noconsole=1 a5fb_keep_on=1 sweetfb_native=1 sweetfb_scale=1 sweetfb_lw=750 sweetfb_lh=1334 sweetfb_gpu=1 herocpu_mhz=2600 herogpu_mhz=650 herogl=1 sweettop=1 glsb3=1 herosb=1 a5fb_perf=1 a5fb_hz=60 heronoexec=vmd,bluetoothd,searchd,ReportCrash,aggregated,analyticsd,cloudd,homed,driverkitd herohalt=1`.

**Qué NO está en git y por qué:** logs del teléfono y sus `.bin` (identificadores del dispositivo), imágenes de BOOT y de raíz, artefactos de Apple, copias de EFS/IMEI.

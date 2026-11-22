# Estudio (solo lectura) de la rama `herolte-ios18` del upstream (18-nov-2026)

Fuente: `origin` = `github.com/wardevsa/ios-a5xelte` (nuestro origen), ramas `herolte` y `herolte-ios18` traídas con `git fetch origin` el 2026-11-18. Solo se ha LEÍDO; no se ha fusionado ni empujado nada. Nivel de evidencia L1 (lectura de nombres y cabeceras de parches y del diario). No se ha compilado ni probado nada de ello.

## 1. Qué es la rama
- **XNU 11215** (el kernel de iOS 18 / macOS 15) para el mismo S7 (HEROLTE), con la build **22H352** (iOS 18.x), conseguido el 17-nov (commits «first iOS 18 boot on the Mali», «iOS 18 colours right on the Mali»).
- Construida sobre dos capas: (a) los parches de **«Bergamota»** para 11215 (`xnu/patches-11215/0003…0251`, nombres `sweet-`, `beryllium-` → un port a un Poco F1, Snapdragon 845) y (b) el port de herolte `9001…9192` (la misma serie 0200-0341 que la nuestra, renumerada, más lo nuevo).
- **Dos piezas específicas que iOS 18 exige y que el S7 no tiene:**
  - `9157-0400-herolte-v80emu`: **emulación en el kernel de las instrucciones ARMv8.1+ del userland** (por ejemplo las atómicas LSE) que el Mongoose y el A53 (ARMv8.0) no ejecutan; con estadísticas en `sysctl kern.v80emu`.
  - `0135-ios18-dyld-pager-arm64e-nopac` y la herramienta `tools/ios18/pacstrip.py`: las imágenes **arm64e** se reescriben **fuera de línea** para que su código no lleve instrucciones de autenticación de punteros (el S7 no tiene PAC).
- Para la energía: `9192-herolte-screen-off-mongoose-idle` aparca los Mongoose con la pantalla apagada con `sched_perfcontrol_update_recommended_cores(0x0f)` (el planificador, no el reposo profundo); `9175-0321-ui-threads-to-idle-fast-cores`; `0191-beryllium-amp-idle-core-steering`.

## 2. Qué tenemos en común y en qué divergimos
- **Común (≈85 %):** la serie `0200-0341` del upstream es la misma que partió nuestra rama: arranque, UFS, GPU Mali, EAGL, Wi-Fi por PCIe con handshake en kernel, audio `HakiosAudio`, VGR0, etc.
- **Solo nuestro:** DROP v2 y el empaquetador de imágenes verificadas; gobierno con evidencias y decisiones; `heronoexec`, `herogov` (gobernador de CPU), `heropd` (apagar dominios del PMU), líneas `HEROLTE PWR/CHG/PD/PMIC/PSCI/IDLE`; icono de carga según el cargador (0432); **reposo profundo de núcleos por PSCI con el paso del PMU de Samsung y criterio de residencia** (0438-0443, E-0290); medición contra Linux (E-0288); `herohot`.
- **Solo del upstream:** todo lo de iOS 18 (kernel 11215, v80emu, pacstrip, `tools/ios18`, raíz HFSX con diario), el escritor de log en la ruta de panic (`9170`, nuestro 0363 pendiente), esperas antes del panic del `initproc` (`9167-9169`), `libheroapp` en `iconservicesagent` (`9191`), `sched_SMT_balance` (`9175`).

## 3. Qué haría falta para iOS 18 y por qué es «cambiar de kernel»
1. **Otro kernel:** XNU 11215 (no 8796.141.3). Toda nuestra serie de energía (0428-0443) hay que **portarla**: el upstream ya portó 0317-0341 de una vez (`ca49e8b`), así que el método existe.
2. **v80emu en marcha** (coste de rendimiento por cada instrucción emulada: no medido por nosotros).
3. **Reescribir la raíz de iOS en USERDATA** con `pacstrip` y la IPSW 22H352: acción roja que borra la raíz actual de iOS 16; no la cubre ninguna decisión vigente (D-0090 lo dice).
4. iOS 18 es más pesado: el propio diario anota el desglose de CPU de sus servicios.

## 4. Qué propongo (a decisión del Director)
- **Ahora:** terminar el reposo profundo en iOS 16.7 (es kernel genérico y se portará).
- **Después, sin tocar el teléfono:** tabla de portado de nuestros parches 0428-0443 a 11215 (ficheros: `osfmk/arm64/cpu.c`, `start.s`, `SweetCPU.cpp`, `herolte_gpu.c` — los mismos que ya toca el upstream) y comprobar si aplican a su árbol (`git apply --check` sobre sus fuentes).
- **Adoptar ya, también en 16.7:** `9192` (aparcar los Mongoose con la pantalla apagada con `sched_perfcontrol_update_recommended_cores`), que se suma al reposo profundo.
- **Decidir más tarde** si saltamos a iOS 18, con copia previa de USERDATA y firma explícita del Director.
- Nota de plataforma: la capa «Bergamota» (Poco F1, Snapdragon 845) demuestra que el upstream ya cubre una plataforma Qualcomm con iOS 18; es un dato para la evaluación de teléfono pendiente.

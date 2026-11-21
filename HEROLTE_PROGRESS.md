# HEROLTE (Galaxy S7 SM-G930F, Exynos 8890): progreso

Registrar por separado: compilación, marcadores recuperados, lo que se ve en
pantalla y comportamiento de iOS. Plan y mapa de hardware en
`docs/herolte-bringup.md`.

## 2026-10-20

- Dispositivo: SM-G930F, bootloader desbloqueado, TWRP instalado.
- `shim/herolte/probe.S` + `probe.c` compilados con Arm GNU Toolchain 14.2.rel1
  (`aarch64-none-elf`): Image de 10.784 bytes, solo relocaciones PC-relativas
  (ADR_PREL_PG_HI21, ADD_ABS_LO12_NC, CALL26), sin llamadas a librería.
  **Solo compilación**; no se ejecutó en el teléfono.
- `tools/herolte-pack-boot.py` probado con una imagen BOOT sintética
  (página de 2048, DTBH v2 con chip 8890): conserva DTBH y ramdisk, copia
  `text_offset`/flags del kernel de stock, recalcula el SHA-1 del header.
  Todavía no se probó con el BOOT real del S7.
- BOOT del teléfono (custom ROM, no stock), leído con `dd` desde TWRP:
  partición de 41.943.040 bytes, página 2048, kernel arm64 sin comprimir de
  38 MB con `text_offset=0x80000`, DTBH v2 con 3 DTB Exynos 8890
  (hw_rev 4–7, 8, 9). DTB: RAM `0x80000000+0x7e400000` y `0x880000000+2G`,
  initrd en `0x82000000`, reservas TIMA `0xb1000000`, ION desde
  `0xc0000000`, módem `0xf0000000`. `0xe2a00000` cae en un hueco libre.
- `probe-boot.img` armado desde ese BOOT (1.495.056 bytes).
- **Primera prueba en el teléfono (reporte del usuario):** el probe muestra
  texto blanco sobre el logo y la cuenta "TWRP EN 60 S"; al terminar, el
  teléfono reinicia solo a TWRP. Prueba que S-Boot ejecuta nuestro Image
  (header arm64 + DTBH correctos), que el framebuffer `0xe2a00000` con el HW
  trigger de DECON_F funciona, que CNTPCT avanza y que el reinicio a
  recovery por PMU `0x105c0000` (INFORM2/INFORM3/SWRESET) funciona.
- **Foto del probe:** EL 1; SCTLR `0x30c5183e` (MMU off); FDT `0x8a000000`;
  IMAGE `0x800bc000`; MIDR `0x410fd034` (Cortex-A53 r0p4); MPIDR
  `0x80000100`; MMFR0 `0x1122` (sin 16 KiB); PFR0 `0x2222`; ISAR0 `0x11120`
  (AES/SHA1/SHA2/CRC32, **sin LSE**); CNTFRQ **0** (como el A5: frecuencia
  desde el ADT, 26 MHz); DECON trigger previo `0x12b0`; initrd
  `0x89000000..0x890dbf7e` (el ramdisk de la ROM).
- Consecuencia: entre initrd y FDT hay 16 MiB, poco para el payload de XNU.
  `xnu_boot` ahora busca el payload pegado a su Image
  (`herolte-pack-boot.py --append`) y usa el initrd solo como alternativa.
- Serie de parches normalizada sobre `xnu-8796.141.3` (ver
  `docs/herolte-bringup.md`): 123 parches aplican con `git apply` simple,
  incluido `0200-herolte-board-target`. 12 movidos a `xnu/patches-pending/`
  (los 10 rotos m?s `0133`/`0134` de GPU del A5, publicados despu?s).
  **El kernel HEROLTE todavía no se compiló**: Actions pendiente.
- `shim/herolte/xnu_boot` (loader) y `tools/mkadt_herolte.py` escritos y
  compilados/ejecutados localmente; sin prueba en el teléfono.
- `0106`/`0107` reescritos como `0201-herolte-amfi-bridge` y
  `0202-herolte-4k-unsigned-dyld-cache`; 125 parches aplican en orden.
- **Primer kernel HEROLTE compilado en Actions** (fork `wardevsa/ios-a5xelte`,
  rama `herolte`, run 39477885586, commit fb6194b): artefacto `xnu-kernel`
  de 61 MB. El chequeo de LSE encontró una sola coincidencia, dentro de
  `K256` (constantes de SHA-256 en `__TEXT`), es decir, datos: el código del
  kernel no tiene atómicas LSE. El chequeo ahora ignora `K256`.
- Actions publica los errores de compilación como anotaciones públicas
  (los logs requieren sesión de GitHub).
- **Primer arranque de XNU en el S7** (`xnu-boot.img`: loader + payload
  pegado de 16.474.720 bytes; kernel sha256 `61a9dd49…ca5d`, cmdline
  `debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress`).
  Foto del usuario: consola de XNU en el framebuffer con VM bootstrap,
  zone_init, firehose, scheduler, KDP serial, `iBoot version: herolte-entry`,
  `SWEET PRNG`, `A5XELTE pthread: libpthread-514.100.2 registered`,
  `SWEET AMFI: built-in interface registered`, platform expert iniciado.
  Pánico en `SweetCPU.cpp:86`: `unsupported topology cpu=0 mpidr=0x100
  count=1` (el chequeo esperaba MPIDR 0 del A5).
- `0203-herolte-boot-mpidr`: el MPIDR de arranque es constante de placa
  (`A5XELTE_BOOT_MPIDR`: A5 `0x0`, herolte `0x100`).
- **Kernel completo hasta la espera del root** (run 39481021599, kernel
  sha256 `ffa3d8ea…432f`, misma cmdline). Foto del usuario: `A5XELTE CPU:
  cpu=0 mpidr=0x100 came alive; SGI1 OK`, `1/1 CPUs initialized, SGI1
  verified`, BSD init, AppleKeyStore, IOWatchdog, IOCoreSurfaceRoot, HID de
  botones/touch, SWEET AMFI (0201) y Sandbox registrados, HFS 627.100.6,
  self-tests de Skywalk `PASSED`, `lo0`/`gif0`/`stf0`, y finalmente
  `Waiting on <dict>IOProviderClass IOMedia, Content Apple_HFS</dict>`.
  Es el punto esperado: no hay driver de almacenamiento todavía.
- **Primer probe UFS** (`0204`, run 39484347438, kernel `d3905386…45f2`,
  `ufsprobe=1`): `cap 0x383ff0f ver 0x200 hcs 0x10f hce 0x1 is 0
  utrlba 0x0:ef002000 dbr 0 rsr 1`, `txprdt 0xc rxprdt 0xc nexus 0xffff`.
  El host quedó vivo tras S-Boot y tomó nuestra lista. TEST UNIT READY en
  LUN 0 (3 veces): `ocs 0x7 upiu 0x21 response 0x1 status 0x2`, o sea un
  UPIU de respuesta real con CHECK CONDITION: el transporte (UTRD con
  offsets en bytes, PRDT, NEXUS, doorbell) funciona. El probe no siguió a
  READ porque abortaba tras el TUR. Siguiente: imprimir el sense, probar
  LUN 0..7 y leer LBA1 aunque falle el TUR.
- **Segundo probe UFS** (run 39486812960, kernel `00f0b0da…deb1`): LUN 0–3
  responden NOT READY (sense key 2, ASC/ASCQ 0/0); LUN 4–7 ILLEGAL REQUEST
  ASC 0x25 (no existen: el S7 tiene 4 LU). READ(10) LBA1 en LUN 0: NOT
  READY. Hipótesis: S-Boot deja el dispositivo en un modo de bajo consumo;
  Linux lo reactiva con START STOP UNIT (ACTIVE) al W-LUN UFS Device
  (`0xD0`). `0204` ahora lo hace antes del primer comando (probe e init).
- **Tercer probe UFS: lectura funcionando** (run 39489906319, kernel
  `869c4c5f…d74a`). W-LUN `0xD0` TUR: NOT READY ASC/ASCQ 04/02
  ("initializing command required"); `START STOP UNIT (ACTIVE) 0`; LUN 0–3
  TEST UNIT READY 0; `READ(10) LBA1 0, signature EFI PART`; GPT de 128
  entradas de 128 bytes en LBA 2; particiones p1 `BOTA0` … p17 `USERDATA`
  (~21,5 GB, bloques de 4 KiB). Primera lectura del UFS desde XNU.
- **Primer root montado desde UFS.** Volumen HFSX de 32 MiB
  (`hfs-test-image`, sha256 `043f1459…8b94`) escrito por adb/TWRP al inicio
  de USERDATA (`/dev/block/sda18`); BOOT con `rd=ufsroot0 ufsroot=USERDATA
  cs_enforcement_disable=1` (mismo kernel `869c4c5f…`); ambos verificados por
  readback. Foto: `"USERDATA" on LUN 0: first block 0x22e0ac, 21566 MiB,
  read-only`, `BSD root: ufsroot0, major 1, minor 0`, `hfs: mounted HEROTEST
  on device b(1, 0)`, `root volume is not authenticated (error 25);
  continuing unsealed`, `devfs_kernel_mount: kernel_mount failed: 2` (la
  imagen no tiene `/dev`), y pánico esperado `exec of /sbin/launchd failed,
  errno 2`. Siguiente: imagen raíz de iOS 16.
- **Root de iOS 16.7.16 (iPhone X, D22AP) en USERDATA.** Workflow `ios-root`
  en el repo privado `wardevsa/ios-herolte-root` (la imagen es software de
  Apple; no se publica): HFSX de 20480 MiB, 3 partes gzip verificadas por
  SHA-256. Escrita con `tools/herolte-flash-root.py` (bloques de 64 MiB con
  readback SHA-256, ceros escritos en el teléfono; un corte del servidor adb
  se retomó con el archivo de estado): 320/320 bloques, imagen sha256
  `2e200c51…13ca8`, firma `HX` en el offset 1024. ADT con `/product` real de
  D22AP (63 propiedades) y kernel `d706ccd8…e271` (incluye 0205). Boot:
  `rd=ufsroot0 ufsroot=USERDATA ufsrw=1 rootrw=1 cs_enforcement_disable=1
  unentitled_ios_sim_launch=1 ignition_level=1 launchd_unsecure_cache=1
  wdt=-1 -wdt_no_pmu wdt_test=no_user_checkin`, verificado por readback.
- **Primer arranque de iOS** (log persistente 0206, kernel `012d056a…af10`,
  53 flushes): launchd hace todo el early boot (fsck, mount-phase-1/2,
  keybag, obliteration, launchd_cache_loader con `launchd_unsecure_cache`) y
  llega a `Early boot complete`; lanza SpringBoard, backboardd, keybagd,
  bluetoothd, fairplayd.H2, etc. SpringBoard aborta en loop (24 veces):
  `NSInternalInconsistencyException: We expect a valid bounds for
  configuration ... Main-External ... CADisplay.name = Wireless ... bounds
  {{0,0},{0,0}}` — no había display principal: el `disp0` del ADT decía
  `samsung,herolte-display` y AppleCLCD matchea `samsung,a5xelte-display`.
- **Con el ADT corregido** (boot `67953d9b…ea19`, mismo kernel): `SWEET FB:
  AppleCLCD 1440x2560 stride 5760 at 0xe2a00000 ... presented as 1125x2436`,
  backboardd configura el display (`display on`) y crea superficies
  1440x2560 y 1125x2436; **SpringBoard ya no crashea** (solo CommCenter, sin
  módem, y driverkitd). En ~5 min de log todavía no hay ningún `swap`.
- **Arranque largo (~20 min) con el ADT corregido:** log hasta el flush #37
  (46 KB). backboardd hace `SwapBegin` (sel 4) y sel 52, pero nunca
  `SwapEnd` (sel 5): ningún `SWEET FB: swap`, ninguna registración de
  notificaciones de vsync. El log deja de crecer bastante antes del final.
  `0207`: sampler de hilos (`sweet_sample.c`, SpringBoard/backboardd, a los
  90 s y cada 120 s) y latido `HEROLTE LOG: alive N s` cada 60 s.
- **Muestreos 0207** (kernel con sampler, ~14 min, latido estable cada
  60 s: el sistema no está colgado). Simbolizado contra la dyld cache de la
  imagen: el hilo `IOMFBServer` de backboardd rasteriza con el renderer de
  CPU de QuartzCore (`CA::OGL::SW::scanline`, `vAlpha_Blend` de vImage) y
  reintenta `eagl_init` (busca GPU) en cada `render_for_time`; el hilo
  principal de backboardd queda en `CA::Display::Display::update` (mach_msg)
  y SpringBoard espera en `FBSystemShellInitialize` (check-in síncrono con
  backboardd). Con un solo A53 el primer frame no termina.
- `0208`: SMP en los 4 A53 (MPIDR `0x100..0x103`) por PSCI `CPU_ON`, IPIs
  GICv2 dirigidas por la máscara de ITARGETSR0 de cada núcleo (adaptado de
  los pendientes 0112/0113 del A5). Requiere `cpus=4`.
- **Primer arranque con 4 núcleos** (`cpus=4`, boot `77af8df8…d298`):
  foto `A5XELTE CPU: cpu=1..3 PSCI CPU_ON rc=0 ... came alive; SGI1 OK`,
  `4/4 CPUs initialized, SGI1 verified`; el arranque va notablemente más
  rápido. Log (flush #67, 11 min): el hilo principal de backboardd ya no se
  bloquea; ahora espera en `DMPerformMigration` (XPC síncrono) mientras
  `com.apple.migrationpluginwrapper` aborta (3 veces), y SpringBoard sigue en
  `FBSystemShellInitialize`. CommCenter crashea 45 veces (sin módem). Sin
  `swap` todavía.
- `tools/herolte-tune-ios-root.sh` (en el workflow `ios-root`): como las
  imágenes v12/v13 del donor, `LastSystemVersion` en
  `com.apple.migration.plist`, CommCenter fuera de `launchd.plist`,
  `BKNoWatchdogs` + excepción de watchdog para Setup y el esqueleto
  `/private/var/containers`. `herolte-flash-root.py --diff` reescribe solo
  los bloques de 64 MiB que cambiaron.
- **Root ajustado** (22 bloques reescritos con `--diff`, imagen
  `6e77614c…c156`): sin migración ni CommCenter. **Primer SwapEnd de
  backboardd** (`sel 5`, registro de 1132 bytes), seguido de inmediato por
  `display off` (el driver hace el fundido a negro y no presenta), luego
  `display on`; SpringBoard crea sus primeras IOSurfaces (ids 7–10). Muestreo
  a los ~6 min: SpringBoard en `GSEventRunModal` (UI arrancada), backboardd
  rasterizando en 4 hilos (`CA::OGL::SW::image_sampler`). Siguiente BOOT
  (`a3bce0c3…0758`): `a5fb_keep_on=1 a5fb_noconsole=1 a5fb_perf=1`.
- **0209 (volcado de registros de swap):** los dos primeros swaps son
  frames negros a propósito (`0x104=0x80000007`, todos los ids de superficie
  0, fondo `0x10c=0xff000000`); después no llega ningún swap con contenido.
  backboardd crea sus superficies de render como `0x62336138` ('b3a8', 2
  planos) de 1440x2560 y 1125x2436: la superficie por defecto (panel
  1440x2560) contradice el tamaño presentado (1125x2436).
- **🍎 iOS en pantalla (2026-10-22, boot `a2d97ebe…2239`, `sweetfb_native=1`):**
  con el tamaño real del panel, primero el logo de Apple y después la
  pantalla de configuración "Hola" (bonjour), con hora, batería e indicador
  de inicio de iPhone X. Táctil y botones sin driver todavía.
- `0210`: botones por GPIO ALIVE (`0x10580000`, del DTB del BOOT): Power
  GPA2 pin 4; Vol+/Vol-/Home GPA0 pines 3/4/5, activos en bajo, solo lectura
  con antirrebote (driver del A5 parametrizado). Táctil: `sec_ts` en 0x48 de
  HSI2C `0x14E10000`, IRQ GPA1 pin 0 (pendiente).
- **Botones en el teléfono (boot `8c9c5843…dd25`, 0210):** los cuatro se
  detectan y llegan a iOS (`SWEET HID: key 0xe9/0xea/0x40/0x30`). Power
  bloquea/desbloquea (con `a5fb_keep_on` la imagen queda congelada y al
  despertar vuelve "Hola"); Home y volumen no cambian nada en "Hola"
  (identidad iPhone X: se pasa deslizando hacia arriba).
- `0211`: driver táctil `bsd/dev/herolte_touch.c` (sec_ts en 0x48 de
  HSI2C `0x14E10000`, pines GPF1-0/1 función 2, INT GPA1-0 por sondeo cada
  5 ms; eventos `0x71` de 8 bytes, coordenadas 0..4095 escaladas a
  1440x2560) y `SweetHID` con la geometría del panel del S7. No toca las
  LDO32/33 del PMIC: si no responde, lo deja anotado.
- **0211 en el teléfono:** GPF1 `dat=0` y GPA1 `dat=0` (SDA/SCL e INT en
  bajo), el HSI2C táctil queda en `trans=0x2000c` con el primer byte en la
  FIFO: el sec_ts está sin alimentación después de S-Boot.
- **0212 en el teléfono:** el batcher del PMIC (`0x10550000`) completa el
  envío del registro, pero la lectura queda en `bat_state=0x200` con la FIFO
  RX vacía; no se encendió nada (la verificación de voltaje no llegó a
  correr). `0213`: init del bus como el probe de Linux (reset, master, código
  HS `0x0f`, HS|AUTO), tres formas de lectura (ext de Linux, 7 bits, con STOP)
  y volcado de registros en cada falla.
- **0213/0214:** ambos congelaron el teléfono (0213 tras resetear el HSI2C
  del PMIC; 0214 al arrancar el primer programa del batcher a ~56 s).
- **0215 (sondeo de solo lectura, arrancó bien):** PMU APM
  `config=0x1 status=0x10000 option=0` (M3 alimentado pero retenido, sin
  `ENABLE_APM`), mailbox `0x11240000` todo en 0, SRAM `0x11200000` con una
  tabla de vectores Cortex-M válida (`00004000 0000009d …`): S-Boot deja el
  firmware del APM cargado y el M3 detenido.
- `0216`: alimentación del táctil por el APM, como Linux con la pantalla
  encendida: liberar el M3 (`APM_CONFIG |= 1`, IRQ del mailbox a 0,
  `APM_OPTION |= ENABLE_APM`) y pedirle por mailbox lecturas/escrituras del
  S2MPS16 (LDO32/33). El batcher queda tras `herotouch=2`.
- **🖐 Táctil funcionando (0216, boot `626b33c7…2d1d`):** el APM responde
  por mailbox (S2MPS16 `id=0x2`, `L32CTRL=0x2e`, `L33CTRL=0x3c`;
  escrituras `0xee`/`0xfc` con respuesta `0xa`, readback correcto); con las
  LDO encendidas SDA/SCL suben (`GPF1 dat=0x3`), el sec_ts está en modo app
  (`0x20`, id `ac a5 52`, tx=15 rx=26) y los toques llegan a iOS
  (coordenadas 0..4095 confirmadas). Muy lento y el gesto de deslizar hacia
  arriba no se completa: lecturas I2C con `int=0x400` (NACK) justo después
  de apoyar el dedo pierden los eventos de movimiento.
- `0217`: reintentos de lectura como `sec_ts_i2c_read()` (hasta 10),
  contadores `moves/i2c_retries/lost_reads`; las pausas de 11 s solo con
  `herotouchslow=1` (el táctil queda listo a los pocos segundos).
- **0217 en el teléfono:** `moves=835 i2c_retries=6 lost_reads=0`: los
  movimientos llegan completos; el gesto en "Hola" no avanza porque Setup
  espera CoreTelephony/activación (igual que el donor).
- **🏠 Pantalla de inicio de iOS (2026-10-23):** imagen con Setup marcado
  como completo (imagen `035edb65…d60a`, flasheo diferencial de 155
  bloques): pantalla de inicio y Centro de control con el táctil. Sin apps
  (el staging excluía `/Applications`; dos iconos "Waiting…") y muy lento.
- `STAGE_ALL_APPS=1` en `ios-root` (todas las apps, ~215 MiB) y `0218` +
  ADT `cpu4..7`: los 4 Mongoose (MPIDR `0x0..0x3`) como lógicos 4–7 con
  `cpus=8`.
- **8 núcleos (ADT con `arm,cortex-a53` también en los Mongoose):**
  `8/8 CPUs initialized`; `0219` confirma contador común a los dos clusters
  (lag < 1 ms) y temporizadores que despiertan en los 8 (21 ms sobre 20).
  Los Mongoose reportan `midr=0x531f0011`, `ctr=0x84448005` (línea de
  I-cache de 128 B frente a 64 B en los A53).
- Con todas las apps se quedaba en el logo: `lsd` no terminaba de sembrar la
  base de LaunchServices porque MobileGestalt calculaba el UDID y esperaba
  para siempre `mac-address-bluetooth0` (no estaba en `/chosen`). Con MACs
  sintéticas en el ADT (`02:48:45:52:4f:0x`): **pantalla de inicio con
  iconos** (Fotos, App Store, Ajustes, Teléfono, Safari, Mensajes) y
  Ajustes > Información abre ("iPhone X", iOS 16.7.16, 21 GB).
- **Batería (0220/0221):** el fuel gauge es el del MAX77854 (`0x36` en
  HSI2C_1 `0x13650000`, pines GPD1-2/3; en HSI2C_0 no hay ACK). Lecturas
  reales en el teléfono: 100 %, 4339 mV, +114 mA con cargador; 4043 mV,
  −749 mA sin él; FULLCAP ≈ 2000 mAh. iOS muestra 100 % → 99 %.
- **Botón de encendido (0220):** con `a5fb_keep_on` se acepta el apagado de
  pantalla si llega < 3 s después de pulsar Power; bloquea y apaga la
  pantalla, y vuelve con la pantalla de bloqueo.
- `0222`: `sweetfb_scale=1` experimental, iOS dibuja 960x1706 y el kernel
  escala x1.5 (menos píxeles para el renderizado por CPU).
- **Más RAM (2026-10-23):** el segundo banco de DRAM (`0x880000000`,
  2 GiB, sin `reserved-memory`) para XNU con `mkadt_herolte.py --bank2`.
  Con 2 GiB el kernel ve la memoria pero entra en pánico en
  `kmem_range_init` (no entran sus rangos virtuales). Con
  `--bank2-mb 1024` arranca; los secundarios no llegaban (CPU_ON rc=0 con
  entrada > 4 GiB) y `0223` entra por un trampolín en `0x8fffe000`:
  **1 GiB y 8/8 núcleos**, pantalla de inicio "bastante más fluida, abre
  todo mucho más rápido".
- **0224:** copia a pantalla en paralelo (3 hilos ayudantes): de 10–20 ms a
  ~5 ms por cuadro, hasta 16 fps con movimiento. El log de `kmem` mostró
  por qué 2 GiB no entraba: el kernel (configuración macOS) reserva un
  compresor de 16 × RAM; `vm_compression_limit` lo limita. Con 2 GiB pasa
  ese punto pero entra en pánico en `write_pte_fast` (PTE no alineada,
  páginas de 16 KiB sobre 4 KiB). **Configuración actual: `--bank2
  --bank2-mb 1536`, `vm_compression_limit=98304`, `cpus=8`: 1.5 GiB,
  arranca.**
- **GPU Mali-T880 (0225/0226):** el dominio G3D y los relojes ya vienen
  encendidos de S-Boot; `GPU_ID=0x08802000` (Mali-T880 r2p0), 12 shader
  cores (`0xff0f`), 1 tiler, 1 L2. Con `herogpu=3`: L2, shader core 0 y
  tiler encendidos (ready `0x1`) y **primer trabajo en la GPU**:
  `WRITE_VALUE` en JS1/AS0 con `irq=0x2 mmu=0 exception=1 output=0`, sin
  fallos y sin afectar a iOS.
- **🎨 La GPU dibuja (0227–0230, 2026-10-24):** el descriptor simple de la
  T720 (SFBD) da `DATA_INVALID_FAULT`; con el multi-target de Mesa v5
  (MFBD) y el tiler "desactivado con jerarquía" (máscara 4096, cabecera de
  512 bytes) el fragment job escribe **256/256 píxeles** en memoria
  privada, y con `herogpu=6` **pinta toda la pantalla 1440x2560 de verde
  en 16.6 ms con un solo shader core** (foto del usuario). La copia de iOS
  se pausa 8 s (`sweet_fb_hold_until`) para que se vea.
- **0231:** los **12 shader cores** (`0xff0f`) encienden con la tensión de
  S-Boot y pintan la pantalla entera en **3.26 ms** (5× más que un núcleo),
  estable. `COHERENCY_FEATURES=0`: la GPU no ve las cachés de la CPU, así
  que leer una superficie de iOS exige limpiarla antes (3.8 ms, un núcleo).
  La copia por "preload" del render target da `DATA_INVALID_FAULT`; Mesa
  no usa preload en Midgard (copia con un fragment shader). Copiar con la
  GPU frames dibujados por la CPU no compensa: la aceleración real pasa
  por shaders (primero un triángulo) y, a la larga, por traducir lo que
  pide CoreAnimation/Metal.
- **0232/0233: primer dibujo 3D, un triángulo con shader** (foto del
  usuario). Un tiler job (JS1) guarda el triángulo en la lista de
  polígonos (cabecera 32 palabras, cuerpo 48) y un fragment job (JS0)
  limpia la pantalla y ejecuta un shader Midgard de un bundle, ensamblado
  a mano (`tools/herolte-midgard-shader.py`). Todo en 16 ms. En 0232 no
  se veía nada porque el alpha test fijo de Midgard quedó en NEVER; con
  ALWAYS (0233) el triángulo aparece. Sale casi negro (`02020202`): el
  shader escribe r0 como fp32, y las constantes fp16 1.0 se leen como
  ~0.008. Siguiente: texturas → escalado por GPU (iOS a 720p).
- **0234: primera textura, escalado por GPU** (`herogpu=9`, foto del
  usuario). Una imagen de 180x320 se dibuja como un quad de pantalla
  completa con filtro bilineal: la GPU la agranda 8x a 1440x2560. Sin
  vertex shader, como el preload de Mesa: un varying con coordenadas de
  texel sin normalizar. Shader de 4 bundles ensamblado a mano (ld_vary,
  imov a r28, textura, writeout). Los píxeles leídos coinciden con sus
  texels, y en el borde de un cuadro sale la mezcla del filtro.
  **3.26 ms con los 12 cores** (34 ms con uno). Siguiente: que iOS
  dibuje a 720x1280 y la GPU escale cada frame a la pantalla.
- **0235: iOS en pantalla a través de la GPU** (`sweetfb_scale=1
  sweetfb_gpu=1`). Cada frame de iOS es la textura del quad de 0234:
  ~4.4 ms por frame con la limpieza de caché, sin fallos. Más fluido, pero
  el cuello de botella es CoreAnimation dibujando en la CPU (3-11 fps según
  la pantalla). 960x1706 son 320 puntos @3x, más angosto que cualquier
  iPhone de iOS 16: la interfaz se rompe. 1125x2001 (0236) tampoco sirve:
  UIKit elige la barra de estado por ancho en píxeles y notch.
- **0237:** como syncmodz/ios-s9, el ADT describe un iPhone XR entero
  (`--scale2`: 828x1792 @2x, subtype 1792). La GPU lo dibuja a alto
  completo con barras negras a los lados; el touch se normaliza sobre esa
  franja. Pendiente de probar.
- **0238 (de ios-s9):** los hilos de UI y render van a los Mongoose
  (cpus 4-7) en vez de los A53, y AppleKeyStore responde wrap/unwrap
  (securityd reintentaba sin fin y cada llamada iba al log). Probado:
  más fluido, log de AKS de 1600 a 19 líneas. El XR deja barras negras y
  el Centro de Control sin blur (fondo negro: el blur es de Metal).
- **0239: HeroGPU, etapa 1 de la aceleración completa.** Servicio IOKit
  para que procesos de iOS usen la Mali (GetParam con los números de
  Panfrost, CreateBO/FreeBO/MapBO, Submit). Selftest en el teléfono:
  `GPU_ID 0x880 rev 0x2000 shaders 0xff0f`, un WRITE_VALUE desde un buffer
  de usuario en VA 0x40000000 → **OK en 115 µs**. Siguiente: Mesa Panfrost
  compilado para iOS con un libdrm sobre HeroGPU (como Bergamota con
  freedreno), luego la capa Metal de Chlorophyll.
- **0240-0242: programas de iOS en la GPU.** Zona de "drop" en USERDATA
  (`tools/herolte-drop.py` desde TWRP, el kernel la instala en
  `/private/var/herolte/` cuando la raíz pasa a lectura-escritura; launchd
  corre `autorun`). 0242 corrige `pmap_sync_page_attributes_phys`, que
  truncaba direcciones físicas sobre 4 GiB (panic en MapBO). Probado con
  `herogpu-test` desde iOS: los parámetros de Panfrost, WRITE_VALUE → OK en
  358 µs y un FRAGMENT clear de 64x64 → **4096/4096 píxeles OK en 197 µs**.
- **Etapa 2 (`gpu/mesa`, workflow `mesa-ios`):** Mesa 25.0.7 Panfrost
  (Gallium + compilador Midgard) dentro de OSMesa, compilado para iOS, con
  un libdrm que traduce los ioctl de Panfrost a HeroGPU. `osmesa-test`
  dibuja un triángulo con OpenGL y mide fps; resultado en el log del kernel.
- **Primer OpenGL en la Mali desde iOS.** `GL_RENDERER = Mali-T880
  (Panfrost)`, GL 2.1. Hicieron falta dos arreglos: 0243 configura la GPU
  como Linux para un T880 r2p0 (`SHADER_CONFIG.LS_ALLOW_ATTR_TYPES`,
  clock gate del tiler, throttle del JM), y el libdrm devuelve a Mesa el
  tamaño real del heap del tiler (32 MiB, no los 128 pedidos: el tiler
  escribía sobre otros buffers → DATA_INVALID_FAULT 0x58). Resultado: sin
  fallos, centro rojo `0xff0000ff`, fondo azul, 8192 píxeles del triángulo
  exactos; **256x256 a 159 fps** con `glFinish` en cada frame. Siguiente:
  la capa Metal de Chlorophyll sobre este Panfrost, para CoreAnimation.
- `sweetfb_scale=1` (0222) muestra la imagen rayada y duplicada (las
  superficies a 960x1706 tienen otro formato): queda desactivado.
- Pendiente: nodo `/product` del ADT a partir del IPSW; root (UFS).

## 2026-10-31: aceleración por GPU usable

- Resolución interna de iPhone 8 (750x1334 @2x, `mkadt_herolte.py --iphone8`), escalada por la GPU al panel. La fluidez mejora mucho.
- Boot args: `sweetfb_native=1 sweetfb_scale=1 sweetfb_lw=750 sweetfb_lh=1334 sweetfb_gpu=1 herogpu_mhz=650 herocpu_mhz=2600 herosb=1`.
- Medido: Mongoose 2598 MHz a 1075 mV, GPU 650 MHz. En reposo 7-22 % de 800 % de CPU.
- `hero-run` mueve `BTAudioHALPlugin` fuera de `HAL/`: `launchd` y `mediaserverd` dejan de gastar CPU. La pista es de ios-s9.
- Fondo: imagen fija desde SpringBoard (`herosb.c`, `herosb=1`). No hay proveedores de PosterBoard, la galería sigue vacía.
- Lista de servicios desactivados: `tools/herolte-disabled.list`, copiada como `disabled.list` a la zona de drop. Con 41 servicios SpringBoard no dibujaba: algún servicio de los otros 13 es necesario, sin identificar.
- Gestos: con `home-button-type` 2 aparece la barra roja. Con 1 no hay barra, pero tampoco gestos. Forzar `_UIStatusBarVisualProvider_Phone` en SpringBoard lo hace cerrarse; `gestures.off` en la zona de drop deja esos ganchos apagados.
- `JOB_READ_FAULT` (0x42): tras él ni un trabajo en memoria del kernel corre; no lo curan hard reset ni apagar el dominio G3D. No se vio desde el cambio de resolución, en pocas pruebas. Causa desconocida.
- Falta: límite térmico, audio, Wi-Fi.
## Pantalla a 60 Hz reales (0296-0297)

El bootloader deja el vclk de DECON_F en el oscilador de 26 MHz (`MUX_DISP_PLL`, CMU_DISP0 +0x200, bit 12 en 0): 363 ciclos por línea, 35,8 ms por cuadro, un TE de cada tres, 20 Hz, aunque iOS dibujara 40-50 fps. Con el vclk en DISP_PLL (62,5 MHz): 14,88 ms por cuadro, período 16,74 ms (59,7 Hz), medido con el contador de líneas (DECON +0x8c). Sin relación: eclk, relojes de bus, MULTI_PKT_CNT. Los cortes horizontales siguen: un solo cuadro en memoria, reescrito mientras DECON lo lee.

## Sonido en iOS (0300-0303)

El I2S está en reset hasta `CON_RSTCLR` (+0x00 bit 31); sin eso una escritura traba un núcleo. MOD: OPCLK de PCLK, CDCLK de entrada, esclavo. `heroaudio=3`: `/dev/hakios-audio` antes de que arranque mediaserverd y el plug-in AudioServerPlugIn de HakiOS (`gpu/hakios-audio`, MIT) en `/System/Library/Audio/Plug-Ins/HAL/HakiosAudio.driver`. El kernel alimenta el FIFO a mano, por tiempo. Probado: tono de llamada y teclado por el parlante, barra de volumen.

- **Extensiones, GPU y Wi-Fi (2026-11-01):** el kernel ahora responde la consulta `0x60` de AMFI (idea del kernel del JM21): iOS pasa de 1 a 516 plug-ins y aparecen widgets y fondos. El cuelgue que siguió era un bug propio: la tabla L3 número 176 del pool de usuario caía sobre el nivel 0 de la GPU (`0x8ffc0000`), a unos 350 MB de buffers, y ningún reset lo arreglaba; `0307` le da al pool su bloque en `0x8fc00000`. Wi-Fi: con el orden y los tiempos de Samsung el enlace PCIe sube al primer intento, `14e4:4415`, ChipCommon `0x17094359`. Falta firmware y driver. Pendiente: `CalendarWidgetExtension` usa 2 núcleos unos 7 minutos tras cada arranque y launchd reintenta `AegirPoster`.
- **Wi-Fi escanea (0308-0311, 2026-11-02):** `bsd/dev/herolte_wifi.c` carga el firmware del teléfono (de VENDOR, en la zona de drop, fuera del repositorio) en la TCM como brcmfmac y lo arranca: RTE 9.96.17 en BCM43596 C0. Colas msgbuf en RAM del host (`0x8f000000`, 1 MB), ioctls por la cola de control: `cur_etheraddr`, `ver`, CLM, `WLC_UP`, `event_msgs` y `escan`; el primer escaneo vio 11 redes en 2,4 y 5 GHz. `0310` agranda el io_map a 64 MB. Falta: asociarse con WPA2, el camino de datos y la interfaz para iOS.
- **WPA2 (0312-0313):** con `sup_wpa=1` el firmware responde -23 (BCME_UNSUPPORTED): el de Samsung no trae supplicant (Android usa wpa_supplicant). En 0312 se asocia y el enlace sube, pero el AP lo echa cada ~5 s con razón 15 (timeout del 4-way handshake), 33 s sin claves. `0313` hace el handshake en el kernel como wpa_supplicant: buffers en el anillo rx, un flow ring hacia el AP, nuestro elemento RSN por `wpaie`, PMK por PBKDF2, PTK, MIC, desenvuelto AES de la GTK y claves por `wsec_key`; después un DHCP DISCOVER a broadcast para probar las dos claves. SHA-1/HMAC/PBKDF2/AES escritos en el archivo (el kernel solo trae SHA-256), verificados en una transcripción a Python contra hashlib e IEEE/RFC 3394, y de nuevo en el teléfono al arrancar.
- **📶 Wi-Fi conectado con WPA2 (0313, run 41519331439, kernel `8c2f42a5…acaf`, log `wifi-0313`):** `crypto check: PBKDF2 ok, AES key unwrap ok`, PMK en 18 ms, `wpaie 0`, flow ring 2 abierto, handshake 1/4→2/4 y 3/4→4/4 (GTK índice 1, 16 bytes), `keys: pairwise 0, group 0`, **`CONNECTED with WPA2 in 1649 ms`** (-46 dBm) y **`DHCP OFFER: 192.168.1.25 from 192.168.1.1`** enviada a broadcast: las dos claves funcionan; 3 de 3 frames enviados. Las BOOT de prueba de Wi-Fi (0310-0313) usaban una línea sin `heroaudio=3` (por eso no había sonido); BOOT diaria `xnu-boot-0313-daily` = línea diaria + `herowifi=1`, sin `herotwrp`. Falta: drenar los anillos siempre (hilo), `en0` y Apple80211 para iOS.
- `0314` (en0 para iOS): las capas de apollo (xnu 0128-0135, de HackiOS, APSL 2.0) para el mismo xnu-8796 e iOS 16.7.16: `sweet_net.c` (en0 con la KPI de interfaces), `sweet_sta.c`, `sweet_apple80211.c` (las peticiones de wifid), `SweetWLAN.cpp` e `IONetworkStack` (`SweetNetworkStack.cpp`, con el sustituto del demonio de IOKit; `herowifiquiet=0` lo quita). `herolte_wifi.c` es el enlace y la estación debajo: hilo de servicio (1-5 ms), escaneos y uniones pedidos por wifid, salida de en0 por una cola, la dirección del ADT (`mac-address-wifi0`) puesta en el firmware con `cur_etheraddr`, `network.txt` como red fija. en0 se crea en `bsdinit_task` antes de launchd.
- **🌐 Internet por Wi-Fi en iOS (0314, run 41525337235, kernel `1bb58e29…4649`, log `wifi-0314`):** en0 hecho antes de launchd, `SweetNetworkStack: opened by configd; busy state 0`, la estación conecta sola a la red fija (1727 ms) y `en0's link (the BCM4359) is up`; configd lee SSID/BSSID/AUTH_TYPE; **`en0 so far 9391 frames sent, 11076 received (15154960 bytes)`**. Safari intenta cargar apple.com (parpadea blanco/negro: dibujo, no red). Sin ícono de Wi-Fi: **wifid no se lanza nunca** (ninguna petición de wifid): su job tiene `_LimitLoadToDeviceTree = ("wlan", "marconi-wifi")` y el ADT no tenía `wlan` (apollo, boot 53). `mkadt_herolte.py` agrega `/arm-io/wlan`; BOOT `xnu-boot-0314-wlan` = la diaria con ese nodo, sin probar todavía.
- **Con wlan (log `wifi-0314w`):** wifid arranca y habla (CARD_CAPABILITIES, POWER, RSSI_BOUNDS, escaneos; ícono de Wi-Fi). Safari parpadea: WebContent se lanza 56 veces y muere con `sig 11, pc 0x0`, `lr` fuera de la dyld cache; simbolizado: `WebCore::Document::resolveStyle` → código del JIT de selectores CSS que salta a 0. Calor: `CalendarWidgetExtension` al 200 % varios minutos y `xpcproxy` relanzando WebContent; el kernel en reposo 5-6 %. La línea de arranque diaria + `herowifi=1` pasaba los 607 caracteres y cortaba `sweetsample=-`.
- `0315`: `mmap(MAP_JIT)` rechazado (`herojit=1` lo permite), como para una app sin dynamic-codesigning; Wi-Fi encendido por defecto (`herowifi=0` lo apaga) y en cuanto está `wifi/fw.bin` (antes 45 s fijos); `CalendarWidgetExtension` no arranca (como `AegirPoster`); `WLC_SET_PM` 2 al conectar; el hilo del chip duerme 20 ms en reposo. BOOT: la línea diaria sin `herowifi=1`.
- **0315 en el teléfono (log `boot-0315`):** Wi-Fi a 1 s de tener los archivos, conecta en 1,6 s. `HEROLTE JIT: com.apple.WebKit asks for JIT memory: refused`: WebContent ya no cae en loop (5 lanzamientos, no 56) y llega a dibujar, pero la página se ve **negra**; 2 de 5 mueren con `sig 5` en `_WebContentServiceInitializer` → JavaScriptCore. Rechazar `CalendarWidgetExtension` fue peor: SpringBoard, widgets de Mapas y Game Center al 150-390 % pidiéndolo (todo 800-1300 %). `0316` lo deja arrancar de nuevo.
- **Negro de Safari y fondos que faltan: caché de la CPU.** En `hakios-gl` (eagl.c) una imagen "compartida" (la textura es la memoria del IOSurface) que otro proceso dibuja con la CPU nunca se sincronizaba: `my_glBindTexture` y el bucle de inicio de cuadro saltan las compartidas ("una GPU que tiene la memoria muestra lo que hay"), y la Mali no es coherente (`COHERENCY_FEATURES=0`): lee la RAM vieja. Cada cuadro decía `0 textures refilled`. Ahora `shared_picture_fresh()` limpia la caché del IOSurface (SyncBO de HeroGPU) cuando su seed cambia y cada 30 cuadros. Sin probar.
- **0316 + hakios-gl con limpieza de caché (log `boot-0316`):** las limpiezas ocurren (20 anotadas), pero sigue igual: el fondo original de iOS 16 negro (algunos fondos sí andan) y Safari negro. Los fondos de iOS llegan como **ASTC 4x4** (`0x93b0`, 750x1334, 1004672 bytes): la T880 los acepta sin error y salen negros. `herodrm` ahora oculta a Panfrost los bits ASTC de `TEXTURE_FEATURES0` (20-23; `HERO_ASTC=1` los deja) y Mesa los decodifica por CPU al subirlos. Safari: el registro de creaciones de IOSurface se corta en las primeras 64 del arranque y los selectores se anotan una vez para todos, así que no se sabe qué pide WebKit; `0317` anota aparte las primeras 160 llamadas de WebKit/Safari con su respuesta. Además: `SWEET Sandbox: com.apple.WebKit.Ne privilege 10001 denied`.
- **0317 (log `boot-0317`):** `texture features 0xfffe003f: ASTC hidden` (pero en ese arranque no hubo subidas ASTC). Las llamadas de WebKit a IOSurface: crea superficies sin error (sel 0), puertos (35), sel 20/44/9; el proceso GPU de WebKit dibuja las páginas en superficies de 10 bits **`'w30r'` (750x1024) y `'b3a8'`**, y backboardd nunca hace textura de ningún formato de 10 bits "mostrado" (solo BGRA/RGBA de 8 bits): CoreAnimation sobre nuestro OpenGL ES no los muestra → negro. Causa: `/product artwork-display-gamut = "P3"` (iPhone X). `mkadt_herolte.py` pone `"sRGB"`; BOOT `xnu-boot-0317-srgb` = 0317 con ese ADT, sin probar.
- **Con el ADT sRGB (logs `boot-0317s`, `boot-0317s2`):** PosterBoard pasa a superficies `'BGRA'` (antes `'b3a8'`), pero el proceso GPU de WebKit sigue con `'b3a8'` (23) y `'w30r'` (5); Safari y el fondo original siguen negros. Desensamblado `WebCore::screenSupportsExtendedColor`: usa lo que le pasa el proceso de interfaz y si no, `MGGetBoolAnswer` con la clave ofuscada `Aixt/MEN2O2B7f+8m4TxUA`: la respuesta P3 sigue en la caché de MobileGestalt. `hero-run` borra una vez `SystemGroup/*/Library/Caches/com.apple.MobileGestalt.plist` (`mgcache.gone`); vale desde el arranque siguiente.

## Ideas del S9 (Scion, 2026-11-06)

Scion (fork de HakiOS, Galaxy S9) muestra la imagen sin copiarla (`fb_zc`, su PR 160): la superficie de pantalla de backboardd sale de un pool contiguo bajo 4 GiB y el IDMA de la pantalla apunta a ella en el siguiente refresco; el escalado lo hace el hardware de pantalla (VGF0). Además: `fb_ca_hz=120` (CoreAnimation a 120 Hz) fue su mayor ganancia, y la limpieza de caché de la GPU salta las páginas del pool (dos de 11 MB menos por cuadro). Sus fondos no están documentados.

Para el 8890 (kernel de Samsung `drivers/video/fbdev/exynos/decon_8890`, GPL; copia local en `C:\Users\amanc\herolte\ref`, fuera del repo):
- Canales IDMA: G0 `0x13951000`, G1 `0x13952000`, VG0 `0x13953000`, VG1 `0x13954000` (DISP0); G2/G3/VGR0/VGR1 `0x13e01000-0x13e04000` (DISP1). Los VG/VGR escalan (`VG_H_RATIO` 0x44, `VG_V_RATIO` 0x48).
- Dirección de lectura: `VG_BASE_ADDR_Y(n)` = 0x74 + 4n, sombra en 0xb74; tamaño en `VG_SRC_SIZE` 0x10 / `VG_IMG_SIZE` 0x18; `VG_PINGPONG_UPDATE` 0x1c.
- DECON_F: `WIN_CONTROL(w)` = 0x130 + 0x20w, canal en bits 14:12 (CHMAP); `SHADOW_REG_UPDATE_REQ` 0x60.
- **0320 (log `boot-0320`):** S-Boot usa la ventana 0 → canal **G1** (`0x13952000`): `IN_CON 0xff800000`, `SRC_SIZE 0xa0005a0`, `BASE_ADDR_Y(0) = 0xe2a00000`, sombra igual. G1 no escala.
- **0321-0323 + herosb/hero-run (2026-11-06, sin probar):** de Scion/S9+ (`danstronics/ios-s9plus-exynos`): 0321 hilos de interfaz de un A53 a un Mongoose apenas queda libre (su `sched_slow_secondaries`); 0322 doble buffer en G1 (segundo buffer `0x91000000`, `herofb2=0` lo apaga); 0323 sin timer coalescing (`sweetfb_tcoal=1` lo deja) e `IOMFBDisplayRefresh` 120 Hz (`sweetfb_cahz`); herosb sube a 60 los `CAFrameRateRange` de SpringBoard (`fps.off`); hero-run pasa widgets y demonios pesados a `PRIO_DARWIN_BG` (`widgets.fg`); CPU a 2288 MHz. CollectionsPoster ahora muere por SIGSEGV (`far` = fin de página) sin mensaje: falta simbolizar.
- **0323 en el teléfono (log `boot-0323`, "funciona muy bien"):** `HEROLTE FB2: two buffers` con flips alternando, `timer coalescing off; CoreAnimation told 120 Hz`, Mongoose a 2288 MHz, herosb sube los topes de fps. Sin muertes de jetsam (la RAM no limita hoy).
- **Fondo original (Clownfish):** el plist está bien y los `.ca` existen; `Background.HEIC` (1,4 MB) se decodifica (hero-run: `UIImage {460, 604}`). CollectionsPoster ya no muere en 0323, pero solo crea una superficie de 1x1 y ninguna textura del tamaño del fondo llega a backboardd. El SIGSEGV de 0320 fue en malloc dentro de `-[WKLegacyWallpaperBundleLoader _loadAllValidWallpaperBundlesFromLegacyLocation]` → `wk_colorWithHexString` (intermitente). Siguiente: muestras de `sweetsample=CollectionsPoste,PosterBoard` (BOOT `0323s`).
- Crashes simbolizados (boot-0323, `tools/herolte-dsc-sym.py`): Siri TTS/Kona/MacinTalk excepción en el arranque de PlugInKit (relanzados en loop); MusicWidgets `strlen(NULL)` en `-[MPMediaLibrary _MediaLibrary_coreLibrary]`; PassbookWidgets aserción Swift en FinanceKitUI; assetsd/mediaserverd excepción no atrapada en dispatch.
- **0324-0325 (log `boot-0325`):** límite de CPU de XNU (30 % de un núcleo) para los procesos con "Widge" en el nombre, y fuera los sintetizadores de voz que abortaban en loop: CPU en reposo de 225-290 % a 29-34 % de 800 %, CalendarWidgetExtension de 199 % a ~58 %, 0 crashes de TTS (antes 54).
- **🧠 ~3 GiB de RAM (0326-0329, 2026-11-07, "va de 10"):** port del `1512-sparse-ram-banks` de Scion/danstronics más cuatro arreglos propios del S7, donde los bancos extra están *debajo* del banco de arranque: (1) sin `kprintf` dentro de `arm_vm_init` (el UART se mapea recién en `serial_init`: cuelgue mudo en la etapa 7); (2) `pmap_object` por índice de página, no `pa - gPhysBase` (negativo: `vm_page_insert_internal ... past object bounds`); (3) fuera las zonas que S-Boot da en la línea de Linux y no en el DTB (`ess_setup=0x91200000`, `sec_tima_log=0x200000@0x92e02000`, `sec_avc_log`, `auto_summary_log`; TWRP `/proc/cmdline`); (4) VA de cada banco congruente con su PA (`ARM64_GRANULE_ALLOW_BLOCK`): el shim pagina en 4 KiB y `topOfKernelData` quedaba a 4 KiB de una página de 16 KiB, las sub-tablas de una página nunca se juntaban y fallaba el assert `tt_entry_free` de `pmap_destroy`. Bancos: `tools/herolte-adt-ram-banks.py` (3058 MiB).
- Las superficies de iOS están en el banco 2 (`0x880000000`): el IDMA es de 32 bits, así que no se pueden mostrar directo. Plan: doble buffer propio bajo 4 GiB (ventana libre `0x90000000-0xb0000000`), la Mali dibuja en el de atrás y se cambia `VG_BASE_ADDR_Y` en el blanking. Sin cortes y sin esperar el hueco de 1,9 ms. Después, escalar por hardware en un canal VG.

- **0330-0331 (2026-11-07, logs `boot-0330`/`boot-0331`):** reposo: con la pantalla apagada (Power) 3 s el clúster Mongoose vuelve a la frecuencia y el voltaje del bootloader (MNGS_PLL M=336 P=3 S=2 = 728 MHz, `vdd_mngs 0x3c` = 675 mV, divisores y EMA guardados antes de subirlo) y a 2288 MHz al encender; vsync a 5 Hz con la pantalla en negro. Funciona (`Mongoose to 728 MHz (screen off)` / `to 2288 MHz`). El TEMP del MAX77854 quedó fijo en 28,0 C (lo escribe Android): el límite térmico usa los cuatro TMU (`0x10060000`/`4000`/`8000`/`c000`, sin relojes propios; TRIMINFO bits 7:0 código a 25 C, 15:8 a 85 C; CURRENT_TEMP 0x40 bits 7:0): 31 C al arrancar, 45 C de pico; con 80 C (`herohot`) baja a 728 MHz, vuelve debajo de 70 C.
- **Apps:** `herolte-drop.py app=FILE.ipa|DIR.app` + hero-run (`/Applications` y LaunchServices). Rechaza binarios cifrados (FairPlay, App Store: el IPA de ipatool lo estaba) y los solo arm64e.
- **Blur negro (Biblioteca de apps, Hoy, Centro de Control), en pausa:** el censo de hakios-gl muestra que ds8/vrd/vrb/vcm se dibujan con nuestros programas y solo 61 "edr" y 66 "lub" (pantalla completa) quedan sin dibujar. Cuadro trazado (`gltrace_at` desde `gl.args`): cada recuadro se arma aparte como rectángulo gris (programa 78, 0,7256) y se pega con programa 0 (sin shader de CoreAnimation), coordenadas de textura en píxeles, y después de ese dibujo el framebuffer no se puede leer. El trazado ahora dice qué función es cada dibujo sin programa (hakios-gl a743004): siguiente paso si se retoma.
## 2026-11-12: reinstalación y fondo original

- **Reinstalación desde HyperOS** (backup de BOOT y EFS en la PC): raíz nueva de 4 partes (`e3cc2519…47c5`), drop con las librerías de 0333, BOOT `0331r`. Los primeros arranques se congelaban a los ~3 min: `hero-run` lanza a los 60 s el migrador de LaunchServices y `_LSPrivateRebuildApplicationDatabasesForSystemApps`; `lsd` al 125-130 % y SpringBoard esperándolo. Cortado, `database2.done` no se escribe y la reconstrucción empieza de nuevo en cada arranque. Con BOOT `0325` y sin tocar el teléfono terminó (`database rebuilt: 1`, 515 plug-ins, el hijo sale con 0) y mató de golpe ~29 extensiones (el fondo negro un momento). Después, `0331r` arranca normal. Pendiente en `hero-run`: marcar la reconstrucción hecha apenas vuelve y no matar al hijo a los 300 s.
- **Fondo original:** `CollectionsPoster` sí lo dibuja (superficies `420f` de 512x512 del HEIC, máscaras `L008`, BGRA de 1105x1160). En backboardd llega por `-texImageIOSurface` como superficie sin formato de 1105x1160 (4448 bytes por fila) que el kernel no pudo atar a la memoria del cliente (`not wired, copied`). El censo de hakios-gl (`c9741a6`, log `boot-c974`) la muestra **toda en cero** (1281800 de 1281800 píxeles): la copia se toma antes de que el cliente dibuje. `0332` ata solo las páginas de los píxeles (el tamaño redondeado puede pasarse del final de lo que el cliente reservó) y, si falla lectura-escritura, prueba solo lectura; anota los dos resultados.
- **Galería de fondos negra:** las miniaturas de 400x400 (también sin formato, copiadas) **sí tienen contenido**: ~40-60 % de píxeles en cero, opacidad en el byte 3 (RGBA), medias de color razonables. El negro de la galería viene de más adelante (dibujo o filtros), no de la copia.
- **0332 en el teléfono (log `boot-0332`, kernel `a0cec9c`):** el fondo ahora llega como 1380x1812 (5536 bytes por fila) y el kernel **sí** lo ata a la memoria del cliente, pero solo para lectura (`read-write 0x2, read 0x0`: la memoria del cliente es de solo lectura); los íconos chicos también se atan. El censo sigue en **cero** (2500560 de 2500560): la memoria misma está vacía cuando backboardd la usa, no es la copia. En la pantalla sigue sin verse. Sospecha siguiente: los mosaicos `420f` de 512x512 que decodifica `CollectionsPoster` (HEIC por VideoToolbox, sin decodificador HEVC por hardware en este teléfono) salen vacíos; falta un censo de esos mosaicos dentro de `CollectionsPoster` (libheroapp).
- **Causa del fondo original (log `boot-heic`, libheroapp `21943b5`+):** dentro de `CollectionsPoster`, `Background.HEIC` del pez abre bien con ImageIO (`public.heic`, 1380x1812) pero dibujado en un bitmap da **0 de 2500560 píxeles** distintos de cero: la decodificación HEIC/HEVC sale vacía sin ningún error (no hay decodificador HEVC por hardware y ImageIO no cae en uno por software). El kernel (0332) y hakios-gl ya no son el problema. Arreglo posible: convertir los HEIC de fondos a PNG al armar la raíz (`sips` en el workflow privado `ios-root`, reescribiendo las referencias del `.ca`), o un decodificador HEIC por software (libheif/libde265) dentro de libheroapp para todo iOS (Fotos y apps también).

## 2026-11-12 (noche): fluidez, la CPU y no la GPU

- **Medido (log `boot-heic`, `boot-prof` con `HERO_PROF=1`):** con movimiento la Mali está ocupada 22-29 % del tiempo; backboardd tarda 18-20 ms de CPU por cuadro (~30 trabajos de GPU por cuadro, ~1100 por segundo) y SpringBoard usa 120-160 %. El perfilador de backboardd: `mach_msg2_trap` 32,7 % y `surface_changed` 12,5 %; Mesa entero 13,9 %.
- **0333 (kernel):** `herolte_gpu_submit()` esperaba cada trabajo girando en `delay(10)`; ahora, después de 4 sondeos, duerme de a 50 us (`herogpu_sleep_us=N`; 0 = como antes). Solo para los trabajos de los clientes (`hg_run_nap`); la presentación y las pruebas de arranque siguen girando. **hakios-gl:** `surface_changed()` suma una octava parte de las filas por cuadro, rotando (un cambio se ve en 8 cuadros), en vez de la superficie entera. Commit `8c57e53`, BOOT `boot-0333.img` (receta de `0331r`: loader sacado de su BOOT, `herolte-banks2.adt`, línea de `payload-0331r.bin`; reproduce `0331r` byte a byte).
- **0333 en el teléfono (log `boot-0333`, poco movimiento):** CPU de backboardd por cuadro mostrado de ~88 ms (4 ventanas con >=15 fps en `boot-prof`) a ~60 ms (1 ventana). Muestra chica: hay que repetir con el mismo uso. En reposo `mach_msg2_trap` sigue en ~33 % de las muestras: lo que queda parece ser la copia a pantalla del kernel (`avg_copy_us` 3-5,5 ms por cuadro, ~17 % de un núcleo a 30 fps). Siguiente: presentar sin copia (como el `fb_zc` de Scion) y bajar los ~30 trabajos por cuadro.
- Drop final con hakios-gl `8c57e53` y sin `HERO_PROF`; BOOT `0333`. Teléfono apagado.

## 2026-11-13: presentación dormida y fondos en PNG

- **0334:** el trabajo de escalado de cada cuadro (`sweetfb_gpu=1`, 3-5 ms) también se espera durmiendo (`hgp_draw_locked` desde `AppleCLCD::present()` en el work loop, con solo `hg_mtx`); `herogpu_sleep_present=0` gira como antes. **En el teléfono (BOOT `0334`, drop `6684c12`):** el usuario lo nota más fluido y **calienta menos** que con 0331r/0332.
- **Fondos HEIC como PNG:** `tools/herolte-wallpaper-png.sh` (macOS, `sips`) convierte cada `.HEIC` de `/Library/Wallpaper` a PNG con el mismo nombre; el workflow `ios-root` lo corre y publica `walls.tar.gz` (los de 375w-812h, con `walls/list`). `hero-run` los pone sobre los HEIC desde el drop (`walls/N`, `walls/list`), sin reflashear la raíz. El workflow pasó a `macos-15` (`macos-14` ya no existe: el primer intento se canceló al instante).
- Scion (S9, Exynos 9810) tiene decodificación H.264/HEVC por hardware con el MFC v10 (`drivers/media/mfc/hakios.exynos_mfc.c`, APSL) y pantalla sin copia (`fb_zc`, pool bajo 4 GiB en `hakios.exynos_dpu.c`): candidatos para el S7 (8890: MFC de la misma familia; IDMA de 32 bits como el 9810).
- **🐟 Fondo original de iOS 16 en pantalla (2026-11-14):** `walls.tar.gz` de la release `ios-root-16.7.16-43472966859` (16 PNG, pez y WWDC 2022), rellenados a anchos múltiplos de 8 px (`tools/herolte-png-pad8.py`) y puestos por `hero-run` (log `boot-walls8`: `15 put`; censo en CollectionsPoster `public.png`, 2507808 de 2507808 píxeles con color). El crash de backboardd al abrir la galería (SIGSEGV en el memmove de QuartzCore, imagen de 5128192 bytes) venía de `ask_for_old_wallpaper()` de `hero-run` (SBSUIWallpaperSetImages con el pez): apagado salvo `oldwallpaper.on` (`54b4a00`). Sin crash ahora.
- **Galería de fondos:** sigue con miniaturas negras/blancas. Weather y Astronomy dibujan con Metal. `drawViewHierarchyInRect:afterScreenUpdates:` en vez de `renderInContext` para las vistas previas de PosterBoard (`b988536`, `preview.cpu` vuelve atrás) no cambió nada visible; no crashea. Pendiente: ver si las miniaturas pasan por los filtros/blur (el negro de los blurs) o por superficies del póster.
- **Blur del Centro de Control: funciona** (2026-11-14, el usuario lo ve desenfocado). Rastreos `boot-blur`, `boot-cc*`: las funciones 61 (`edr`) y 66 (`lub`) no son del blur: aparecen en todos los cuadros (ajuste final de la pantalla, valores neutros: `edr` [inf 1], `lub` [0.05 1 1]) y no dibujarlas no cambia nada. `gltrace_draws=N` ahora dispara con N o más (`c6165d1`).
- **Perfil con 0334 (logs `boot-prof2`, `boot-prof3`):** fps máximo 44,4 (antes 38,6); `surface_changed` 0,9 % (antes 12,5 %); GPU 23-33 %. `mach_msg2_trap` sigue en ~36 % de las muestras de backboardd. Llamadas a HeroGPU por 5 s con movimiento (`de36f17`): submit ~4700-5200 (1,65 s de pared, casi todo durmiendo), syncbo 150-175 (180-260 ms: limpieza de caché, ~1,3 ms cada una), create ~50-120 (35-46 ms), map ~50-110 (14-18 ms): ~0,1 núcleo en total; el resto del tiempo en el kernel no es HeroGPU (IOSurface, IOMobileFramebuffer, mensajes de CoreAnimation). La presentación cuesta `avg_copy_us` ~5 ms por cuadro (escalado por la GPU + `dc cvac` de 4 MB) y retiene `hg_mtx` mientras tanto: los trabajos de backboardd esperan. Siguiente: pantalla sin copia con escalado por hardware (VG de DECON_F, superficies de backboardd en un pool bajo 4 GiB), como el `fb_zc` de Scion.

## 2026-11-14: escalado por hardware (VGR0)

- **0335 (log `boot-0335`, solo lectura):** a los 30 s DISP1 está encendido (`status 0x3000f`), VGR0 (`0x13e03000`) parado (ratio 0x100000, IRQ 0x36) y su SysMMU (`0x13e30000`) deshabilitada y bloqueada (`ctrl 0x3`). DECON_F: `RESOURCE_OCCUPANCY_INFO_1 0x100000`, `RESOURCE_SEL_1 0x33033333` (el nibble de VGR0 distinto).
- **0336 (log `boot-0336`):** a los 40 s, SysMMU a `0` (bypass), VGR0 programado como `vpp_reg_8890.c` (750x1334 → 1440x2560, ratios 0x85555/0x85666, coeficientes de `vpp_coef.h`) leyendo una imagen de prueba en `0x92000000`, y la ventana 0 al canal 5 por 8 s. VGR0: `enable 0x4` (OP_STATUS), `irq 0x10001` (**FRAMEDONE**, sin error de lectura ni deadlock); DECON siguió a 60 Hz después (11 cuadros en 200 ms). Nadie miró la pantalla durante la prueba. **Después quedó el logo de Apple para siempre**, con iOS andando por detrás: la prueba coincidió con los flips de FB2 de backboardd; el flip 5 (a FB2) no se tomó, `hfb_give_up` vio la sombra ya en FB y no reescribió `0x74`, y al volver G1 tomó ese flip pendiente: mostró el cuadro viejo de FB2 mientras la GPU dibujaba en FB.
- **0337 (`753a4d6`):** `hfb_give_up` siempre apunta G1 a FB; la prueba corre a los 3 s del hilo de bus (antes de cualquier presentación, y no si los flips ya empezaron) y anota estado de DECON, interrupciones pendientes, ocupación de recursos y una medida de cuadros con VGR0 y de nuevo con G1.- **0337 en el teléfono (log `boot-0337`):** el usuario vio la imagen de prueba (cuatro colores, pantalla completa) y después iOS arrancó normal. Con la ventana 0 en VGR0 el panel recibió un cuadro cada 83,7 ms (75,5 ms leyéndolo, `pend` con bit 8 de FIFO): VGR0 en el oscilador de 26 MHz. De vuelta en G1, 60 Hz.
- **0338 (`dbe14cd`, BOOT `boot-0338b.img`):** los cuadros de iOS van por VGR0. La Mali dibuja el cuadro 1:1 (750x1334, 768 píxeles por fila) en FB o FB2 y VGR0 lo escala al panel, con los mismos dos buffers y flips (registros base/pingpong/sombra iguales a G1). La ventana 0 vuelve a G1 en FB cuando la CPU escribe el panel (copia de respaldo, fundido al apagar) y regresa a VGR0 en un cuadro de GPU posterior (como mucho una vez por segundo); error de lectura o flip no tomado: G1 para siempre. Relojes: los user mux `ACLK_DISP1_0_400_USER`/`ACLK_DISP1_1_400_USER` de CMU_DISP1 (`0x13F00000` +0x200/+0x204, bit 12; `clk-exynos8890.c` de Linux) pasan del oscilador a `gout_top_aclk_disp1_*_400` de CMU_TOP (`herovgrclk=0` los deja). La primera vez se miden los cuadros del panel: menos de 10 en 200 ms, vuelve a G1 para siempre. `herovgr=0` deja el escalado en la GPU; la prueba de colores pide `herovgrtest=1`. **En el teléfono: "más fluido"** (2026-11-14); falta el log.
## 2026-11-14 (noche): vibración y primer paso del decodificador de video

- **0339-0341: motor de vibración.** Del árbol de dispositivos del propio teléfono (TWRP `/proc/device-tree`, copia en `priv\dt-twrp`): `/haptic` pwm_id 1, período 37950 ns, duty 32500 ns, reg2 0x82, regulador `VDD_MOT_3.3V` = LDO34 del S2MPS16; `pwm@136c0000`, TOUT1 en gpd0-5 función 2; relojes del PWM en CMU_PERIC0 (+0x800 bit 8, +0x844 bit 0). El bloque háptico del MAX77854 (0x66, en el bus del medidor de batería, que ahora tiene un candado) como el MAX77705 de Scion (S9). `/dev/hakios-haptic` recibe las muestras del Actuator del plug-in de audio. 0339: S-Boot deja el prescaler 0 del PWM en 0x41 (15 pasos por período) y el motor se rechazaba; 0341 lo pone en 0 (987 pasos de 26 MHz). **El motor vibra** (prueba de medio segundo al arrancar, sentida). `herohaptic=0` sin motor, `herohaptictest=0` sin la prueba.
- **iOS todavía no lo usa.** `mkadt_herolte.py` agrega `/product/haptics` (closed-loop 1, supports-3rd-party-haptics 1, del DeviceTree.d22ap del IPSW 16.7.16); BOOT `0341` con `priv\herolte-banks3.adt`. `hero-run` borra el caché de MobileGestalt cuando cambia `mgcache.token` del drop. MobileGestalt responde `DeviceSupportsClosedLoopHaptics = true`, pero `AudioServicesPlaySystemSound(4095)` (sonda `haptics.probe` en hero-run) no inicia nunca la E/S del Actuator en mediaserverd. Diagnóstico en curso: `hero-oslog` (registro en vivo de logd con LoggingSupport, como test de hero-run) y una prueba de CoreHaptics con sus errores. Scion corre antes `sound_test springboard route`.
- **0340: MFC (sondeo de solo lectura).** `mfc0@152E0000` (ip_ver 0xe, 400 MHz, SPI 302), dominio `pd-mfc` PMU 0x105c4180, dos SysMMU (0x15200000, 0x15220000). En el arranque el dominio está **encendido** (`status 0x3000f`) y `ACLK_MFC_600` habilitado (`enable 0x1`). El firmware `mfc_fw.bin` (778268 bytes) está en la partición VENDOR (copia en `priv\fw`). Referencia: `hakios.exynos_mfc.c` de Scion (MFC v10, 9810) y su decodificador para VideoToolbox (`mfc_decoder.c`).
- Drop: `priv\drop-20261114` (gl.env sin `HERO_PROF`, `mgcache.token`, `haptics.probe`).
## 2026-11-15: el trabajo del Note FE en el S7 (0342-0344)

- **0342:** los parches de kernel del port del Galaxy Note FE (egemengunel/ios-a5xelte, rama `gracerlte`, 76abd2e; el mismo Exynos 8890, que partió de este port en 0331) fusionados a tres vías sobre 0332-0341, en un solo parche. Afuera: 0400 (dirección del panel del Note FE) y 0402 (voltajes ASV de ese chip). Conflictos: el bus del medidor lleva el motor (0339) y el cargador (0406/0411) bajo un candado; `hg_run()` espera la interrupción de la GPU (0415) o duerme (0333). Árbol de trabajo: `merge-notefe2` (fuera del repo), base sacada del buildtree de CI de 0341.
- **0343:** piso de brillo 64/255 (`herobrightmin`): el brillo automático, sin sensor de luz, pedía 1 y la pantalla quedaba negra (boot-0342).
- **0344:** en el S7 la espera por interrupción de la GPU (`herogpuirq`) y la cuenta de llamadas (`notefe_uc`) apagadas por defecto: boot-0342 promediaba 19,5 fps contra 31,4. Sin `herogov` en la línea de arranque; `herocap=coreduetd:20` queda.
- **Cámara frontal: funciona** (S5K4E6; mismos rieles S2MPB02 LDO5/6/7/13 y pines gpc0-4/gpc1-1/gpk0-2 que el Note FE, verificados en el árbol del teléfono). `hero-run` hace la secuencia del bot del Note FE con `cam.level=8` (`kern.notefe_cam=7`, reinicia mediaserverd, MobileGestalt); `gpu/camera` = libnotefecam.dylib, cargada por libheroapp con `cam.media=1`.
- **Bluetooth: funciona** (lista equipos). El módulo del S7 es **Semco** ("BCM4359C0 Grace SWB-B90S" tras el patch `bcm4359C0_semco.hcd` de VENDOR, en el drop como `bt-murata.hcd`). Hizo falta: `bluetoothd` fuera de `heronoexec`, su job con otra etiqueta en `launchd.plist` (drop con destino absoluto; launchd guarda su propia lista de deshabilitados) y el nodo ADT `/arm-io/bluetooth` (`bluetooth,n88`) + `/arm-io/isp` (`priv\herolte-banks4.adt`). BOOT `boot-0344b.img`.
- **El táctil necesita arrancar desde TWRP:** reiniciando desde iOS, la SRAM del APM no tiene su firmware (lo deja Linux/TWRP), el APM no responde y el táctil no tiene alimentación ("no supply").
## 2026-11-15: ¿iOS 18 en el S7? Medido

- **Shared cache de iOS 18.7.8 (iPhone XR, arm64e), `tools/dsc-lse-scan.py` vía `dsc-scan.yml`:** 609 M instrucciones en `__text`; **463.816 atómicas LSE** (iOS 16.7.16 arm64: 990 en 375 M, ninguna en libobjc/CoreFoundation/Foundation/UIKitCore/QuartzCore), 93.674 LDAPR/LDAPUR, **19,6 M operaciones PAC** a reescribir (más 9,2 M en el espacio HINT, NOPs en ARMv8.0). `objc_retain`, `objc_release`, `swift_retain`, `swift_release`, `os_unfair_lock_lock` tienen 1 LSE cada una; `pthread_mutex_lock` 2.
- **Costo de la emulación en el S7 (0345 = v80emu de la rama v80emu-test, `tools/ios/v80stress.c`, log `boot-0345`):** LL/SC nativo 13 ns; LDADDAL emulado **1364 ns (105x)**; LDAPR emulado 1696 ns; una PAC emulada ~1,4 us. Semántica: 31302 comprobaciones sin fallos; 8 hilos x 20000 atómicas mezcladas exactas. 4 fallos en el `si_addr` de las señales por fallo de página (el emulador reporta otra dirección).
- **Conclusión:** emular por trampas los `retain`/`release` (millones por segundo) es inviable; PAC y LDAPR se reescriben 4 bytes por 4 (Renegade de Bergamota; LDAPR -> LDAR); las LSE calientes necesitarían reescribir el cache con saltos a rutinas aparte (las frías pueden quedar en trampas, contando sitios con `kern.v80emu`). Más el kernel xnu-11215 con todos los drivers portados (rama `herolte-ios18`). Grande y sin garantía de quedar usable; el Edge 30 (ARMv8.2, LSE nativo) evita la parte de LSE.
## 2026-11-15 (tarde): iOS 18 en el S7, adelante igual

- **Decisión del usuario:** seguir con iOS 18 en el S7 (20 fps alcanzan; Wi-Fi/BT pueden faltar).
- **Kernel xnu-11215 (rama `herolte-ios18`):** `50fef0c` arregla la compilación (9162: MPIDR_CORETYPE_* en A5XELTE.h, UBSan verifier salteado para HEROLTE; 9079/9084/9095 sin lo que Bergamota ya trae). Compila todo; faltaba el enlace: `b266564` (9163) da stubs a sweet_early_*/sweet_reboot_note_panic y saca SweetAdreno para A5XELTE. Build de b266564 en CI, sin resultado todavía.
- **Cache de iOS 18.7.8 (`tools/dsc-tramp-space.py`, log `logs/dsc-tramp-space.txt`):** 463.816 LSE (ldadd64al 165k, ldadd64 151k, ldadd32* 99k, cas ~37k, casp ~870, swp ~6k). Relleno libre (ceros) entre imágenes: 7,8 MiB en 3836 huecos; dentro de los segmentos: 0. Con rutinas de 64 bytes caben 117.762 (48 B: 148.562); el resto queda en trampas. Hay que ubicar primero las imágenes calientes (libobjc, libswiftCore, libsystem_*, libdispatch, CoreFoundation, Foundation, UIKitCore, QuartzCore); la mayoría de los sitios están en Recon3D, WebCore, AppleCV3D, libusd, VectorKit. Otras clases: LDAPR 93.670, FP16 22.574, FCMA 2.455, SHA3/512 848, FJCVTZS 474, RCpc con desplazamiento 4.
- **`tools/ios18/v80strip.py`:** LDAPR/LDAPUR #0/STLUR #0 -> LDAR/STLR en el lugar; cada LSE -> B a su propia rutina LDXR/STXR (registros temporales guardados bajo la zona roja, NZCV preservado, CASP escribe de vuelta si falla la comparación), LDAPUR/STLUR con desplazamiento -> LDUR+DMB ISHLD / DMB ISH+STUR. `ios-tools` (9a00099) arma `v80stress-r`: 44 sitios reescritos, desensamblado revisado (capstone), ninguna LSE/RCpc restante.
- **Siguiente:** probar `v80stress-r` en el teléfono con iOS 16 (semántica y ns por atómica); modo cache de v80strip con prioridad a imágenes calientes; root de iOS 18 con Renegade (`ref/bergamota/tools/renegade`) + v80strip.
- **Kernel xnu-11215 en el S7 (2026-11-15, rama `herolte-ios18`, root de iOS 16 todavía en USERDATA):** BOOT 18k1/18k2 (`ed5bc42`): sólo marcas 1-7 (la consola A5 se apagaba a propósito en `arm_vm_init`). **9165** deja viva la consola temprana: alias de la pantalla en TTBR1 después de los low globals (con páginas de 4 KiB, `VM_MIN_KERNEL_ADDRESS` + un bloque cae en otra entrada L1 sin tabla; 18k3) y marcas 21-29 dentro de `arm_vm_init`. 18k4 (`baf6902`): pasa todo `arm_vm_init` y `kprintf` (marca 20) y entra en pánico al arrancar los secundarios: `cpu_common.c:855 cpu_signal == SIGPdisabled (0x8)`: la ventana de IRQ de 0208 en `SweetCPU::initCPU` tomaba la SGI propia antes que `processor_cpu_reinit()` de 11215. 18k5 (`cpus=1`, log `boot-18k5`): UFS y root montado, audio (el pitido), Wi-Fi conectado (WPA2), táctil, batería, GPU, APM; `init` queda en `herolte_wifi_early()` sin `en0` (un solo núcleo). **9166** saca esa ventana: 18k6 (`36bc7e8`, 8 núcleos) llega a launchd, y el launchd de iOS 16 sale: `initproc exited -- exit reason namespace 7 subcode 0x1: could not set up inheritance port` (libxpc; el userland de 16 no sirve con el kernel de 18, como se esperaba). v80emu ya estaba en la serie de 11215 (`9157-0400`). Siguiente: la raíz de iOS 18 (workflow `ios18-root`) en USERDATA (el usuario aprobó borrar USERDATA).
- **`v80stress-r` en el S7 (iOS 16, BOOT 0345, log `logs/boot-0345-v80r.txt`): TODO OK, 31.448 comprobaciones, 0 fallos** (los 4 fallos de `si_addr` de la emulación desaparecen: la rutina falla en espacio de usuario con la dirección real). **LDADDAL por rutina 19 ns** contra 14 ns de LL/SC nativo y 1364 ns por trampa; LDAPR -> LDAR 6 ns. Las rutinas de v80strip resuelven el costo de las atómicas de iOS 18.
- `90612e8`: rutinas más cortas (valor viejo directo en Rt cuando se puede: LDADDAL w8,w9,[x10] = 9 palabras) y `tools/ios18/v80strip_cache.py` (cache entero, por prioridad: runtime y UI primero; resto a v80emu; hashes de página recalculados). Plan sobre 18.7.8 en `dsc-scan`.
- **Raíz de iOS 18 en USERDATA (2026-11-16/17, armada en WSL, BOOT 18k12/18k13):** launchd, tareas de arranque y FIPS pasan; SpringBoard y backboardd arrancan y se prende la pantalla. Arreglos en el camino: pads duplicados en `v80strip_cache` (dos rutinas en la misma dirección: launchd moría en `os_unfair_lock_unowned_abort`; `7b219ef` los une y verifica cada rutina), constantes de SHA-256 en `__text` de corecrypto tomadas por atómicas (`d0da131`, capstone 5 como prueba de vecinos). backboardd moría con SIGILL en FP16 (el Exynos 8890 no tiene FEAT_FP16): `5568864` reescribe la aritmética FP16 como rutinas FP32 (`tools/ios18/fp16.py`, probado contra unicorn con `test_fp16.py`). 18k13 seguía igual (`fmov h1, #imm` en QuartzCore): las máscaras escalares del prefiltro nunca coincidían. `b044d8f` las arregla y usa el `__text` de WebGPU (sin inicializadores ni +load, sólo corre con un dispositivo Metal) como espacio: en el cache 22H352 todos los sitios de nivel 0 quedan con rutina (3401 FP16, 16216 atómicas; antes faltaban 886 FP16 de CoreGraphics y 510 atómicas de libobjc).
- **iOS 18.7.8 ARRANCA hasta SpringBoard en el S7 (2026-11-17, BOOT 18k12 + raíz `b044d8f`, fotos del usuario):** pantalla de inicio (girada a horizontal), Centro de control (Wi-Fi marcado encendido, batería 99 %), Ajustes y Acerca de: "iPadOS Version 18.7.8", "Model Name iPhone X", Capacity/Available "Zero KB", Songs/Videos/Photos "Loading...". Este arranque no dejó log nuevo (el leído era idéntico a 18k13). Pendiente de pulir: nombre del SO (iPadOS) y modelo en MobileGestalt, capacidad del disco, Wi-Fi/BT reales en iOS 18, rendimiento, los 22 FP16 de RenderBox sin lugar.
- **Calor de iOS 18 (boot-18k15, `sweettop`): 1100-1400 % de 800 % de CPU.** Widgets (Calendar, Stocks, Weather, WorldClock, HealthBalance...) a ~200 % cada uno, kernel_task 150-210 %, backboardd hasta 424 % (composición por CPU), launchd relanzando cada 10 s lo que heronoexec niega (~40 intentos de analyticsd/homed/cloudd/ReportCrash/searchd en 7 min). La serie 11215 llegaba solo a 0316: sin 0330/0331 no había límite de calor (Mongoose fijo a 2288 MHz). **Arreglos:** `ca49e8b`/`5cdcfda`/`cdcb785` (rama `herolte-ios18`) portan 0317-0325 y 0330-0341 como 9171-9190 (sin RAM banks 0326-0329, ni 0332/0343/0344); 9175 devuelve `false` (bool en 11215); 9178 limita todo nombre con "Wid". Kernel CI run 44157236108 (0 LSE). `c3fe5eb` (rama `herolte`): en builds 22* `herolte-tune-ios-root.sh` saca 31 trabajos de launchd.plist (herolte-disabled.list + heronoexec + spaceattributiond/wifip2pd).
- **Mali en iOS 18:** la tabla de funciones de OpenGLES (`-getMacroContextPrivate`) de iOS 18 es idéntica a la de 16.5 (457/457 entradas), así que `libhakiosgl` (eagl.c + Mesa) debería andar sin cambios; los ganchos de `ca_hooks.c` (direcciones de 16.7) se niegan solos en 18. El paquete de drop de iOS 16 traía `/System/Library/xpc/launchd.plist` de 16 (copia en `priv/drop-ios16-onphone`); se escribió uno para iOS 18 sin launchd.plist, hero-run, libheroapp ni cámara, con `wallpaper.png` (Clownfish). BOOT 18k16g = kernel cdcb785 + `herogl=1 herosb=1`, drop activo, sin `serial=3 -enable_kprintf_spam`; 18k16 = lo mismo sin GL y con `herodrop=0` (respaldo).
- **18k16g/18k17g (2026-11-17):** SoC 37-38 °C con 0330/0331 (antes quemaba); widgets ~60 %, kernel_task ~70 %. Con 9175 (UI a núcleos rápidos) hubo SIGSEGV en libobjc/malloc de SpringBoard, runningboardd, dasd, geod, searchpartyd (dos en casi la misma dirección: liberaciones de más); con `sweetfast=0` (18k17g) solo queda 1 SIGSEGV, de backboardd (pc basura desde QuartzCore +0x2203c8 por dispatch, al abrir el Centro de control). Fondo de `herosb` visible (Clownfish). **Mali no se usa en iOS 18:** `CA::WindowServer::AccelServer::renderer()` (0x18476d7c4) solo crea Metal (`new_metal_context`, 0x18489631c); sin dispositivo Metal devuelve NULL. El renderer GLES sigue (`GLESContext::GLESContext(void*)` 0x1848f968c; tabla de backends 0x1ef98d348 = gles_new_context 0x184928e38 (info tipo 3 = EAGLContext), metal_new_context, sw_new_context), pero el servidor nunca lo pide; `CA_ENABLE_OGL` se lee con getenv y se descarta. Plan: gancho en libhakiosgl que, sin Metal, arme GLESContext + Renderer en AccelServer (+0x400 contexto, +0x408 Renderer de 0x68 bytes) como hace el camino de Metal. Símbolos locales en `/root/cacheorig/dyld_shared_cache_arm64e.symbols` (WSL, `/root/syms-QuartzCore.txt`).
- **18k17h (2026-11-17): primer arranque con el Mali en iOS 18.** `ca_server_hook.c` (`509dbd4`, de Bergamota) instaló los dos ganchos y armó el renderer GLES; interfaz con blur, backboardd 120-220 % (antes 250-400), cuadros de ~27 ms, SoC hasta 50 °C. Fallas: velo rojo en la pantalla de bloqueo y formas del Centro de control a medio rellenar (las funciones de CA de iOS 18 cambiaron de número). `ffa76f2`: `ca_hooks.c` con la vtable de GLESContext de 22H352 (0x1ef986be0, slots 0x3d8/0x3e8 = GLContext::function_supported/function_uniform) y los números de 22H352 en `eagl.c` (c4p 22, ds8 29, vrd 39, vrb 40, sb3 42, vcm 48; tabla de nombres 0x1e7311c60). Pendiente: wifid 150-190 % y findmylocated ~100 % todo el tiempo (iOS 16 en reposo: 45-200 % de 800 % en total; iOS 18: 1100-1400 %). BOOT 18k18g = 18k17g sin herocap y con `sweetsample=wifid,findmylocated`.
- **18k19/18k20 (2026-11-17): colores de iOS 18 bien.** El censo (`glcensus=1`) mostró `vcm` (48) dibujada 1466 veces como imagen (el velo rojo) y ningún número entregado: los ganchos estaban en la vtable de GLContext (0x1ef986be0), que el constructor de GLESContext reemplaza por la suya (`__ZTVN2CA3OGL11GLESContextE` 0x1ef984ea8, mismos slots 0x3d8/0x3e8). `0dd0e5a` le pasa el contexto de CA a eagl.c al crearlo; `0ac1f0d` engancha la vtable correcta y usa los nombres de funciones de 22H352. 18k20: pantalla de bloqueo y Centro de control bien (usuario: "todo eso de 10"). backboardd ~23 % de CPU; cuadros de 18-45 ms (2-18 ms esperando a la GPU, el resto CPU); SoC hasta 54 °C. Consumo restante: widgets ~200 % entre todos (NewsToday2 no lo agarra el tope), searchpartyd ~70 %, launchd ~49 %, mobileassetd ~33 %. `3e1cbc4`/`6fba12f`: fuera también cryptexd, passd, findmylocated, nehelper, searchpartyd, mobileassetd, osanalyticshelper, PerfPowerServices. Íconos de Ajustes siguen sin cargar (sin crash ni error de iconservicesagent en el log; ya faltaban antes del Mali).
- **18k21/18k22 (2026-11-17/18):** 9192 (`d58b00f`, rama `herolte-ios18`) con la pantalla apagada saca los núcleos 4-7 del conjunto recomendado (`sched_perfcontrol_update_recommended_cores(0x0f)`): log "screen off: only the A53s run", SoC 43 -> 38 °C; el usuario: "no calienta tanto". 9191 mete libheroapp (CoreImage por software) en iconservicesagent: entró, pero los íconos de Ajustes siguen vacíos. El censo apunta a `c4p` (22): recibe su matriz (5x4, color a máscara) pero eagl.c no lo dibuja porque no hay textura en la unidad 0 (~700 veces). Pantalla: al apagar, el fundido lo escribe la CPU y el kernel pasa la ventana de VGR0 a G1 y vuelve al encender: la animación de apagado se ve rota y el fondo de bloqueo cortado; BOOT 18k23g prueba `herovgr=0`. fps del panel en movimiento: ~15 de media (iOS 16 en 0345: 10,6), 30 de máximo en ambos. La galería de fondos (PosterBoard) sigue vacía (necesita Metal, como en iOS 16).
- **18k23-18k25 (2026-11-18):** fondo negro por corrupción del HFS+ raíz (sin journal: cada reinicio forzado a TWRP dejaba el mapa de bloques atrás; "BlockMarkFreeInternal() trying to free unallocated blocks", drop sin wallpaper.png, error 5). `2aafd7a`: la raíz se formatea con `mkfs.hfsplus -s -J`, el atributo se apaga para los pasos de Renegade y `tools/ios18/hfs-journal.py on` lo enciende al terminar; en el teléfono "hfs: Initializing the journal", raíz "journaled". El primer arranque de cada raíz nueva reconstruye la base de LaunchServices (lsd ~86-100 % durante minutos). La galería de fondos quedó blanca desde 18k21: libheroapp en PosterBoard y en las extensiones de pósters; `d30481f` le pone `heroapp.off` (el kernel no borra archivos del drop). 18k25: texto como bloques sólidos después de 3 min: la tabla de 256 IOSurfaces de eagl.c se llenó ("more textures with IOSurfaces than there is room for"); `68b1156`: 4096 con índice por nombre. Estado estable (18k25): 13 fps de media en movimiento, cuadro de backboardd 25 ms con 3,4 ms de GPU (Mali 6 % ocupada): límite de CPU; SpringBoard 91 %, backboardd 70 %, chronod 52 %.
- **18k26-18k29 (2026-11-18/19):** galería de fondos de nuevo con miniaturas (18k29, con mobileassetd de vuelta: `37507f5`). 9193 (`c6786c6`): informe por minuto de v80emu: como mucho ~33 000 trampas/s durante dos minutos (casi todas audiomxd en libBNNS/MIL), el resto <4 000/s: la emulación no es el cuello de botella (~4 % de un núcleo). Sin 9175 (`3aec31f`) y con `sweetfast` por defecto (UI a los Mongoose): sin la ola de SIGSEGV; cuadro de backboardd 22 ms (GPU 4,5 ms). Con `herovgr=0` kernel_task subió de ~20 a ~52 % (el escalado por GPU de cada cuadro); 9194 (`d972dd2`) pone la pantalla en negro de una al apagar (el fundido mezclaba el búfer viejo de G1) para volver a VGR0, y el tope de widgets también toma "Today" (NewsToday2). Bucles de crash que quedan: KaleidoscopePoster (SIGSEGV x12), MauiAUSP/SiriAUSP (abort x23).
- **18k30/18k31 (2026-11-19):** el usuario: "mejoró bastante" con VGR0 de vuelta (9194) y la UI en los Mongoose, pero quema "sobre todo cuando lo quiero apagar": en el S7 `PEHaltRestart(kPEHaltCPU)` volvía sin hacer nada y `halt_all_cpus()` giraba en `while (1)` con la pantalla negra. 9195 (`d66a6b2`): apagado real bajando PS_HOLD (PMU +0x330c bit 8, como exynos-reboot.c de Samsung), reinicio con SWRESET, log antes, PMU mapeada en el arranque, y WFI en vez del bucle. Pendiente medido en 18k30: backboardd mandó 10 481 trabajos a la GPU en 5 s (~2000/s) y las llamadas de envío costaron 2,8 s de CPU en esos 5 s (~265 us cada una, HeroGPU): lo siguiente para la fluidez y el calor. Espacio: borrados artefactos viejos de `dl`, logs de CI, `/root/cachemod` y `/root/wslk` (+15 GB en C:).
- **18k32-18k37 (2026-11-19/20): calor real.** El usuario se quemó un dedo: la lectura de la TMU estaba mal decodificada (TRIMINFO de 9 bits: código a 25 °C en 8:0, a 85 °C desde el bit 9; CURRENT_TEMP en +0x40, 8:0), el SoC estaba a ~117 °C real. 9197 (`e437bc3`, rama `herolte-ios18`, CI 44634907571): lectura de 9 bits y escalones: 70 °C -> 1976 MHz, 80 °C -> 728 MHz, 90 °C -> sólo A53, 105 °C x3 lecturas -> apagado; se sale de cada uno 8 °C abajo. BOOT 18k37 verificado (pico 78 °C, bajó a 1976 MHz a los 70). Fuera networkserviceproxy (~180 %) y los demonios de actualización (`f6e5f90`). Fondos: las Collections pasadas a PNG como en iOS 16 (heic2png); el fondo por defecto de iOS 18 (MercuryPoster) es sólo Metal y queda negro.
- **Metal M1/M1b (2026-11-20, `docs/herolte-metal.md`):** frontend AIR de Scion + arreglos de ios-b1lte + `gpu/mesa/air-herolte.py` (`7c49803`, `ad32a4a`). boot-18k39: libhakiosair abrió "Mali-T880 (Panfrost)" y compiló `post` para Midgard. boot-18k40: **`fluidity::sdf` compiló y dibujó en el T880** (exit 0), el primer pipeline de MercuryPoster en la GPU; `post`/`fluidity`/`tori` cayeron en `air_metal_test` (formas fijas: texture3d, buffer de 256 bytes, 3 atributos), no en el compilador; `shippou::one::compute` (~73K instrucciones NIR) tuvo al compilador a 199 % varios minutos sin terminar. M2: `gpu/mesa/hero-metal-test.c` (`cd962ea`) arma cada pipeline con lo que declaran sus funciones. El disco de WSL `Ubuntu` (`E:\WSL`, banco de Metal en `/root/metal`, raíz en `/root/ios18`) no está conectado desde el 2026-11-20.
- **Metal M2 (2026-11-20, boot-18k41..45, `docs/herolte-metal.md`):** `hero_metal_test` (`cd962ea`, `9a04b3d`, `e0acc3d`) sobre el T880: todos los pipelines de render de MercuryPoster compilan (0,01-2,7 s) y dibujan (1-6 ms). Primero no cambiaba ningún píxel: el arreglo constante `quadVertices[6]` de `postVertex` iba a scratch sin su valor inicial (todos los vértices en un punto; arreglo `a3e0fa3`); después los colores salían mal porque Midgard lee la salida como 32 bits y los shaders escriben `half4` (`e0acc3d`). **18k45: `postVertex` + `postFragment` dibujan la imagen entera con colores plausibles** (degradé; RGBA32Float y RGBA8 coinciden). `fluidity` y `pro24` dibujan; `fluidity::sdf` y `tori` necesitan sus datos reales (M3). `pro24`: bicubic como lineal. `shippou::one::compute`: sin `b2i8` (bajado dentro de Midgard) pero >90 s en el asignador de registros de Midgard (~73K instrucciones NIR). El banco de Metal está en la WSL `Ubuntu-24.04` (`/root/metal`, con el corpus); sólo la raíz de iOS 18 estaba en `E:\WSL`.
- **Metal M3 (2026-11-21, BOOT 18k46 = xnu `5f3c6f2` con 9198; userland `eca3381`):** `MTLCreateSystemDefaultDevice()` devuelve "Mali-T880 (Panfrost) (Hakios)" en el S7. El kernel nombra `HeroMetal.bundle` en el `IOAcceleratorES` de HeroGPU; hero-run lo instala en `/System/Library/Extensions`; el plug-in (subclase de `_MTLDevice`: con NSObject Metal no lo llamaba, boot-18k46) da dispositivo sólo a los procesos de `/private/var/herolte/metal.allow` y carga ahí el driver de Scion (versión Panfrost de ios-b1lte). `hero_mtl_test` por Metal de verdad: librería de MercuryPoster, pipeline `post`, dos command buffers completos (3 y 1 ms), píxeles idénticos a los de `hero_metal_test`. backboardd/SpringBoard siguen en OpenGL. Siguiente: M4, MercuryPoster con su `CAMetalLayer` (drawables sobre IOSurface).
- **Metal M4 (2026-11-21, BOOT 18k46, userland `5fda253`..`33aa84d`):** drawables de Metal sobre IOSurfaces por el SurfaceBO de HeroGPU (`gpu/metal/metal-herolte.py`), 4096/4096 píxeles iguales en IOSurface y `CAMetalLayer` (boot-18k48). Con `MercuryPosterExtension` en `metal.allow`, el fondo de iOS 18 (estilo fluidity) dibuja en el T880: primero sólo el degradé rosa (18k49), después con las dos pasadas un degradé azul (18k50, foto del usuario). Arreglos: texturas sin asignar leen ceros; pérdida de ~430 BOs de 4 KB cada 5 s (`setBytes` + autorelease sin pool en el hilo del póster; widgets en blanco y tirones) arreglada en 18k53 (0 BOs nuevos, pool 505/512 reusados); la forma faltaba porque el `bool` de los uniforms del SDF (load_ubo de 8 bits) se leía mal en Midgard y G quedaba en 0 (`33aa84d`, sin probar). Pendiente: function constants (`isPhone`=0) y ~14,5 ms de envío síncrono por cuadro.

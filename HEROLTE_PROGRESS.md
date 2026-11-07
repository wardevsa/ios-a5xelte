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
# Transferencia entre sesiones y modelos

## Protocolo
**Quien sale** (fin de sesión, corte inminente, cambio de modelo): (1) deja un checkpoint de la tarea en curso; (2) actualiza `STATE.md` y su marca `state-commit` si cambió el panorama; (3) añade **abajo** un relevo nuevo `H-NNNN` (los anteriores no se editan); (4) `render` + `check` + commit local.
**Quien entra:** sigue "Si acabas de incorporarte" de `README.md`, lee el relevo vigente y **verifica** cada afirmación importante contra el repositorio antes de repetirla (`status`, `evidence`, `regress`). Si el estado real contradice el relevo, gana el estado real y se anota la discrepancia en un checkpoint.
Un relevo contiene siempre: repositorio y rama exactos, estado Git, documentos creados o modificados, qué se verificó y cómo, permisos vigentes, riesgos, decisiones pendientes, hilos abiertos con su siguiente paso y la misión recomendada. **No incluye secretos ni datos privados.**
Los informes para el jefe técnico (ChatGPT) usan el mismo formato: se le entregan a través del Director.

---

## Relevo vigente: H-0097 — lote D-0067: min31 (herogpu_mhz=650) ESCRITA (2 de 3); teléfono en TWRP, sin reiniciar (2026-11-15)
- **Tarea en curso: T-0012.** min30 (E-0230) funcionó: 2600 MHz / 1075 mV, SoC 38-41 C. BOOT = `xnu-boot-v2-s7-min31-20261115.img` (sha256 `9a155ba6…2a4`, E-0228/E-0231). Queda 1 escritura de D-0067: min29 (`71c3344f…82fa7`) solo para volver atrás.
- **Director:** `adb reboot`, 5 min de uso, fluidez/calor, TWRP. **Ingeniero:** log: 'HEROLTE GPU: clock … 650 MHz', vdd_g3d, JOB_READ_FAULT, avg_copy_us, fps, temperatura.
- Si min31 falla: min29 (D-0067). Si va bien: quedarse con min31 y pasar al userland.
- Fallos de userland vistos: Ajustes > About crashea, Messages crashea, Phone en blanco, assetsd, driverkitd.

## Relevo anterior: H-0096 — lote D-0067: min30 (herocpu_mhz=2600) ESCRITA (1 de 3); teléfono en TWRP, sin reiniciar (2026-11-15)
- **Tarea en curso: T-0012.** BOOT = `xnu-boot-v2-s7-min30-20261115.img` (sha256 `add62cf6…cfdbe`, E-0227/E-0229). Quedan 2 escrituras de D-0067: min31 (`9a155ba6…a02a4`, +herogpu_mhz=650) y min29 (`71c3344f…82fa7`, vuelta atrás).
- **Director:** `adb reboot`, 5 min de uso, calor/fluidez, TWRP. **Ingeniero:** log: 'Mongoose at 2600 MHz', vdd_mngs, SoC C, fps; si va bien -> min31; si no -> min29.
- Restaurar BOOT: min29 (cubierta por D-0067) / original E-0009 (firma).

## Relevo anterior: H-0095 — min29 medida (1976 MHz, SoC 34-43 C, 12 fps medios); min30 (herocpu_mhz=2600) preparada, NO escrita (2026-11-15)
- **Tarea en curso: T-0012.** E-0226: Mongoose 1976 MHz a 912,5 mV sin fallos; temperatura baja; el Director ve mejora clara. E-0227: min30, sha256 `add62cf6…9cfdbe`.
- **Siguiente:** firma del Director para min30 (opcional: la fluidez ya es aceptable) y, aparte, el plan de userland (fondo, assetsd, MobileSMS, hero-run por DROP), todavía sin hacer.
- BOOT actual: min29 (funciona). Restaurar: min28/min27/original E-0009.

## Relevo anterior: H-0094 — min29 (heropower=1 herocpu_mhz=1976) ESCRITA (D-0066); teléfono en TWRP, sin reiniciar (2026-11-15)
- **Tarea en curso: T-0012.** BOOT = `xnu-boot-v2-s7-min29-20261115.img` (sha256 `71c3344f…2fa7`, E-0224/E-0225).
- **Director:** `adb reboot`, 5 min de uso normal, apuntar fluidez y calor; volver a TWRP. **Ingeniero:** `herolte-log-pull.py`; 'HEROLTE CPU ... MHz', 'HEROLTE TMU', temperatura de la pila, fps, fallos.
- Restaurar BOOT: min28 (funciona) / min27 / original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0093 — min28 medida (GPU presenta: 88 -> 6,3 ms/cuadro; 10 fps); min29 (heropower=1 herocpu_mhz=1976) preparada, NO escrita (2026-11-15)
- **Tarea en curso: T-0012.** E-0223: lag restante por CPU a 242 MHz (Mongoose) / 1055 MHz (A53) y composición CA en CPU. E-0224: min29, sha256 `71c3344f…832fa7`.
- **Riesgo:** sube tensión/frecuencia del cluster rápido (upstream L4h, hasta 2600 MHz). heropower=1 añade el gobernador de calor y la temperatura en el log. Volver a min28 (funciona).
- **Siguiente:** firma del Director; `adb reboot`, 5 min de uso; log: 'HEROLTE CPU: ... MHz', temperatura/TMU, fps, fallos.
- Pendiente: fondo negro (herosb/hero-run), assetsd, MobileSMS, memoria baja.
- Restaurar BOOT: min28 (funciona) / min27 / original E-0009.

## Relevo anterior: H-0092 — min28 (min27 + sweetfb_gpu=1) ESCRITA (D-0065); teléfono en TWRP, sin reiniciar (2026-11-15)
- **Tarea en curso: T-0012.** BOOT = `xnu-boot-v2-s7-min28-20261115.img` (sha256 `9811a265…e56`, E-0221/E-0222).
- **Director:** `adb reboot`, 5 min de uso normal, apuntar si hay menos lag o si se congela; volver a TWRP sin Vol-+Power. **Ingeniero:** `herolte-log-pull.py`; avg_copy_us/fps; errores de GPU (JOB_READ_FAULT, gpuPresent); vuelta a min27 si falla.
- Restaurar BOOT: min27 (funciona) / min26 / original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0091 — iOS en pantalla con táctil (min27); log medido; min28 (sweetfb_gpu=1) preparada, NO escrita (2026-11-15)
- **Tarea en curso: T-0012.** E-0220: lag = copia/reescalado por CPU 88 ms/cuadro; memoria libre cae a 72 MB; SpringBoard inició el apagado a los ~7 min (¿Vol-+Power del Director?); crashes: assetsd x13, MobileSMS, fileprovider(s). Sin temperatura (heropower=0). E-0221: min28 = min27 + `sweetfb_gpu=1`, sha256 `9811a265…09be56`.
- **Siguiente:** firma del Director; `adb reboot`, 5 min con uso normal; log: avg_copy_us, fps, errores de GPU (JOB_READ_FAULT, fallos de gpuPresent). Si la GPU falla, volver a min27.
- Pendiente aparte: fondo negro (herosb/hero-run por DROP), assetsd/autorun, memoria baja, temperatura (heropower=1 es riesgo), Messages crashea.
- Restaurar BOOT: min27 (a59c26fa…, funciona) / min26 / original E-0009.

## Relevo anterior: H-0090 — min27 (scale=1 lw=750 lh=1334) ESCRITA (D-0064); teléfono en TWRP, sin reiniciar (2026-11-15)
- **Tarea en curso: T-0012.** BOOT = `xnu-boot-v2-s7-min27-20261115.img` (sha256 `a59c26fa…f4640`, E-0218/E-0219).
- **Director:** `adb reboot`, 5 min sin pulsar, apuntar qué ve; volver a TWRP (si falla el force reboot: Power+Vol- ~10 s para apagar, soltar y entrar a recovery). **Ingeniero:** `herolte-log-pull.py`; 'presented as'; FBSRC/FBPROBE con contenido; ¿arranca (riesgo 0xa0000000)?
- Restaurar BOOT: min26/min25/original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0089 — min26 medida (sin registro de puerto; tamaño pedido 750x1334 != 1440x2560); min27 (scale=1 lw=750 lh=1334) preparada, NO escrita (2026-11-15)
- **Tarea en curso: T-0012.** E-0217. Hipótesis: desajuste lógico/ADT (el comentario del driver: "a mismatch left every swap layer empty"). min27 = línea de min26 + `sweetfb_scale=1 sweetfb_lw=750 sweetfb_lh=1334`, mismo kernel 0355. E-0218, sha256 `a59c26fa…6f4640`.
- **Riesgo:** con escala, la superficie por defecto usa memoria física en 0xa0000000 (primer banco); si choca el kernel puede fallar. Se volvería a min26/min25 por TWRP.
- **Siguiente:** firma del Director; `adb reboot`, 5 min; TWRP; log: FBSRC/FBPROBE con contenido; 'presented as'.
- Restaurar BOOT: min26/min25/original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0088 — min26 (kernel 0355, FBCALL) ESCRITA (D-0063); teléfono en TWRP, sin reiniciar (2026-11-15)
- **Tarea en curso: T-0012.** BOOT = `xnu-boot-v2-s7-min26-20261115.img` (sha256 `c08cd221…c57fca`, E-0215/E-0216).
- **Director:** `adb reboot`, 3 min sin pulsar, TWRP (si adb no sale: desenchufar/enchufar). **Ingeniero:** `herolte-log-pull.py`; `grep -a FBCALL`.
- Restaurar BOOT: min25/min24/original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0087 — kernel 0355 (CI 43711249983) y min26 preparada, NO escrita; BOOT sigue con min25 (2026-11-15)
- **Tarea en curso: T-0012.** E-0214 kernel, E-0215 imagen `xnu-boot-v2-s7-min26-20261115.img` sha256 `c08cd221…c57fca`: línea de min25 + kernel 0355 (FBCALL).
- **Siguiente:** firma del Director; `adb reboot`, 3 min, TWRP (si adb no sale: desenchufar/enchufar); `herolte-log-pull.py`; `grep -a FBCALL`: ¿qué llamada es el registro de vsync? ¿registerNotificationPort?
- Restaurar BOOT: min25/min24/original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0086 — CI de 0355 falló (cast de puntero); corregido en local (3decc3e), a la espera de nueva firma de CI (2026-11-15)
- **Tarea en curso: T-0012 / T-0049.** Run 43710141555: error `SweetFramebuffer.cpp:1185: cast from pointer to smaller type 'unsigned int'` (mach_port_t es puntero aquí). Corregido: se imprime como `(unsigned long long)(uintptr_t)port`. El parche nunca produjo kernel, así que se corrigió en su sitio. D-0061 nombra el commit 34fd5f9: un commit nuevo (3decc3e) necesita firma nueva.
- BOOT actual: min25. Siguiente: firma de CI de 3decc3e; min26; firma de BOOT; leer FBCALL.

## Relevo anterior: H-0085 — análisis: UI arrancada pero sin vsync registrado; parche 0355 (log de llamadas IOMFB) escrito, sin CI (2026-11-15)
- **Tarea en curso: T-0012.** E-0213 / `docs/S7GE_BACKBOARDD_WAIT.md`: SpringBoard en GSEventRunModal, backboardd en run loop, superficies a cero, selector 72 nunca llamado (iOS 16.7.16 usa 68/74/79/84/50/52/55). `tools/herolte-smp-images.py` mapea PC -> librería (caché de dyld extraída con 7z de `systemos.dmg`; sin símbolos de función porque los linkedit están comprimidos con APFS).
- **Siguiente:** firma del Director para push + CI de 0355 (commit 34fd5f9); min26 = línea de min25 + kernel 0355; firma de BOOT; arrancar 3 min; leer `FBCALL` (argumentos de las 120 primeras llamadas, asincronía, registerNotificationPort).
- Pendiente aparte: DROP v2 (hero-run/autorun/herosb), assetsd aborta, táctil sin probar.
- BOOT actual: min25. Restaurar: min24/min23/original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0084 — min25 medida: sweetfb_native=1 no basta; backboardd sigue en espera; BOOT sigue con min25 (2026-11-15)
- **Tarea en curso: T-0012.** E-0212: 'presented as 1440x2560' correcto, superficies de pantalla 1440x2560 a cero, hilos en espera. Quedan como sospechosos: assetsd aborta ('Too many corpses', sig 6), com.apple.datamigrator (3 ejecuciones), faltan hero-run/autorun/herosb/disabled.list (DROP), y el estado de migración/setup del root.
- **Siguiente:** (1) symbolizar los PC del muestreo SMP (dyld cache de la raíz; `7z` lee el HFS sin montar pero los tamaños salen 0, hay que ver si extrae) para ver qué espera backboardd; (2) mirar el crash de assetsd (bt en el log, direcciones sin símbolos); (3) instalar el userland de upstream por DROP (herodrop=1) tras una firma.
- Táctil: el driver arranca ('sensing, INT=0; polling 5 ms'); falta una prueba con toques (la pantalla no responde mientras no haya UI).
- Restaurar BOOT: min24/min23/original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0083 — min25 (min24 + sweetfb_native=1) ESCRITA (D-0060); teléfono en TWRP, sin reiniciar (2026-11-15)
- **Tarea en curso: T-0012.** BOOT = `xnu-boot-v2-s7-min25-20261115.img` (sha256 `a55af158…c9e4`, E-0210/E-0211).
- **Director:** `adb reboot`, 5 min sin pulsar, apuntar si ve logo de Apple o texto de iOS; volver a TWRP (si adb no aparece: desenchufar y enchufar). **Ingeniero:** `herolte-log-pull.py`; FBSRC/FBPROBE con contenido; 'presented as'.
- Restaurar BOOT: min24/min23/original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0082 — min25 (min24 + sweetfb_native=1) preparada, NO escrita; BOOT sigue con min24 (2026-11-15)
- **Tarea en curso: T-0012.** Hipótesis nueva (upstream, L4h): sin `sweetfb_native=1` el lienzo presentado (1125x2436) contradice el panel (1440x2560) y backboardd solo hace swaps negros; con él upstream vio Apple + "Hola". E-0210: imagen `xnu-boot-v2-s7-min25-20261115.img` sha256 `a55af158…6dc9e4`.
- **Siguiente:** firma del Director; `adb reboot`, 4-5 min (sin pulsar), TWRP; `herolte-log-pull.py`; FBSRC/FBPROBE: ¿contenido no nulo?; ¿cambia 'presented as'?
- Restaurar BOOT: min24/min23/original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0081 — backboardd está BLOQUEADO esperando algo (no lento): 12 min, 25 presents, superficies a cero (2026-11-15)
- **Tarea en curso: T-0012.** E-0209: FBSRC todo ceros en 25 presents/12 min; muestras SMP: hilos en espera. Hipótesis A reforzada (no B). BOOT sigue con min24.
- **Siguiente:** (1) symbolizar los PC de las muestras SMP con la dyld cache de la raíz iOS (`/media/.../ios-root-herolte-20261115.img` montable en solo lectura con sudo del Director, o del IPSW os.dmg) para ver QUÉ espera backboardd; (2) mirar upstream: backboardd espera `DMPerformMigration` / `FBSystemShellInitialize`; en esta raíz podrían faltar flags (SetupDone, migración) o servicios; (3) instalar el userland de upstream por DROP (autorun/hero-run/herosb/disabled.list).
- Restaurar BOOT: min23/min22/original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0080 — min24 medida: superficies origen todo ceros (no es la caché); BOOT sigue con min24 (2026-11-15)
- **Tarea en curso: T-0012.** E-0208: FBSRC pass 0 = pass 1 = 0 (incluido alfa) en los 12 primeros presents (190 s). Hipótesis B (caché) descartada para ese tramo; el renderer no ha escrito las superficies 3/5. Falta saber si más tarde (min23: ~10 fps hacia el minuto 5-7) hay contenido: las sondas FBSRC solo cubren presents 1-12 y cada 25.
- **Siguiente (sin escribir BOOT):** el Director reinicia con la misma min24 y la deja 12 min; yo leo FBSRC de presents 25, 50, 75... (si el ritmo sube). Después, según resultado: renderer negro => userland upstream (hero-run/autorun/herosb/disabled.list via DROP) y sampler de qué espera backboardd.
- Restaurar BOOT: min23/min22/original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0079 — min24 (kernel 0354, sonda FBSRC) ESCRITA (D-0059); teléfono en TWRP, sin reiniciar (2026-11-15)
- **Tarea en curso: T-0012.** BOOT = `xnu-boot-v2-s7-min24-20261115.img` (sha256 `968ddd3a…fd64f64`, E-0206/E-0207).
- **Director:** `adb reboot`, 3-4 min sin pulsar nada, TWRP. **Ingeniero:** `herolte-log-pull.py`; `grep -a FBSRC`: pass1 > pass0 = caché; ambos 0 = renderer negro.
- Restaurar BOOT: min23/min22/original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0078 — kernel 0354 (CI 43705328859) y min24 preparada, NO escrita; BOOT sigue con min23 (2026-11-15)
- **Tarea en curso: T-0012.** E-0205 kernel, E-0206 imagen `xnu-boot-v2-s7-min24-20261115.img` sha256 `968ddd3a…d64f64`: min23 con kernel 0354 (FBSRC pass 0/1 de la superficie origen).
- **Siguiente:** firma del Director; `adb reboot`, 3-4 min, TWRP; `herolte-log-pull.py`; `grep -a FBSRC`: si pass1 > pass0 es caché; si ambos 0 el renderer dibuja negro (A).
- Restaurar BOOT: min23/min22/original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0077 — min23 medida: cuadros a ~10 fps pero negros; parche 0354 (sonda de la superficie origen) escrito, sin CI (2026-11-15)
- **Tarea en curso: T-0012.** E-0204: keep_on funciona (la pantalla no se apaga), el cuadrado negro del Director = el lienzo presentado; 40/40 miniaturas negras; backboardd/SpringBoard ociosos. Hipótesis A: la superficie compuesta es realmente negra (CA sin contenido/ sin GPU; upstream usa hero-run/herosb/drop con disabled.list). Hipótesis B: coherencia de caché (superficies WC). 0354 las separa (FBSRC pass 0/1).
- **Siguiente:** firma del Director para push + CI de 0354 (commit 54c3d98); construir min24 (misma línea que min23, kernel nuevo); firma de BOOT; arrancar 3-4 min.
- Pendiente aparte: userland de upstream no instalado (`/private/var/herolte/autorun` ausente: SPAWN FAILED; herodrop=0). DROP v2 sirve para instalar hero-run/herosb/disabled.list; evaluarlo después de 0354.
- Memoria libre cae de 268 a 98 MB en 7 min (vigilar).
- Restaurar BOOT: min23/min22/original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0076 — min23 (a5fb_keep_on=1 a5fb_noconsole=1) ESCRITA (D-0057); teléfono en TWRP, sin reiniciar (2026-11-15)
- **Tarea en curso: T-0012.** BOOT = `xnu-boot-v2-s7-min23-20261115.img` (sha256 `595a146f…1898f2`, E-0202/E-0203).
- **Director:** `adb reboot`, 8 min sin pulsar Power, mirar a los 3-4 min qué se ve (una frase), volver a TWRP. **Ingeniero:** `herolte-log-pull.py`; FBPROBE de present 25, 50, 75…; ¿`display-off request ignored`?; ¿contenido no negro?
- Restaurar BOOT: min22/min21/original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0075 — min22 medida: el panel recibe negro; min23 (a5fb_keep_on=1 a5fb_noconsole=1) preparada, NO escrita (2026-11-15)
- **Tarea en curso: T-0012.** E-0201: 9/9 miniaturas negras, off=0: el contenido presentado es negro (no el fundido). Hipótesis (upstream, L4h): primer cuadro del renderer de CPU tarda minutos y backboardd pide display off tras el primer swap; `a5fb_keep_on=1` lo ignora. Además `a5fb_noconsole` (nombre bajo A5XELTE) en vez de `sweetfb_noconsole`.
- **Imagen:** `xnu-boot-v2-s7-min23-20261115.img` sha256 `595a146f…1898f2` (E-0202): min22 + `a5fb_noconsole=1 a5fb_keep_on=1`. Mismo kernel 0353.
- **Siguiente:** firma del Director; `adb reboot`, 6-8 min (el primer cuadro puede tardar), TWRP; `herolte-log-pull.py`; leer FBPROBE de present 25, 50, 75… ¿aparece contenido?
- Restaurar BOOT: min22/min21/…/original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0074 — min22 (kernel 0353, miniatura FBPROBE) ESCRITA (D-0056); teléfono en TWRP, sin reiniciar (2026-11-15)
- **Tarea en curso: T-0012.** BOOT = `xnu-boot-v2-s7-min22-20261115.img` (sha256 `8bd3295b…dd4cea6`, E-0199/E-0200).
- **Director:** `adb reboot`, 3-5 min, volver a TWRP. **Ingeniero:** `herolte-log-pull.py`; `grep -a "FBPROBE\|^FBP "` y leer las miniaturas (¿negro, bloqueo, fondo?; ¿off=1?).
- Restaurar BOOT: min21/min20/min19/original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0073 — kernel 0353 (CI 43702827328) y min22 preparada, NO escrita; BOOT sigue con min21 (2026-11-15)
- **Tarea en curso: T-0012.** E-0197: min21 sin anillo, pantalla negra/apagada, teclas sin efecto. Display off = desvanecimiento por software (0079); on = repinta el último cuadro. Falta saber si los cuadros son negros: 0353 vuelca miniatura 32x64 (FBPROBE/FBP) al log.
- **Imagen:** `xnu-boot-v2-s7-min22-20261115.img` sha256 `8bd3295b…91dd4cea6` (E-0199). Solo cambia el kernel respecto a min21.
- **Siguiente:** firma del Director (decisión nueva: D-0054 nombra solo min21); `adb reboot`, 3-5 min, TWRP; `herolte-log-pull.py`; `grep FBPROBE/FBP` y leer las miniaturas.
- Restaurar BOOT: min21/min20/min19/original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0072 — min21 (min20 + heroring=0 sweetfb_noconsole=1, kernel 0352) ESCRITA (D-0054); teléfono en TWRP, sin reiniciar (2026-11-15)
- **Tarea en curso: T-0012.** BOOT = `xnu-boot-v2-s7-min21-20261115.img` (sha256 `141a6d87…336a1e`, E-0195/E-0196).
- **Director:** `adb reboot`, 5-10 min mirando la pantalla (¿consola, fondo, iconos, negro?), volver a TWRP. **Ingeniero:** `herolte-log-pull.py`; contar swaps y ver si SpringBoard/backboardd siguen vivos.
- Restaurar BOOT: min20/min19/original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0071 — kernel 0352 (CI 43699443107) y min21 preparada, NO escrita; BOOT sigue con min20 (2026-11-15)
- **Tarea en curso: T-0012.** E-0193: UI de iOS viva, GPU arranca y nadie la usa; la pantalla muestra el anillo 0351. T-0046 hecha: kernel 0352 (E-0194). Imagen `xnu-boot-v2-s7-min21-20261115.img` sha256 `141a6d87…336a1e` (E-0195) = min20 + `heroring=0 sweetfb_noconsole=1`.
- **Siguiente:** firma del Director para escribir min21 (decisión nueva: D-0052 nombra solo min20). Después `adb reboot`, 5-10 min, TWRP, `tools/herolte-log-pull.py`.
- Investigación abierta (solo PC): por qué nadie abre HeroGPU/IOAccelerator; xstat 9 de widgets/UARP; assetsd xstat 6; `autorun` ausente.

## Relevo anterior: H-0070 — min20 (min19 con herogpu=1) ESCRITA (D-0052, 1 de la tanda nueva); teléfono en TWRP, sin reiniciar (2026-11-15)
- **Tarea en curso: T-0012.** E-0190: iOS llega a SpringBoard con herogpu=0. BOOT = `xnu-boot-v2-s7-min20-20261115.img` (sha256 `039b30dc…c82fb6`, E-0191/E-0192). Primera vez con la GPU Mali en esta unidad.
- **Director:** `adb reboot`, dejar 5-10 min, volver a TWRP y avisar. **Ingeniero:** `python3 -I tools/herolte-log-pull.py adb OUT.txt`; mirar herolte_gpu (arranque, errores MMU/job), swaps de backboardd, si SpringBoard sale, y contar swaps/min. El log no va a git.
- **RESULTADO (E-0193):** GPU arranca bien (Mali-T880 r2p0) pero nadie la usa (sin jobs); SpringBoard vivo ~270 s; en pantalla sigue la consola. Siguiente: (1) por qué backboardd/SpringBoard no abren HeroGPU/IOAccelerator (¿falta entitlement/IOKit match, Metal sin renderer?); (2) por qué el panel no muestra la UI (la consola temprana 0348/0351 sigue pintando el framebuffer; swaps al DECON con superficie vacía?); (3) xstat 9 de widgets/UARP y assetsd 6. Cualquier cambio de kernel = parche + CI (publish, rojo) + imagen + firma.
- Restaurar BOOT: min19/min18/original E-0009 (cada escritura exige firma).

## Relevo anterior: H-0069 — min19 (min18 con herolog=1) ESCRITA (D-0051, 20/20 de BOOT); teléfono en TWRP, sin reiniciar (2026-11-15)
- **Tarea en curso: T-0012.** E-0187: launchd vivo y en bucle exec/EXIT; falta saber qué procesos y con qué código. BOOT = `xnu-boot-v2-s7-min19-20261115.img` (sha256 `4ab37c87…1e63`); EFS intacto (E-0189). **Contador de BOOT agotado (20/20):** otra escritura de BOOT exige decisión nueva.
- **RESULTADO (E-0190):** log leído. iOS arranca: `Early boot complete`, configd, backboardd y SpringBoard lanzados; backboardd presenta cuadros en AppleCLCD. El "bucle" era arranque normal. Pendiente: ver por qué la pantalla muestra la consola y no la UI (¿flip del framebuffer de DECON?), salidas no cero (HorizonSetup ausente, driverkitd 9, IOMFB_FDR_Loader), relanzados de bluetoothd/fairplayd.H2 (7), y dejar correr más de 70 s.
- Restaurar BOOT: min18 (E-0185/E-0186) o el original E-0009, cubierto por D-0051.

## Relevo anterior: H-0068 — min18 (min17 + args de launchd del upstream) ESCRITA (D-0050, 19/20 de BOOT); teléfono en TWRP, sin reiniciar (2026-11-15)
- **Tarea en curso: T-0012.** E-0184: con la raíz iOS y ufsrw=1 rootrw=1 la raíz se monta, XNU lanza `/sbin/launchd` y lo mata `CS_KILLED` (panic + A5 XNU PANIC). BOOT = `xnu-boot-v2-s7-min18-20261115.img` (sha256 `cd8be9c5…d85e`); EFS intacto (E-0186). Queda UNA escritura de BOOT en la tanda D-0043/45/46/47/49/50 (20): la siguiente tanda necesitará una decisión nueva con su contador.
- **Qué mirar (Director, tras `adb reboot`):** si desaparece el pánico de launchd; mensajes de `launchd`, `xpcproxy`, `dyld`, `libignition`, `Early boot complete`, SpringBoard...; o un panic nuevo (copiar literal). El anillo (tercio izquierdo) se mueve mucho: varias fotos.
- Siguiente probable según resultado: si sigue CS_KILLED, mirar `kern_exec.c:7611` (condición del kill: firma del binario, ubc_cs_blob, `cs_enforcement`/`PE_i_can_has_debugger`), la caché de dyld de 16 KiB frente a páginas de 4 KiB (parche 0107 del A5XELTE) y el AMFI (0106) en este kernel.
- Restaurar BOOT: min17 / min16 / original E-0009, cubierto por D-0050.

## Relevo anterior: H-0067 — min17 (ufsrw=1 rootrw=1) ESCRITA (D-0049); teléfono en TWRP, sin reiniciar (2026-11-15)
- **Tarea en curso: T-0012.** E-0181: con la raíz iOS en USERDATA y ufsrw=0, XNU reconoce el HFS+ pero falla al inicializar el diario (`jnl: do_jnl_io: strategy err`, `journal_create: failed`). BOOT = `xnu-boot-v2-s7-min17-20261115.img` (sha256 `8c984503…19bd2`; min16 con `ufsrw=1 rootrw=1`); EFS intacto (E-0183). Escrituras de la tanda: 18/20.
- **Qué mirar (Director, tras `adb reboot`):** que desaparezca `cannot mount root` y las líneas `jnl:`/`hfs: late jnl init`; después `calling VFS_ROOT`, mensajes de `launchd`/`xpc`, o un `A5 XNU PANIC`. Copiar literal; la línea de la marca blanca y 8-10 anteriores.
- **Riesgo:** el kernel ahora puede escribir en USERDATA (solo ahí). Si algo corrompe la raíz: restaurar la imagen E-0179 con `tools/herolte-write-userdata.py` (nueva autorización, ~80 min) o las copias E-0124/E-0125.
- Restaurar BOOT: min16 (ufsrw=0) o el original E-0009, cubierto por D-0049.

## Relevo anterior: H-0066 — USERDATA ESCRITA con la raíz iOS (D-0048): Android borrado del inicio de USERDATA; falta el primer arranque con raíz (2026-11-15)
- **Tarea en curso: T-0012** (test de arranque; D-0047 vigente, 17/20 escrituras de BOOT). T-0044 hecha: E-0180 (hash de los primeros 20 GiB de USERDATA leído en el teléfono = 8c448c05…587a). Vuelta atrás: E-0124/E-0125 + BOOT original E-0009.
- **Siguiente (Director):** `adb reboot` con el BOOT `min16` (línea de min2: `ufsrw=0`, sin Wi-Fi/energía/GPU). Esperado: desaparece `cannot mount root`, `hfs_mount` sin error, `calling VFS_ROOT`, y entonces `launchd`/panic. Copiar literal lo que se vea en el anillo (tercio izquierdo) y las últimas líneas.
- Si no monta: leer el `errno` (mi anillo muestra solo la cadena de formato; habría que enganchar el valor); si monta y falla `launchd`, anotar el mensaje.
- Teléfono ahora: TWRP, USERDATA desmontada. Restaurar BOOT original cubierto por D-0047.

## Relevo anterior: H-0065 — plan de la raíz iOS (vía B, local) listo; mañana F1 con sudo del Director (2026-11-15)
- **Tarea en curso: T-0012** (test de N2: resultado A alcanzado, E-0177; D-0047 vigente, 17/20 escrituras de la tanda) y **siguiente: T-0045** (preparar la imagen final de la raíz iOS; necesita `sudo`, que teclea el Director). T-0044 (escribir USERDATA, ROJO) bloqueada hasta tener imagen y autorización con hash.
- **Hecho esta noche:** `docs/S7GE_IOS_ROOT_PLAN.md` (F0-F5), F0 comprobada (E-0178: IPSW y `lab-full-xnu-20261114.img` coinciden con sus hashes), `tools/herolte-write-userdata.py` + `test_write_userdata.py` (7 pruebas con adb falso; escritor por `nc` ~18 MB/s, trozos verificados contra el teléfono, se niega sin autorización), informe a la jefatura `docs/S7GE_INFORME_JEFATURA_20261115.md`.
- **Mañana (en orden):** F1 (Director con `!sudo`: copiar la imagen de laboratorio, montar rw, `tools/herolte-tune-ios-root.sh MONTAJE 20H392`, desmontar, `fsck.hfsplus -n`, hash); F2 prueba de transporte `--dry-transport`; F3 autorización roja de escribir USERDATA con el hash de F1; F4 arranque con el BOOT `min16`; F5 iterar.
- **Teléfono:** en TWRP con BOOT `min16`. Copias SYSTEM/USERDATA/RECOVERY verificadas (E-0123…E-0125): la vuelta atrás de Android.
- Restaurar BOOT original (E-0009) cubierto por D-0047.

## Relevo anterior: H-0064 — N2 ALCANZADO: XNU arranca hasta bsd_init y falla al montar la raíz (esperado); el 'reinicio' era una mala lectura (2026-11-15)
- **Tarea en curso: T-0012.** E-0177 + `docs/S7GE_N2_REACHED.md`: min16 muestra el log del kernel (APM, TOUCH, GPU probe disabled, UFS, `cannot mount root, errno = %d`, Skywalk PASSED, `bsd_autoconf: calling kinit`) y se actualiza: resultado **A** de N2. BOOT del teléfono = min16 (17/20 escrituras de la tanda; no hace falta escribir más para esto).
- **Corrección:** la pantalla 'XNU MMU ON + 3 bloques' que leí como reinicio eran marcas de start.s sobre el framebuffer con el kernel vivo y sin consola visible. Desde min2 el kernel arrancaba.
- **Siguiente (decisión del Director):** de dónde sale la raíz iOS HFS+ (~20 GiB): A repo privado propio con el workflow `ios-root`, B construirla en este PC desde un IPSW (`tools/mkiosroot.sh`, apfs-fuse, sudo, ~40 GB), C que la facilite quien la tenga. Luego: escribir USERDATA (borra Android; autorización roja propia con hash; copias en E-0124/E-0125) y línea de arranque con `ufsrw=1`.
- Restaurar BOOT original (E-0009) cubierto por D-0047.

## Relevo anterior: H-0063 — min16 (kernel 0351: anillo de mensajes de kprintf/printf) ESCRITA (D-0047, 17/20); teléfono en TWRP, sin reiniciar (2026-11-15)
- **Tarea en curso: T-0012.** E-0169: el reinicio está tras el anuncio PE_lockdown_iokit (dentro de PE_lockdown_iokit/vm_set_restrictions/kperf_init_early/bsd_init); E-0173: -v no muestra el log. BOOT = `xnu-boot-v2-s7-min16-20261114.img` (sha256 `048add02…09cf`); EFS intacto (E-0176).
- **Qué mirar (Director, tras `adb reboot`):** además de las dos columnas de fases (derecha 36, izquierda 28), el **tercio izquierdo** de la pantalla (x≈20-620) muestra un anillo de unas 73 líneas con el comienzo (36 caracteres) de cada mensaje de kprintf/printf; una **marca blanca** en el borde izquierdo señala la línea MÁS RECIENTE. Copiar: la línea de la marca y las 8-10 líneas anteriores (de arriba abajo en el orden de pantalla; el anillo da la vuelta, así que el orden temporal es hacia abajo desde la línea de la marca +1 y reinicia arriba). Cualquier línea con `panic`/`error`/`fail`/`mount`.
- Restaurar BOOT original (E-0009) cubierto por D-0047.

## Relevo anterior: H-0062 — min15v (min15 + `-v`, kernel 0350) ESCRITA (D-0046, 16/20); teléfono en TWRP, sin reiniciar (2026-11-15)
- **Tarea en curso: T-0012.** E-0169: min15 llega a PE_lockdown_iokit (64 fases); el reinicio está en PE_lockdown_iokit/vm_set_restrictions/kperf_init_early/bsd_init o más allá. BOOT = `xnu-boot-v2-s7-min15v-20261114.img` (sha256 `79fdf35c…94f5`); EFS intacto (E-0172).
- **Qué mirar (Director, tras `adb reboot`):** con `-v` XNU escribe el LOG del kernel en la pantalla en texto normal (líneas largas, muchas; pueden pasar rápido). Copiar: (1) cualquier línea con `panic`/`Panic`/`error`/`fail`; (2) las ÚLTIMAS líneas antes de que la pantalla se reinicie; (3) si hay un `A5 XNU PANIC`. Si se ve demasiado rápido, hacer vídeo corto o varias fotos; yo puedo sacar fotogramas con `tools/herolte-video-frames.sh`.
- Restaurar BOOT original (E-0009) cubierto por D-0046.

## Relevo anterior: H-0061 — min15 (kernel 0350: lista de fases en 3 columnas) ESCRITA (D-0043/D-0045, 15/20); teléfono en TWRP, sin reiniciar (2026-11-14)
- **Tarea en curso: T-0012.** E-0165: min14 listó 36 fases hasta thread_init (tope de pantalla, slot 76) y luego start.s volvió a ejecutarse (reinicio); sin pánico visible. BOOT = `xnu-boot-v2-s7-min15-20261114.img` (sha256 `7337370f…5675`); EFS intacto (E-0168).
- **Qué mirar (Director, tras `adb reboot`):** la lista de nombres ahora CONTINÚA en una segunda columna (a la izquierda de la primera, a partir de ~x=660) y una tercera (x≈20) cuando se llena la primera. El ÚLTIMO nombre de la última columna dice dónde se reinicia. Copiar los nombres de la 2.ª y 3.ª columna (de arriba abajo). Si hay `A5 XNU PANIC`, copiarlo literal.
- Fases esperadas tras thread_init: restartable_init, workq_init, turnstiles_init, mach_init_activity_id, exception_init, sfi_init (si CONFIG_SCHED_SFI), kernel_thread_create, load_context - done; luego kernel_bootstrap_thread: idle_thread_create, sched_startup, thread_daemon_init, thread_bind, mapping_adjust, …
- Restaurar BOOT original (E-0009) cubierto por D-0045.

## Relevo anterior: H-0060 — h53 llegó a la fase 'kmem' (entradas STARTUP de KMEM); min14 SIN herostop ESCRITA (D-0043/D-0045, 14/20); teléfono en TWRP, sin reiniciar (2026-11-14)
- **Tarea en curso: T-0012.** E-0163: kmem_init() termina y se anuncian las entradas STARTUP de KMEM (entre ellas kmem_range_init). herostop=53 solo prueba que se llegó al 53. BOOT = `xnu-boot-v2-s7-min14-20261114.img` (sha256 `1a0c4d20…0073b`); EFS intacto (E-0164).
- **Qué mirar (Director, tras `adb reboot`):** los nombres de fase irán apareciendo; **si el reinicio es un PÁNICO, `A5 XNU PANIC: …` quedará en pantalla** (la consola temprana sigue viva; en min10/min11 los pánicos se quedaron): copiarlo literal. Si NO hay pánico y acaba en la pantalla de reinicio (azul, cian, magenta, XNU MMU ON), es un cuelgue + reinicio por vigilante: anotar los últimos nombres que alcance a ver.
- Siguiente según el resultado: pánico ⇒ leer la causa; cuelgue ⇒ h54/h55/h56 (preparadas h56) para ver la fase tras 'kmem'.
- Restaurar BOOT original (E-0009) cubierto por D-0045.

## Relevo anterior: H-0059 — h52 congeló con kmem_init anunciada; h53 ESCRITA (D-0043/D-0045, 13/20); teléfono en TWRP, sin reiniciar (2026-11-14)
- **Tarea en curso: T-0012.** E-0161: vm_object_bootstrap y vm_map_init terminan; kmem_init se anuncia (la función donde min1 hizo panic en kmem_range_init). BOOT = `xnu-boot-v2-s7-min14h53-20261114.img` (sha256 `5a97c6aa…b877`); EFS intacto (E-0162).
- **Qué mirar (Director, tras `adb reboot`):** los nombres de antes y, debajo de `kmem_init`, **`vm_fault_init`** (slot 53). **Congela con `vm_fault_init` visible** ⇒ `kmem_init()` TERMINA y vm_mem_bootstrap casi acaba: el fallo es posterior (siguientes fases de kernel_bootstrap: hace falta h54+). **No congela** (reinicio) ⇒ el reinicio está DENTRO de `kmem_init()` (kmem_range_init y compañía).
- Restaurar BOOT original (E-0009) cubierto por D-0045.

## Relevo anterior: H-0058 — h50 llegó a vm_object_bootstrap; h52 ESCRITA (D-0043/D-0045, 12/20); teléfono en TWRP, sin reiniciar (2026-11-14)
- **Tarea en curso: T-0012.** E-0156: nombres de fase vistos (vm_mem_bootstrap … vm_object_bootstrap). BOOT = `xnu-boot-v2-s7-min14h52-20261114.img` (sha256 `22c7d73f…6f10`); EFS intacto (E-0160).
- **Qué mirar (Director, tras `adb reboot`):** los 10 nombres de antes y, debajo, **`vm_map_init`** y **`kmem_init`** (slots 51 y 52). **Congela** con `kmem_init` visible ⇒ el kernel anuncia `kmem_init` (donde min1 hizo panic con 2 GiB); el fallo es dentro de `kmem_init` o después ⇒ h53 (`vm_fault_init`) distingue. **No congela** (reinicio) ⇒ el reinicio está dentro de `vm_object_bootstrap()` o `vm_map_init()`: h51 distingue.
- Restaurar BOOT original (E-0009) cubierto por D-0045.

## Relevo anterior: H-0057 — min14h50 (kernel 0349: nombres de fase en pantalla) ESCRITA (D-0043/D-0045, 11/20); teléfono en TWRP, sin reiniciar (2026-11-14)
- **Tarea en curso: T-0012.** E-0148: arm_init termina; el reinicio está en machine_startup/kernel_bootstrap. D-0045 (ampliación de D-0043): enganches de dibujo en 5 ficheros del arranque, verificados por herramienta. Kernel 0349 revisado (E-0149). BOOT = `xnu-boot-v2-s7-min14h50-20261114.img` (sha256 `f01f9ce3…a39e`); EFS intacto (E-0155).
- **Qué mirar (Director, tras `adb reboot`):** bloque 40 blanco (de antes) y, unos 0,7 s después, **bloques nuevos con el NOMBRE de cada fase a su izquierda** (empiezan en el slot 41, bajo el blanco). herostop=50 congela tras la 10.ª fase (slot 50). **Congela** ⇒ los nombres dicen las 10 primeras fases y el fallo es posterior. **No congela** (pantalla de reinicio) ⇒ el reinicio es antes de la fase 10: leer los nombres que se vean y probar h44.
- Imágenes preparadas: min14 (sin herostop), h44, h56, h62 (E-0150, E-0152..E-0154).
- Restaurar BOOT original (E-0009) cubierto por D-0045.

## Relevo anterior: H-0056 — h29: pantalla negra con un bloque (serial_init pasa y limpia la consola); 0348 (bloques 30-40 en el resto de arm_init) en CI (2026-11-14)
- **Tarea en curso: T-0012** (D-0043, 9/20). E-0140: el kernel supera `serial_init` (el bloque 29 se dibuja después y la consola real borró lo anterior); el reinicio es posterior.
- **Hecho:** 0348 (bloques 30-40 tras cada paso restante de arm_init y consola temprana viva en A5XELTE); publicado en `mio`; CI en curso. Luego: revisión D-0043 (solo `osfmk/arm/arm_init.c`), imágenes herostop 35/40 etc.
- **Más allá de arm_init** (machine_startup → kernel_bootstrap → STARTUP_SUB_*) hay que marcar ficheros fuera de la lista blanca de D-0043 (`osfmk/arm/model_dep.c`, `osfmk/kern/startup.c`): pedir al Director ampliarla. También `-v` (verbose) en la línea de arranque para ver el log de kernel (D-0043 no lo cubre).
- Restaurar BOOT original (E-0009) cubierto por D-0043.

## Relevo anterior: H-0055 — h28 congeló (bloques 27 y 28); h29 ESCRITA (D-0043, 9/20); teléfono en TWRP, sin reiniciar (2026-11-14)
- **Tarea en curso: T-0012.** E-0137: el kernel vuelve de `arm_vm_init` a `arm_init` y llega justo antes de `serial_init`; el reinicio es posterior al bloque 28. BOOT = `xnu-boot-v2-s7-min12h29-20261114.img` (sha256 `8a66aedb…86b6`); EFS intacto (E-0139).
- **Siguiente (Director):** `adb reboot`, mirar. **Congela** con un bloque nuevo (29 gris) ⇒ `serial_init` termina; el reinicio es posterior (hace falta un kernel con más marcas tras `serial_init`: `kernel_startup_initialize_upto(STARTUP_SUB_KPRINTF)`, `kprintf`, etc.). **No congela** ⇒ el reinicio está DENTRO de `serial_init`.
- Restaurar BOOT original (E-0009) cubierto por D-0043.

## Relevo anterior: H-0054 — h26 congeló (bloques 25 y 26); h28 ESCRITA (D-0043, 8/20); teléfono en TWRP, sin reiniciar (2026-11-14)
- **Tarea en curso: T-0012.** E-0135: el kernel supera `pmap_bootstrap` y las tablas de E/S tempranas; el reinicio es posterior al bloque 26. BOOT = `xnu-boot-v2-s7-min12h28-20261114.img` (sha256 `453009ce…4e5f`); EFS intacto (E-0136).
- **Siguiente (Director):** `adb reboot`, mirar. **Congela** con un bloque nuevo (27 morado, 28 blanco) ⇒ el reinicio está en `serial_init` o después (h29, por construir). **No congela** ⇒ entre el bloque 26 y el 28: `arm_vm_init` terminando o el código previo a `serial_init` (h27 por construir).
- Restaurar BOOT original (E-0009) cubierto por D-0043.

## Relevo anterior: H-0053 — h24 congeló (bloques 19-24, sonda verde); h26 ESCRITA (D-0043, 7/20); teléfono en TWRP, sin reiniciar (2026-11-14)
- **Tarea en curso: T-0012.** E-0133: el kernel sobrevive a apagar TTBR0 y llega al bloque 24 (antes de `pmap_bootstrap`); el reinicio es posterior. BOOT = `xnu-boot-v2-s7-min12h26-20261114.img` (sha256 `99fff0a4…2c4e`); EFS intacto (E-0134).
- **Siguiente (Director):** `adb reboot`, mirar. **Congela** con bloques hasta el 26 (25 tras `pmap_bootstrap`, 26 tras las tablas de E/S) ⇒ reinicio posterior (h28). **No congela** ⇒ el reinicio está entre 24 y 26: `pmap_bootstrap` o las tablas de E/S (h25 por construir).
- Nota: adb se reenumera a veces; reintentar con espera (el script de escritura aborta antes de escribir si no ve el teléfono).
- Restaurar BOOT original (E-0009) cubierto por D-0043.

## Relevo anterior: H-0052 — min12h24 ESCRITA (D-0043, 6/20); teléfono en TWRP, sin reiniciar (2026-11-14)
- **Tarea en curso: T-0012.** BOOT = `xnu-boot-v2-s7-min12h24-20261114.img` (sha256 `a6942183…df0c`); EFS intacto (E-0132).
- **Siguiente (Director):** `adb reboot`, mirar. **Congela** con la página de stages, las líneas `A5V` y la columna de bloques hasta el 24 (20 verde = sonda ok, 21…24) ⇒ el reinicio es posterior al bloque 24 (siguiente h26, luego h28). **No congela** (azul/cian/magenta + XNU MMU ON) ⇒ el reinicio es anterior (siguiente h22).
- Restaurar BOOT original (E-0009) cubierto por D-0043.

## Relevo anterior: H-0051 — min12 ya no cuelga ni panica: acaba en reinicio; bisección con herostop 22-28 (2026-11-14)
- **Tarea en curso: T-0012** (D-0043, 5/20 usadas). E-0131: sin página de stages, sin A5V, sin pánico; pantalla de reinicio. Lectura: la sonda del alias pasa; el kernel sigue y se reinicia como en min2-min7.
- **Siguiente:** escribir **h24** (E-0128; kernel 0347; congela tras el bloque 24 = antes de `pmap_bootstrap`) y ver: congela con bloques 20…24 ⇒ el reinicio es posterior a 24 (h26, h28); no congela ⇒ anterior (h22).
- Restaurar BOOT original (E-0009) cubierto por D-0043.

## Relevo anterior: H-0050 — copias SYSTEM/USERDATA/RECOVERY hechas y verificadas; min12 (kernel 0347, 8 bloques de alias) ESCRITA (D-0043, 5/20) (2026-11-14)
- **Tarea en curso: T-0012.** T-0043 (copias) hecha: E-0123 (RECOVERY = copia del 12-nov), E-0124 (SYSTEM 7,75 GB), E-0125 (USERDATA 23,4 GB), cada una verificada por trozos y contra el hash de la partición entera en el teléfono. Carpeta `IOS-S7-backup/2026-11-14-engineer-full/` en el NVMe. La SYSTEM del snapshot del Director NO es válida (más corta).
- **BOOT = `xnu-boot-v2-s7-min12-20261114.img`** (sha256 `7718a774…c834`), leída de vuelta; EFS intacto (E-0126). Kernel 0347 (E-0121): el alias del framebuffer ahora cubre los 8 bloques de 2 MiB.
- **Siguiente (Director):** `adb reboot`, mirar. Esperado tras el bloque 19: **20 (sonda: VERDE = bien)**, **21**, y bloques 22-29 después de apagar TTBR0 si el kernel sigue; texto `A5V TTBR1/TCR/…/PAR` como antes; si hay `A5 XNU PANIC`, transcribir literal.
- **Riesgo pendiente:** las copias nuevas están en un solo disco (NVMe).
- Restaurar BOOT original (E-0009) cubierto por D-0043.

## Relevo anterior: H-0049 — min11: el alias mapeaba solo 2 MiB (granularidad de 4 KiB); parche 0347 (8 bloques) en CI (2026-11-14)
- **Tarea en curso: T-0012.** E-0118 + docs/S7GE_MIN11_RESULT.md: TG0/TG1 = 4 KiB, L2 = bloque de 2 MiB; el alias cubría las primeras ~364 filas; la sonda en la fila 1500 cayó fuera ⇒ fallo ⇒ pánico secundario en vm_fault.
- **Hecho:** 0347 (mapea 8 bloques de 2 MiB); publicado en `mio`; CI en curso. Luego: revisión D-0043, imagen min12 (sin herostop) y escribirla (D-0043: 4/20 usadas).
- **Teléfono:** en TWRP con min11. Restaurar BOOT original (E-0009) cubierto por D-0043.

## Relevo anterior: H-0048 — min11 (kernel 0346, sin herostop) ESCRITA (D-0043, 4/20); teléfono en TWRP, sin reiniciar (2026-11-14)
- **Tarea en curso: T-0012.** BOOT = `xnu-boot-v2-s7-min11-20261114.img` (sha256 `483bb381…685c`); EFS intacto (E-0117). Revisión del kernel E-0115; imagen E-0116.
- **Qué mirar (Director, tras `adb reboot`):** tras los cuatro `rb:`, líneas `A5V TTBR1=0x… / TCR / cpu_ttep / VA / L1e / L2e / PAR` (copiarlas literales), y el bloque 20 (VERDE = alias válido, ROJO = no). Si el alias es válido, el kernel sigue y se verán bloques 21+. Si no, queda parado con los números en pantalla.
- Restaurar BOOT original (E-0009) cubierto por D-0043.

## Relevo anterior: H-0047 — min10: pánico en la sonda del alias (mi parche); 0346 (AT + números) en CI (2026-11-14)
- **Tarea en curso: T-0012.** E-0114: `Invalid kernel stack pointer` en `_vm_fault_internal+0x24` (segundo fallo, NULL+0x9e); el primero es el acceso por el alias virtual en la sonda de 0345 (docs/S7GE_MIN10_PANIC.md).
- **Hecho:** 0346 (imprime TTBR1/TCR/cpu_ttep/VA/L1e/L2e, `AT S1E1W` + PAR_EL1, y solo escribe si la traducción existe; si no, se detiene con los números). Publicado en `mio`; CI en curso. Luego: revisión D-0043 (E-…), imágenes min11 y escribir (D-0043: 3/20 usadas).
- **Teléfono:** en TWRP con min10 (panica en la sonda). Restaurar BOOT original (E-0009) cubierto por D-0043.

## Relevo anterior: H-0046 — min10 (kernel 0345, sin herostop) ESCRITA (D-0043, 3/20); teléfono en TWRP, sin reiniciar (2026-11-14)
- **Tarea en curso: T-0012.** BOOT = `xnu-boot-v2-s7-min10-20261114.img` (sha256 `a88997bd…03bca`); EFS intacto (E-0113). Revisión del kernel E-0108; imágenes: E-0109 (sin herostop), E-0110/0111/0112 (h20, h21, h22).
- **Qué mirar (Director, tras `adb reboot`):** columna derecha tras el bloque 19: **bloque 20 = veredicto de la sonda (VERDE: el alias virtual ve la misma memoria que el físico; ROJO: no)**, **bloque 21 dibujado por el alias con TTBR0 vivo**, luego 22+ (tras apagar TTBR0). Posibles finales: texto de `A5 XNU PANIC` (transcribir literal), pantalla de reinicio, o congelada.
- Restaurar BOOT original (E-0009) cubierto por D-0043.

## Relevo anterior: H-0045 — min9 (sin herostop) quedó colgada en el bloque 19; parche 0345 (sonda del alias) en CI (2026-11-14)
- **Tarea en curso: T-0012.** E-0107: sin herostop y con 0344 la pantalla se congela como h19 (sin reinicio, sin pánico). Con kernels sin alias (0338-0342) acababa en reinicio.
- **Hecho:** 0345 escrito (aplica; pasa la lista blanca de D-0043): sonda del alias VA↔PA antes de apagar TTBR0 (bloque 20: verde = ok, rojo = distinta memoria; 21: dibujo por el alias con TTBR0 vivo); bloques posteriores renumerados 22-29. Publicado en `mio`; CI en curso. Luego: revisión D-0043 (evidencia), imágenes min10 (sin herostop y variantes 20…29) y escribirlas.
- **Teléfono:** en TWRP con min9. Restaurar BOOT original (E-0009) cubierto por D-0043.

## Relevo anterior: H-0044 — min9 (kernel 0344, sin herostop) ESCRITA (D-0043, 2/20); teléfono en TWRP, sin reiniciar (2026-11-14)
- **Tarea en curso: T-0012.** E-0105: con herostop=23 la pantalla quedó como en h19 (4 `rb:` y bloques hasta el 19; sin pánico ni bloques 20-23). BOOT = `xnu-boot-v2-s7-min9-20261114.img` (sha256 `501b889e…409e`), leída de vuelta; EFS intacto (E-0106).
- **Qué distingue min9:** si la pantalla acaba en el **estado de reinicio** (azul/cian/magenta + XNU MMU ON, sin texto) ⇒ el kernel NO se cuelga entre 19 y 20: avanza y el freeze de h23 era real pero el dibujo por el alias no se ve (el alias no funciona: revisar atributos/offset). Si acaba **congelada como h19** (texto + 19 bloques) ⇒ el kernel se cuelga justo al apagar TTBR0 o al dibujar por el alias (siguiente: prueba previa a TTBR0 off con lectura cruzada alias VA ↔ PA).
- Restaurar BOOT original (E-0009) cubierto por D-0043.

## Relevo anterior: H-0043 — min9h23 (kernel 0344, D-0043, 1/20) ESCRITA; teléfono en TWRP, sin reiniciar (2026-11-14)
- **Tarea en curso: T-0012.** BOOT = `xnu-boot-v2-s7-min9h23-20261114.img` (sha256 `4b0d8fd5…d8ed`); EFS intacto (E-0104). Revisión del kernel: E-0094; imágenes preparadas: E-0095…E-0103 (min9 sin herostop y h20…h27).
- **Siguiente (Director):** `adb reboot`, mirar la columna derecha: tras los 19 bloques de siempre, **20 naranja-rojo, 21 oro, 22 rosa, 23 verde** y la pantalla congelada. Si no hay bloques nuevos tras el 19: h20. Si hay un `A5 XNU PANIC`: transcribir archivo, línea y condición literales.
- Restaurar BOOT original (E-0009) cubierto por D-0043.

## Relevo anterior: H-0042 — autorización amplia de diagnóstico D-0043 registrada; CI de 0344 en curso (2026-11-14)
- **Tarea en curso: T-0012.** D-0043 (hasta 20 escrituras, hasta 2026-11-16): kernels del CI de `herolte-drop-v2` con 0332-0337 intactos y parches posteriores que pasen `tools/herolte-diag-patch-check.py` y estén revisados y registrados (evidencia con run, hash y qué hace cada cambio); mismo ADT y cargador; línea de min2 + `herostop=N`; 47/57 PASS; hashes registrados antes de escribir.
- **Ahora:** CI 43613119407 (0344) → cuando termine: ci_check, revisar el contenido de 0343+0344 (solo dibujo; ya hecho al escribirlos, registrar), construir h20…h27, escribir **h23** y continuar.
- El teléfono está en TWRP con h23 del kernel 0343 (que panica por mi fallo). Restaurar BOOT original (E-0009) cubierto por D-0043.

## Relevo anterior: H-0041 — h23 (kernel 0343) PANICÓ por un fallo de mi parche; corrección 0344 en CI (2026-11-14)
- **Tarea en curso: T-0012** (D-0042: 1/8 usada, pero el kernel va a cambiar). E-0093: `A5 XNU PANIC: arm_vm_init.c:1878 Assertion failed (l1 …TYPE_TABLE)` en `a5_early_map_final()`: falta la entrada L1 de `VM_MIN_KERNEL_ADDRESS`.
- **Hecho:** parche 0344 (`init_ptpages` antes de leer el L1) escrito, aplica; publicado en `mio` y CI lanzado. **Siguiente:** CI → descargar → construir h20…h27 con el kernel nuevo → pedir tanda nueva (D-0043) con su hash.
- **El teléfono** está en TWRP con h23 (kernel 0343, panica pronto: no sirve para más pruebas). Restaurar BOOT original (E-0009) cubierto por D-0042.

## Relevo anterior: H-0040 — tanda D-0042 (kernel 0343), imagen 1/8: h23 ESCRITA; teléfono en TWRP, sin reiniciar (2026-11-14)
- **Tarea en curso: T-0012.** BOOT = `xnu-boot-v2-s7-min8h23-20261114.img` (sha256 `493f8478…a8aa`), leída de vuelta; EFS intacto (E-0092). Quedan 7 escrituras.
- **Siguiente (Director):** `adb reboot`, mirar; contar los bloques de la columna derecha y decir el color de los últimos. Esperado: hasta el bloque 19 como h19, **más** los bloques 20 (naranja-rojo), 21 (oro), 22 (rosa), 23 (verde lima) si el kernel llega a 23 y se congela. **Si sigue en 19 y no hay más** ⇒ el alias virtual no funciona o el reinicio es anterior a 23: siguiente h20. **Si no congela** (azul/cian/magenta + XNU MMU ON): igual, h20/h21.
- Restaurar BOOT original (E-0009) cubierto por D-0042.

## Relevo anterior: H-0039 — kernel 0343 compilado; imágenes min8 listas; PENDIENTE decisión del Director (2026-11-14)
- **Tarea en curso: T-0012.** CI 43610634539 OK; ci_check: 0343 APLICADO; kernel `ac49a28e…6080`. Imágenes (verificadas, NO escritas): min8 (sin herostop) y min8h20…h27 (E-0083…E-0091).
- **Necesita:** decisión nueva del Director (D-0041 cubre solo el kernel `4e5f25a5…`): una tanda D-0042 para el kernel `ac49a28e…6080`, con el mismo ADT/cargador/línea de min2 y solo `herostop=N` (N 20-27) como diferencia. Propuesta de orden: **h23** primero; congela ⇒ h25 ⇒ …; no congela ⇒ h21 ⇒ h20/h22 (si ningún bloque ≥20 aparece, h20 comprueba que el alias del framebuffer funciona).
- El teléfono está en TWRP con h19 escrita. Restaurar BOOT original (E-0009) cubierto por D-0041.

## Relevo anterior: H-0038 — h19 CONGELÓ: el reinicio es posterior a apagar TTBR0; kernel nuevo en preparación (2026-11-14)
- **Tarea en curso: T-0012** (D-0041, 5/8 usadas, pero el siguiente paso exige un kernel nuevo y por tanto una decisión nueva). Observación E-0082.
- **Hecho:** parche 0343 (alias virtual del framebuffer tras TTBR0 + bloques 20-27) escrito, aplica sobre 0338-0342; a publicar en `mio` y compilar en CI (D-0030).
- **Siguiente:** CI → construir imagen (sin herostop y variantes) → pedir al Director autorización con hash del kernel nuevo (D-0041 no lo cubre).
- **El teléfono:** el Director vuelve a TWRP. BOOT = h19. Restaurar BOOT original (E-0009) cubierto por D-0041.

## Relevo anterior: H-0037 — h19 ESCRITA (5/8 de la tanda D-0041); teléfono en TWRP, sin reiniciar (2026-11-14)
- **Tarea en curso: T-0012.** h18 congeló con el bloque 18 visible (E-0079 + aclaración E-0080): `set_mmu_ttb_alternate` se supera. BOOT = `xnu-boot-v2-s7-min7h19-20261114.img` (sha256 `fd1ec365…22a1`), leída de vuelta; EFS intacto (E-0081). Quedan 3 escrituras.
- **Siguiente (Director):** `adb reboot`, mirar, **contar los bloques y decir el color de los dos últimos**. **Congela** con un bloque nuevo (blanco, slot 19) ⇒ el reinicio es posterior a apagar TTBR0 (hace falta kernel nuevo). **No congela** (azul/cian/magenta + XNU MMU ON) ⇒ el reinicio está entre los bloques 18 y 19.
- Restaurar BOOT original (E-0009) cubierto por D-0041.

## Relevo anterior: H-0036 — h18: observación AMBIGUA, pendiente de aclarar con el Director (2026-11-14)
- **Tarea en curso: T-0012** (D-0041, 4/8 usadas). E-0079: "nada nuevo en los stages, solo apareció otro cian abajo del todo".
- **Aclaración pedida:** ¿cuántos bloques en la columna derecha y de qué color el último (cian como en h17, o marrón chocolate)? ¿quedó congelada? Si es idéntica a h17 y congelada ⇒ el kernel no llega al bloque 18: falla en `set_mmu_ttb_alternate` (cambio a la TTBR1 final). Si hay un marrón nuevo ⇒ siguiente h19.
- **Diferencia con el kernel del upstream (todo lo que conocemos):** nuestros 0332-0337 no tocan el arranque temprano (0335 solo lee `herosplash`); un kernel upstream (artefacto `kernel-0331-upstream-1c454bf`) con nuestro cargador/ADT/línea sería el contraste limpio; exige decisión nueva (otro kernel no está en D-0041).
- Restaurar BOOT original (E-0009) cubierto por D-0041.

## Relevo anterior: H-0035 — h18 ESCRITA (4/8 de la tanda D-0041); teléfono en TWRP, sin reiniciar (2026-11-14)
- **Tarea en curso: T-0012.** BOOT = `xnu-boot-v2-s7-min7h18-20261114.img` (sha256 `3f6b2fa7…f09a`), leída de vuelta; EFS intacto (E-0078). Quedan 4 escrituras.
- **Siguiente (Director):** `adb reboot`, mirar. **Congela** con un bloque nuevo (chocolate, slot 18) debajo de los 18 anteriores ⇒ el reinicio es posterior a `set_mmu_ttb_alternate` (siguiente h19). **No congela** (azul/cian/magenta + XNU MMU ON) ⇒ el reinicio está en `set_mmu_ttb_alternate` (el cambio a la TTBR1 final).
- Restaurar BOOT original (E-0009) cubierto por D-0041.

## Relevo anterior: H-0034 — h17 CONGELÓ: arm_vm_physmap_init termina; el reinicio es posterior al bloque 17 (2026-11-14)
- **Tarea en curso: T-0012** (D-0041, 3/8 usadas). Observación E-0077.
- **Siguiente:** el Director fuerza el apagado (Vol− + Power ~7 s), entra en TWRP y avisa; el ingeniero escribe **h18** (sha256 en las evidencias de la serie preparada, E-0073). Si h18 **no** congela ⇒ el reinicio está en `set_mmu_ttb_alternate` (cambio de TTBR1 a la tabla final); si congela ⇒ h19.
- Idea en estudio para ir más rápido (no hecha): parche 0343 con pausas temporizadas en vez de congelar (`heropause`), para ver varias etapas en un solo arranque.
- Restaurar BOOT original (E-0009) cubierto por D-0041.

## Relevo anterior: H-0033 — h17 ESCRITA (3/8 de la tanda D-0041); teléfono en TWRP, sin reiniciar (2026-11-14)
- **Tarea en curso: T-0012.** BOOT = `xnu-boot-v2-s7-min7h17-20261114.img` (sha256 `5bf549f0…1ee0`), leída de vuelta; EFS intacto (E-0076). Quedan 5 escrituras.
- **Siguiente (Director):** `adb reboot`, mirar. **Congela** con texto hasta `rb: physmap_init` **más** `7: rb: extra banks` / `rb: extra banks mapped` (marcas de dentro de `arm_vm_physmap_init`) y el bloque 17 (turquesa oscuro) ⇒ el reinicio es posterior (siguiente h18). **No congela** (azul/cian/magenta + XNU MMU ON) ⇒ el reinicio está **dentro de `arm_vm_physmap_init`**.
- Restaurar BOOT original (E-0009) cubierto por D-0041.

## Relevo anterior: H-0032 — h16 CONGELÓ: el reinicio es posterior al bloque 16 (antes de arm_vm_physmap_init) (2026-11-14)
- **Tarea en curso: T-0012** (D-0041, 2/8 usadas). Observación E-0075: texto hasta `rb: physmap_init`, 17 bloques, hueco del 14 esperado (`#if ARM_LARGE_MEMORY` no compilado).
- **Siguiente:** el Director fuerza el apagado (Vol− + Power ~7 s), entra en TWRP (Vol+ + Home + Power) y avisa; el ingeniero escribe **h17** (sha256 en E-0072; ya registrado). Si h17 **no** congela ⇒ el reinicio está dentro de `arm_vm_physmap_init`.
- Restaurar BOOT original (E-0009) cubierto por D-0041.

## Relevo anterior: H-0031 — h16 ESCRITA (2/8 de la tanda D-0041); teléfono en TWRP, sin reiniciar (2026-11-14)
- **Tarea en curso: T-0012.** BOOT = `xnu-boot-v2-s7-min7h16-20261114.img` (sha256 `6c8caa70…2962d`), leída de vuelta; EFS intacto (E-0074). Quedan 6 escrituras.
- **Siguiente (Director):** `adb reboot`, mirar. Resultados: **congela** con texto hasta 6c más la marca "7: entering arm_vm_init" y rosa/turquesa/marrón (slots 13-15) + slot 16 ⇒ el reinicio es posterior a 16 (siguiente h18); **no congela** (azul/cian/magenta + XNU MMU ON) ⇒ anterior a 16 (siguiente h14). Plan en `docs/S7GE_HEROSTOP_BISECT.md`.
- Restaurar BOOT original (E-0009) cubierto por D-0041.

## Relevo anterior: H-0030 — min7h08 CONGELÓ: el reinicio es posterior a la marca 6c (2026-11-14)
- **Tarea en curso: T-0012** (autorización vigente D-0041, 1 de 8 escrituras usada).
- **Observación (E-0067):** tras `adb reboot`, pantalla congelada con texto de las marcas 1-6c y la columna derecha de 12 bloques tal como se predijo. El kernel llega a `arm_init` hasta 6c; **el reinicio ocurre después**. El teléfono sigue encendido y congelado: hay que forzar el apagado.
- **Siguiente:** el Director entra en TWRP (Vol− + Power ~7 s para apagar/reiniciar y, al arrancar, Vol+ + Home + Power) y avisa; el ingeniero escribe **h16** (`xnu-boot-v2-s7-min7h16-20261114.img`, sha256 en E-0065, ya registrado) y se repite. Orden y plan: `docs/S7GE_HEROSTOP_BISECT.md`.
- Restaurar BOOT original (E-0009) cubierto por D-0041.

## Relevo anterior: H-0029 — tanda D-0041 (imagen 1/8: min7h08, herostop=8) ESCRITA; teléfono en TWRP, SIN reiniciar (2026-11-14)
- **Tarea en curso: T-0012** (autorización vigente D-0041).
- **Hecho:** kernel CI 43603366417 (0338-0342, sha256 `4e5f25a5…4d6f`), imagen `xnu-boot-v2-s7-min7h08-20261114.img` (sha256 `0bb5e7a6…a37ff`), leída de vuelta; EFS intacto (E-0059, E-0060). Quedan 7 imágenes de la tanda.
- **Canal de RAM:** `/dev/mem` imposible (TWRP sin CONFIG_DEVMEM); el contador de 0342 no se puede leer desde TWRP. Alternativa pendiente de pensar (no hecha): breadcrumbs dentro de una región que TWRP exponga.
- **Siguiente (Director):** grabar, `adb reboot`, ≥ 2 min. **Resultado esperado:** pantalla CONGELADA con la columna derecha (x≈1300) de **12 bloques** (slots 0-8 y 10-12, con el hueco del slot 9 en y≈376) si el kernel llega a esa marca (ver `docs/S7GE_HEROSTOP_BISECT.md`); si se ve el reinicio de siempre (azul/cian/magenta + XNU MMU ON, sin columna), el reinicio ocurre antes del bloque 8. Luego yo decido el siguiente N (bisección 12 / 16 / 19) y construyo la imagen en el PC.
- Restaurar BOOT original (E-0009) cubierto por D-0041.

## Relevo anterior: H-0028 — min6 ESCRITA (D-0039) y verificada; el teléfono está en TWRP, SIN reiniciar (2026-11-14)
- **Hecho:** el Director firmó (D-0039) tras ver el hash. BOOT = `xnu-boot-v2-s7-min6-20261114.img` (sha256 `4f412a5b…29b43`), leído de vuelta igual; EFS intacto dentro de la sesión (E-0056). Nada más escrito.
- **Tarea en curso: T-0012.** Siguiente (Director): grabar en cámara lenta encuadrando la **columna derecha** (x≈1300), `adb reboot`, ≥ 2 min; contar de arriba abajo los bloques (hasta 20) y capturar el último fotograma antes de que la pantalla vuelva a "azul, cian, magenta, XNU MMU ON". Si no arranca: Vol− + Power ~7 s y Vol+ + Home + Power.
- **Lectura:** último bloque = última fase alcanzada (`S7GE_MIN6_ANALYSIS.md`, `S7GE_ARM_VM_INIT_ANALYSIS.md` §4). Restaurar el BOOT original (E-0009) está cubierto por D-0039. Lectura `/dev/mem` NO autorizada (D-0038 solo cubrió last_kmsg/iomem, ya hechas, E-0054).

## Relevo anterior: H-0027 — min5 ESCRITA (D-0037) y verificada; el teléfono está en TWRP, SIN reiniciar (2026-11-14)
- **Hecho:** el Director firmó (D-0037). BOOT = `xnu-boot-v2-s7-min5-20261114.img` (sha256 `4cb134c2…93bd5`), leído de vuelta igual; EFS intacto dentro de la sesión (E-0053). Nada más escrito.
- **Tarea en curso: T-0012.** Siguiente (Director): grabar en cámara lenta, **encuadrando también el borde derecho** (columna x=1300: rojo, verde, azul, amarillo, cian, magenta, naranja, lima, violeta, blanco de arriba abajo = etapas 1,2,3,4,5,6,6a,6b,6c,7), `adb reboot`, ≥ 2 min. Si no arranca: Vol− + Power ~7 s y Vol+ + Home + Power.
- **Lectura:** ningún bloque en la columna ⇒ el cuelgue es anterior a `arm_init`; hasta el bloque n ⇒ la etapa n+1 no termina. Min6 (variar argumentos) solo tras ver esto. Restaurar el BOOT original (E-0009) está cubierto por D-0037.

## Relevo anterior: H-0026 — min4 ESCRITA (D-0036) y verificada; el teléfono está en TWRP, SIN reiniciar (2026-11-14)
- **Hecho:** el Director firmó (D-0036). BOOT = `xnu-boot-v2-s7-min4-20261114.img` (sha256 `8e8725f3…980b4`), leído de vuelta igual; EFS intacto dentro de la sesión (E-0051). Nada más escrito.
- **Tarea en curso: T-0012.** Siguiente (Director): grabar en cámara lenta y de cerca, `adb reboot`, ≥ 2 min; rellenar `docs/S7GE_MIN4_OBSERVATION_TEMPLATE.md` (siete bloques por posición y color, texto literal, captura final). Si no arranca: Vol− + Power ~7 s y Vol+ + Home + Power.
- **Después:** si se ven magenta y los naranjas, o hay ambigüedad por el texto, min5 = 0339 (`docs/S7GE_MIN5_DESIGN.md`; commit local, no empujado; requiere CI y autorización nueva). Restaurar el BOOT original (E-0009) está cubierto por D-0036.

## Relevo anterior: H-0025 — min3 ESCRITA (D-0035) y verificada; el teléfono está en TWRP, SIN reiniciar (2026-11-14)
- **Hecho:** el Director firmó la autorización (D-0035) con imagen y hash. `tools/herolte-flash-boot.sh --execute`: BOOT = `xnu-boot-v2-s7-min3-20261114.img` (sha256 `c70d3dd8…e36f`), leído de vuelta igual; EFS intacto (E-0049). Nada más escrito.
- **Tarea en curso: T-0012.** Siguiente (Director): grabar en cámara lenta y de cerca, `adb reboot`, ≥ 2 min, y pasar el texto literal indicando que es de min3: ¿sale `A5 XNU STAGE 7`? ¿cinco bloques? ¿texto nuevo o panic? Si no arranca: Vol− + Power ~7 s y Vol+ + Home + Power.
- **Pendiente de aclarar:** de qué arranque (min1/min2) es la transcripción STAGE 1-6 (MIN3_ANALYSIS §3); si es de min2, min3 probablemente no cambia el resultado y el paso siguiente son marcas entre las etapas 6 y 7 (kernel nuevo, CI).
- Restaurar el BOOT original (E-0009) está cubierto por D-0035.

## Relevo anterior: H-0024 — segundo arranque (min2): pantalla fija con los bloques de color de XNU; sin conclusión firme todavía (2026-11-14)
- **Observación (E-0047, transcripción de terceros; no he visto el vídeo):** cargador → `RAM BASE` → pantalla fija con bloques de color (magenta, cian, azul), sin panic ni `HEROLTE KMEM:`. **`NO XNU ON` no existe** en cargador ni kernel (mala lectura probable). **Los bloques los dibuja XNU** (`start.s`: verde=entrada, azul=MMU, cian=fp, magenta=tunables, amarillo=`arm_init_jump`; 36×21 px en x=240, y=88/120/152/184/216; texto `XNU ENTRY`/`XNU MMU ON` en y=256/288): el ensamblador de arranque ejecutó **al menos hasta `tunables_done`**. Falta saber si están el verde y el amarillo (→ si entró en C).
- **No concluir:** "ya no hay panic, luego `vm_compression_limit` funcionó" (un cuelgue silencioso también no muestra panic); "ADT incorrecto / handoff" (parten de la cadena inexistente). **Pregunta abierta:** con la consola de texto activa por defecto debería verse al menos el banner y `HEROLTE KMEM:`.
- **El Director dijo "autorizo seguir con min3 o lo que tú veas":** NO es una autorización de escritura (no nombra imagen ni hash; no existe min3). **Nada se escribió ni se leyó del teléfono.** Estado: TWRP con min2 en BOOT. D-0034 sigue cubriendo solo min2 y la restauración.
- **Siguiente:** pedir fotos fijas de la pantalla final y del instante del texto del cargador (`BOOTARGS`); luego elegir entre P (mirar), Q (leer RAM/pstore: lectura nueva que hay que autorizar), R (imagen con más marcas/diagnóstico), S (1 536 MiB) o T (restaurar Android). Detalle en `docs/S7GE_MIN2_ANALYSIS.md`. Tarea en curso: **T-0012**.

---

## Relevo anterior: H-0023 — min2 ESCRITA y verificada (D-0034); el teléfono está en TWRP, SIN reiniciar (2026-11-14 12:31)
- **Hecho:** tras poner el Director el teléfono en TWRP y un `adb reconnect offline` (no reinicia el servidor), `tools/herolte-flash-boot.sh --execute` dio `OK: BOOT escrito y leído de vuelta (18 618 384 bytes, sha256 595316aa…edae21); EFS intacto` (E-0046). Los intentos anteriores de las 12:29-12:30 abortaron sin escribir (adb `offline`).
- **El EFS en vivo cambió entre sesiones** (`eb8912ad…` → `b006b26d…`): el superbloque ext4 cambia con cada sesión de TWRP; el script compara dentro de la sesión (idéntico). Esperado, no un fallo.
- **Tarea en curso: T-0012** (primer arranque N2). **Estado del teléfono:** TWRP, BOOT = min2. **Siguiente (Director):** grabar la pantalla (con fotogramas legibles de las líneas `HEROLTE KMEM:` si vuelve a haber panic), `adb reboot`, ≥ 2 min, pasar la transcripción literal; si no arranca, Vol− + Power ~7 s y Vol+ + Home + Power. Luego restaurar BOOT (`S7GE_FLASH_PROCEDURE.md` §4) si se quiere volver a Android. **Ningún otro intento está autorizado** (D-0034 = min2 + restauración).

---

## Relevo anterior: H-0022 — min2 AUTORIZADA (D-0034) pero NO escrita: el teléfono está `offline` en adb (2026-11-14 12:30)
- **Director:** "Autorizo min2, firmado PioXI" → **D-0034** (`device-write-boot` + `device-read`, imagen `xnu-boot-v2-s7-min2-20261114.img`, SHA-256 `595316aa…edae21`, hasta 2026-11-16), colgada de **T-0012**. El `gate` autoriza.
- **Intento de escritura:** `tools/herolte-flash-boot.sh … --execute` **abortó sin tocar nada** (`debe haber exactamente un dispositivo en recovery`): minutos antes `adb devices` mostraba `recovery`, ahora el dispositivo aparece `offline` (probablemente arrancó/entró en el bucle de panic). **Nada se escribió** (el script comprueba antes de cualquier escritura).
- **Pendiente del Director:** dejar el teléfono en **TWRP** (Vol− + Power ~7 s, y enseguida Vol+ + Home + Power) y avisar; entonces el ingeniero repite el `--execute` (misma autorización) y el teléfono se queda en TWRP hasta que el Director grabe y reinicie.
- Sigue pendiente: fotogramas del vídeo con las líneas `HEROLTE KMEM:` del primer panic (confirmarían la hipótesis) y archivar el vídeo con su hash.

---

## Relevo anterior: H-0021 — primer arranque real: PANIC en kmem_range_init (clase B); causa probable = la configuración de RAM ya documentada (2026-11-14)
- **Observación (E-0044, transcripción de terceros; yo no vi el vídeo):** cargador → `COPYING KERNEL` → `RAM BASE 0x80000000` → **XNU hace panic en `kmem_range_init`** (`vm_map_locate_space failing…`) + `handshake structure not initialized` (que es del volcado de core, no la causa). El cargador y el kernel **ejecutan en esta unidad**; el kernel **no completó el arranque**. La transcripción dice `kext_range_init`: lectura defectuosa de `kmem_range_init` (medido con `strings` en el kernel del CI).
- **Causa más probable (hipótesis fuerte):** nuestro ADT declara **2 GiB** (`dram-size 0x80000000`, leído del fichero) y la línea **no lleva `vm_compression_limit=98304`**: es el pánico que `HEROLTE_PROGRESS.md` (2026-10-23/24) ya documentó (compresor de 16×RAM). **Error de proceso mío:** el verificador no compara contra la configuración funcional (KI-0009; punto 20 de la lista previa).
- **Candidata min2** (solo añade `vm_compression_limit=98304 vm_compressor=2`): `xnu-boot-v2-s7-min2-20261114.img`, SHA-256 `595316aa…edae21`, 47/56 PASS (E-0045). **NO escrita; requiere una autorización NUEVA con ese hash** (D-0033 cubre solo la imagen mínima 1 y la restauración).
- **Estado del teléfono:** tiene escrita la imagen que da panic (y no sé si está en TWRP o en bucle: lo sabe el Director). Para usar Android: restaurar BOOT (`S7GE_FLASH_PROCEDURE.md` §4; cubierto por D-0033).
- **Tarea en curso: T-0012** (primer arranque N2; fase 1 ejecutada, siguiente intento pendiente de autorización).
- **Pedir al Director:** (1) fotogramas del vídeo con las líneas `HEROLTE KMEM:` anteriores al panic y el texto completo del panic; (2) archivar el vídeo con su hash; (3) decidir: restaurar Android ya, o autorizar min2.

---

## Relevo anterior: H-0020 — FASE 1 AUTORIZADA Y BOOT ESCRITO; el teléfono sigue en TWRP, SIN reiniciar (2026-11-14 12:00)
- **Director:** "Autorizo la fase 1, firmado PioXI" → **D-0033** (`device-write-boot` + `device-read`, imagen mínima `07ddfa06…5db3`, hasta 2026-11-16), colgada de **T-0012** (en curso). **Ejecutado por el ingeniero** con `tools/herolte-flash-boot.sh --execute`: `OK: BOOT escrito y leído de vuelta (18 618 384 bytes, sha256 07ddfa06…5db3); EFS intacto (eb8912ad…7817)` (E-0043; el EFS del teléfono coincide con el `EFS.img` del snapshot).
- **Estado exacto del teléfono ahora:** en **TWRP**, con el BOOT **nuevo** (la variante mínima) escrito y verificado; **NO se ha reiniciado**: el experimento empieza cuando el Director reinicie, **con la pantalla grabada** (`adb reboot`). Nada más se ha escrito (ni `/sdcard`, ni EFS, ni RECOVERY, ni USERDATA).
- **Siguiente (Director):** grabar, reiniciar, observar ≥ 2 min y, si no arranca, forzar TWRP (Vol− + Power ~7 s, luego Vol+ + Home + Power); transcribir la pantalla y pasársela al ingeniero: `tools/herolte-boot-transcript-check.py … --min`, criterios A-E en `S7GE_MIN_BOOT_VALIDATION.md`. Después **restaurar BOOT** (`S7GE_FLASH_PROCEDURE.md` §4) mientras no haya raíz.
- **Si algo se tuerce, la vuelta atrás es la de siempre** (`BOOT.img` de E-0009, que está en el PC). La autorización cubre también esa restauración.
- **Ningún otro paso está autorizado:** la candidata normal, fase 3, es otra imagen y otra autorización.

---

## Relevo anterior: H-0019 — guía de flasheo corregida (2026-11-14)
- **Hecho (T-0039, solo documentos):** `docs/S7GE_FLASH_PROCEDURE.md` para el Director: recomienda `tools/herolte-flash-boot.sh` (ensayo + `--execute` solo con la autorización registrada) y da el equivalente manual **corregido**. Corrige 8 errores del borrador de jefatura, los de mayor impacto: `/sdcard` es USERDATA en TWRP (usar `/tmp`); `sha256sum` de la partición entera nunca coincide con el de la imagen (usar `head -c`); **no vuelve a TWRP solo** (teclas); **el BOOT original no está en el móvil** (se empuja desde el PC); `herolog=1` escribiría en USERDATA (otra imagen y otra autorización).
- **No ejecuté la Fase 23 (comprobar el móvil con `adb ls`):** es leer el dispositivo (rojo) y la guía no lo necesita.
- **Pendiente (Director):** firmar la autorización de la fase 1 con el texto de la solicitud §7; decidir si repite SYSTEM/USERDATA. **Siguiente (verde): T-0035.**

---

## Relevo anterior: H-0018 — el snapshot de backup del Director NO está completo; qué sirve y qué no (2026-11-14)
- **Medido (T-0038, solo lectura, sin adb, nada modificado; E-0042; `docs/S7GE_BACKUP_STATUS.md`):** `BOOT.img` bueno (el prefijo = E-0009; 98 bytes de cola de `dd`); `EFS.img` bueno (8 bytes de superbloque ext4 distintos de 11-12: un montaje más); **`RECOVERY.img` TRUNCADA (7,8 de 48,2 MB)**; `SYSTEM.img` 5,7 GB sin verificar; **`USERDATA.img` 0 B**. La jefatura lo dio por "completo": no lo es. USERDATA en tarjeta SD: declarada, **sin ruta ni hash**, por eso **no** se registra como evidencia (el `E-0041` que proponía ya es del OSMesa).
- **Lo que necesita la fase 1 SÍ está cubierto** por las copias verificadas de 2026-11-12 (BOOT, EFS, **RECOVERY completa**). La fase 1 no toca SYSTEM ni USERDATA.
- **No hecho (rojo, no autorizado):** comparar contra el teléfono con `adb` (`device-read`). Comandos de solo lectura listos en `S7GE_BACKUP_STATUS.md` §6. **No se recortó nada en sitio** (innecesario: solo BOOT tiene cola y es redundante con E-0009).
- **Errores del borrador de jefatura que no deben llegar a la firma:** el hash de la imagen terminaba en `…8f40` (es el de la NORMAL; la mínima termina en `…5db3`) y llevaba el **número de serie** del teléfono (privado). La solicitud (`herolte-solicitud-n2.md` §7) ya trae el hash completo y correcto y sin serie.
- **Corrección de expectativa:** el EFS del teléfono **no tiene por qué coincidir con la copia de 11-12** (superbloque); el script compara antes/después de la sesión.
- **Pendiente del Director:** la autorización roja de la fase 1 (y si quiere la lectura del teléfono), decidir si repite SYSTEM/USERDATA. **Siguiente (verde): T-0035.**

---

## Relevo anterior: H-0017 — B2 autorizada por el Director (D-0032) y el OSMesa propio compila sobre Mesa 26.2.4 (2026-11-14)
- **Director:** "Autorizo B2". **Hecho (T-0036):** `gpu/mesa/osmesa-frontend/` (fuentes de Mesa 25.0.7 sin tocar + `patches/0001-osmesa-no-postprocess.patch` + `integrate.py` con anclas exactas + Meson 26.x + README + 7 pruebas; la prueba encontró y corrigió un fallo de idempotencia). **Compila en Linux sobre Mesa 26.2.4 (913/913) y una prueba mínima da el píxel correcto (E-0041).** Documentos: `S7GE_OSMESA_MESA26_COMPATIBILITY.md` (lo que rompió: Meson ≥1.4, opciones, `with_shared_glapi`, `libglapi_static`, `glapi.h`, módulo `postprocess` eliminado), `S7GE_OSMESA_TEST_PLAN.md`, `S7GE_OSMESA_B2_RISKS.md`.
- **No resuelto:** el gancho de `mmap` de Panfrost (2 de 12 ediciones de `patch-mesa.py` fallan en 26.2.4), el glue `osmesa_hero.inc`/`hero_hw.c`, Panfrost compilado y Darwin (T-0037, bloqueada: falta `libdrm-dev`, instalar herramientas del sistema es rojo). **`gpu/mesa/build-mesa.sh` sigue en Mesa 25.0.7: el drop no cambia.**
- **Corrección de un dato mío anterior:** "fallan 3 ediciones" salió de una segunda pasada sobre un árbol ya modificado; son 2.
- **La variante mínima del primer arranque no usa GL**: nada de esto afecta al flasheo. Backup del Director en otra terminal: no tocar adb ni esa carpeta. **Siguiente (verde): T-0035.**

---

## Relevo anterior: H-0016 — herramienta de flasheo con salvaguardas lista; D-0031 (OSMesa) solo como política (2026-11-14)
- **Hecho (T-0034):** `tools/herolte-flash-boot.sh` (ensayo por defecto; `--execute` exige que `governance.py gate device-write-boot --task T-0012` autorice; comprueba hash, sda5, tamaño, EFS antes/después, hash en el teléfono y lectura de vuelta) con **13 pruebas con un adb FALSO**; `tools/herolte-boot-transcript-check.py` (clasifica la transcripción A-E; **no hay log que extraer**: `herolog=0`); `S7GE_PREFLIGHT_CHECKLIST.md` (19 puntos con su estado real; el rollback está **documentado, no ensayado**), `S7GE_FLASH_SCRIPTS.md`, `S7GE_POST_FLASH_ANALYSIS.md`, `S7GE_OSMESA_FORK_POLICY.md`.
- **D-0031 (jefatura):** OSMesa lo mantenemos nosotros; **no se implementa nada** hasta que el Director confirme y se elija B1 (congelar Mesa 25.0.7) o B2 (solo el frontend sobre un Mesa más nuevo). Señal a favor de B2: las 18 funciones de Mesa que usa `osmesa.c` existen en 26.2.4 con la misma declaración (no compilado).
- **Cuando el Director autorice el flasheo:** registrar su decisión `APPROVED` (`authorizes` con `device-write-boot` y `device-read`, hash de la imagen en el texto), poner `authorization_ref` en T-0012, ensayo del script, después `--execute`. **El ingeniero no ejecuta el script sin esa decisión; la herramienta tampoco.**
- **Backup del Director en otra terminal:** no tocar adb ni esa carpeta. **Siguiente (verde): T-0035** (renovar la línea base de regresión y repetir la batería de mutantes de governance.py; no lanzarla si compite con el backup).

---

## Relevo anterior: H-0015 — Fases 10-13 hechas; hallazgo: OSMesa no existe desde Mesa 25.1 (2026-11-14)
- **Hecho (T-0033, solo documentos y descargas públicas):** `S7GE_BOOT_LOG_EXPECTATIONS.md`, `S7GE_ROLLBACK_PLAN.md` (**no restaurar con el BOOT del snapshot sin recortar**: lleva 98 bytes de más, KI-0008), `S7GE_MESA_VERSION_ANALYSIS.md` (parcheador: 12/12 sobre Mesa 25.0.7; **falla en 26.2.4 porque OSMesa fue eliminado en 25.1.0**; licencias de Mesa y libdrm verificadas: MIT), `S7GE_EXECUTIVE_SUMMARY.md`.
- **Para el Director:** la fase 1 (variante mínima) sigue esperando tu autorización roja, el backup completo/recortado y, recomendado, una segunda copia de EFS. Plan, criterios y vuelta atrás están en `herolte-solicitud-n2.md`, `S7GE_MIN_BOOT_VALIDATION.md`, `S7GE_BOOT_LOG_EXPECTATIONS.md`, `S7GE_ROLLBACK_PLAN.md`. **Riesgo residual:** si TWRP no responde no hay camino de restauración documentado por Download/Odin.
- **Decisión de jefatura nueva necesaria:** qué hacer con OSMesa (quedarse en 25.0.7 / mantenerlo / otra superficie de Mesa).
- **Sin tareas verdes abiertas.**

---

## Relevo anterior: H-0014 — decisión de jefatura: primer flasheo con la variante mínima; Fases 7-9 hechas (2026-11-14)
- **Decisión (jefatura, nivel B):** primer flasheo = `xnu-boot-v2-s7-min-20261114.img` (SHA-256 `07ddfa06…5db3`, E-0040); la candidata normal (`2c155829…8f40`, E-0038) queda para una **fase 3 con autorización propia**. `docs/herolte-solicitud-n2.md` está reescrita (fases 1-4, texto de autorización de la fase 1). **Siguen pendientes del Director:** backup completo y recortado (KI-0008) y la firma de la autorización roja.
- **Hecho (T-0032, solo documentos):** `S7GE_MIN_BOOT_VALIDATION.md` (qué observar, criterios A-E fijados antes de arrancar, protocolo, qué no concluir), `S7GE_EXTRACTION_INTERFACES.md`, `S7GE_CONSOLIDATION_RISKS.md` (R1-R10), `S7GE_EAGL_BRIDGES.md` (propuesta: conservar hakios-gl, sin medir), `S7GE_A5XELTE_LESSONS.md` (la 8.ª: A5 se negó a exponer descriptores crudos; herolte los expone), `S7GE_INCONSISTENCIES.md` (17 filas; corrige dos afirmaciones de la directiva: el upstream de herolte es T880, no un A5/Exynos 7580; STATUS cita Mesa 26.2.4).
- **Backup del Director en otra terminal:** no tocar adb ni esa carpeta.
- **Sin tareas verdes abiertas.** Esperas: autorización roja de la fase 1; decisiones de jefatura sobre consolidar/separar y sobre el puente EAGL.

---

## Relevo anterior: H-0013 — modelado S7GE Fases 4-6 hecho; hallazgo sobre lo que hace N2 en el hardware (2026-11-14)
- **Hecho (T-0031, solo documentos y una candidata en el PC):** `S7GE_SPLIT_PLAN.md` (mapa medido de `herolte_gpu.c`: GPU 1 960 líneas, el resto ~1 350; audio y Wi-Fi son autocontenidos; los no-GPU solo dependen de `hg_rd/hg_wr/msleep`; la presentación sí está acoplada al display), `S7GE_PATCH_DEPENDENCIES.md` (63 parches tocan `herolte_gpu.c`; candidatos a consolidar; la vía segura es una serie paralela con árbol idéntico, no quitar parches), `S7GE_MESA_INTEGRATION.md`, `S7GE_INCONSISTENCIES.md` (14 puntos), entitlements de la jefatura incorporados al ABI v2 **con su límite**: con `cs_enforcement_disable=1` el entitlement no es una barrera, la barrera es la AS por contexto.
- **Hallazgo importante para el flasheo:** la candidata N2 es de solo lectura para el **almacenamiento**, no para el hardware: por defecto arranca el hilo de **Wi-Fi** (escribe GPIO, reloj, PMU y PCIe), el de bus/display y los de energía y medición. No toca tensión ni frecuencia de CPU (sin `herocpu_mhz`). Variante de menor huella construida y verificada: `xnu-boot-v2-s7-min-20261114.img` (SHA-256 `07ddfa06…5db3`, E-0040, +`herowifi=0 heropower=0 herogpu=0`). **El Director/jefatura elige cuál** (la solicitud en `docs/herolte-solicitud-n2.md` lo explica).
- **Backup del Director (NVMe) sigue en otra terminal:** no tocar adb ni esa carpeta. Recortar la cola de dd al terminar (KI-0008).
- **Pendiente:** autorización roja de flasheo (Director); decisiones de jefatura sobre separar `herolte_gpu.c` y la serie consolidada; ninguna tarea verde abierta.

---

## Relevo anterior: H-0012 — modelado S7GE Fases 0-3 hecho (solo documentos); el backup del S7 corre en otra terminal (2026-11-14)
- **Hecho (T-0030, VERDE, sin tocar parches ni código):** `docs/S7GE_INVENTORY.md` (86 parches tocan los ficheros de GPU, ~40 son el núcleo; **`herolte_gpu.c` (3 465 líneas) también contiene audio, Wi-Fi, relojes de CPU y display**: hay que sacarlos antes de rediseñar S7GPU), `S7GE_EXECUTION_MODEL.md` (secuencia de job por sondeo, AS0 única, recuperación por escalera, causa de los `0x42` sin demostrar), `S7GE_ABI_V2_PROPOSAL.md` (contexto con AS propia, handles con generación, entitlement, errores estructurados, migración), `S7GE_IR_DESIGN.md` (10 categorías de nodo del macroinforme, validador, pruebas de host).
- **Backup del Director en curso (NVMe):** no tocar adb ni esos ficheros. Hallazgo KI-0008: `adb exec-out dd` añade ~98 bytes de texto de dd a cada imagen; recortar después con `tools/herolte-trim-dd-tail.py` (informa por defecto) y comparar con el sha256 calculado EN el teléfono. La evidencia del backup será la siguiente entrada libre de evidence.toml.
- **Pendiente del Director:** autorización roja de `device-write-boot` (texto y procedimiento en `docs/herolte-solicitud-n2.md`), tras completar y comprobar el backup. Sin L3/L4 de esta unidad.
- **Sin tareas verdes abiertas** salvo continuar el modelado (Fases 4-6, esperan a la jefatura).

---

## Relevo anterior: H-0011 — candidata N2 reconstruida con el kernel del CI; esperando la autorización roja (2026-11-14)
- **Hecho:** push de `herolte-drop-v2` al remoto `mio` (D-0030), CI `xnu` run `43579309448` = success, `ci_check` por nombre completo: los 6 parches 0332..0337 APLICADOS, ninguno propio saltado (E-0037). Kernel `62ea7501…2d5b`. Candidata nueva **`xnu-boot-v2-s7-20261114.img`** (SHA-256 `2c155829…8f40`): verificador 47 PASS/0 FAIL, independiente 51 PASS/0 FAIL (E-0038). Copias del teléfono verificadas (E-0036). T-0016 y T-0029 hechas.
- **Falta (Director):** autorizar `device-write-boot`; la solicitud completa, el procedimiento y la vuelta atrás están en `docs/herolte-solicitud-n2.md` (T-0012 sigue bloqueada hasta entonces). **Nada se ha escrito en el teléfono.** Sin L3/L4 de esta unidad.
- **En curso:** T-0028 (mutantes de rev3, segundo plano). **Esperas:** T-0004 (R2), T-0023 (aislamiento de HeroGPU: la GPU no debe usarse con software no confiable).
- **Aviso al próximo ingeniero:** no escribir al teléfono ni leer sus particiones sin la autorización del Director con imagen, hash y copias nombrados.

---

## Relevo anterior: H-0010 — T-0016 hecha; D-0029/D-0030 del Director; push y CI (2026-11-14)
- **Decisiones del Director (firmadas):** D-0029 (el NVMe NTFS vale como zona de trabajo para imágenes grandes; ext4 sigue preferido para repositorios y bucles), D-0030 (push de `herolte-drop-v2` SOLO al remoto `mio` = `darkcloud9998/ios-a5xelte`, lanzar el workflow `xnu` y descargar artefactos; sin push a `origin`, sin PR, sin force), D-0014 (renumeración) aprobada.
- **T-0016 hecha:** `0332-herolte-drop-marker-protocol` → `0336-…`, `0334-herolte-drop-v2` → `0337-…`; fusión local con `origin/herolte` (un conflicto de texto en `HEROLTE_PROGRESS.md`, ambas partes conservadas); la serie 0332..0337 aplica limpia en el orden final (E-0035; aplicabilidad, no compilación). `validate-repo.py`: 4 errores antiguos (KI-0001).
- **Antes de publicar** se escaneó el contenido (sin secretos, sin binarios de Apple, sin IMEI/serie; solo direcciones USB de prueba 192.168.7.x y rutas con el usuario local).
- **Siguiente:** push + CI + `ci_check.py` por nombre completo (`0337-herolte-drop-v2`) → kernel del CI → reconstruir la candidata BOOT con nombre nuevo, reverificar, archivar. T-0028 (mutantes rev3) sigue en curso en segundo plano.
- **Antes de pedir el flasheo al Director** (acción roja): candidata verificada en el PC, BOOT original con hash (E-0009) y copia TWRP de EFS fuera del teléfono (el EFS NO está en este repositorio: lo respalda el Director).

---

## Relevo anterior: H-0009 — el Director delega más autonomía (D-0028); T-0028 en curso (2026-11-14)
- **D-0028 (Director, sus palabras):** el ingeniero y la jefatura técnica son más autónomos; el Director lee todo e interviene de forma extraordinaria. Aplicación: `delete-archived` (nivel A) para borrar temporales YA archivados con hash verificado, por ruta exacta. **Sigue rojo/del Director:** el teléfono, reglas X y `AGENTS.md`, borrado general, publicar/CI en el repositorio público, R2 (D-0005), host-config-change. Las directivas de la jefatura son dirección técnica; una acción C solo la cubre una decisión del Director.
- **Hecho hoy:** T-0025 cerrada (E-0031/E-0032), T-0026 (D-0025), D-0027 ejecutado (E-0033: 6,2 → 29,5 GiB libres; la imagen y `r3/work` siguen en NTFS), T-0019 (E-0034: imagen anterior archivada, sha256 = E-0010).
- **En curso: T-0028** (ronda completa de 49 mutantes sobre rev3, guardia de disco). Ver `resume` de la tarea.
- **Esperas:** T-0004 (R2: D-0005), T-0016/T-0023 (arquitectura). El S7 sigue sin tocarse; sin L3/L4 de esta unidad.
- Contraseña de sudo: el ingeniero no la tiene; los comandos con sudo los ejecuta el Director.

---

## Relevo anterior: H-0008 — T-0025 cerrada; sudo/montaje/compilación pesada/imágenes de prueba son VERDES (D-0025), 2026-11-14
- **T-0025 hecha:** verify real del Director: `ROOT_HFSPLUS_LAB_VALID_CANDIDATE` (`lab-full-xnu.img.valid`), sha256 `747d0245…ec27f` idéntico antes, después y en la copia de NTFS (E-0031; salidas en E-0032). Contiene binarios de Apple: no va a git. **No se ha arrancado en ningún sitio** (nivel L2, sin L3/L4). Faltan los 2 ficheros `U+0E33` (KI-0006); los 195 `NAME-NORMALIZED` son avisos (KI-0007).
- **D-0025 (Director, 2026-11-14):** `privileged-or-mount` y la nueva `heavy-compile` pasan a nivel A; D-0022 y D-0021 quedan sustituidas. **No** cambia: borrar/mover datos, publicar/CI, todo lo del teléfono (siguen rojos), ni **R2** (D-0005: sigue sin autorizar; hay que pedir al Director que lo diga expresamente). El ingeniero **no tiene sudo** (pide contraseña): ejecuta el Director los comandos con sudo, o la sesión debe disponer de él. Las guardas de `img_common.sh`/`guard.py` no se relajan.
- **T-0026 hecha** (como D-0025, no como "tres niveles nuevos": la estructura A/B/C/X ya son los tres colores).
- **Siguiente (verde): T-0028** (ronda completa de 49 mutantes sobre rev3, con guardia de disco). Otras esperas: T-0004 (R2), T-0019 (archivar `lab-full.img.partial` anterior; el nuevo ya está), T-0016/T-0023 (arquitectura).
- Scratchpad volátil: la imagen nueva ya está en NTFS; `r3/work` (renombrado) y los logs también deberían archivarse si se vuelven a necesitar.

---

## Relevo anterior: H-0007 — T-0025 con verify real analizado; T-0027 cerrada; T-0026 en espera (2026-11-14)
- **T-0025:** populate y primer verify REALES hechos por el Director (E-0029). Catálogo en bruto: 327/327 nombres en forma XNU exacta; los 195 `NAME-NORMALIZED` son avisos (Linux recompone al leer, KI-0007); el fallo real eran 2 EXTRA: `.journal` y `.journal_info_block` (omisión mía del punto 5, corregida en `tools/ios-root-lab/verify_image.sh`). **Falta que el Director repita `sudo bash <carpeta-imagenes>/xnu_sudo_run.sh verify`** (montaje de solo lectura); si pasa, la imagen se renombra a `.valid`. Ver `docs/herolte-unicode-imagen.md` §5. Después: archivar la imagen (12 GB, volátil en /tmp) y cerrar T-0025.
- **T-0027 hecha (E-0030):** el hueco R07 era del stub de losetup (el retraso de udev nunca arrancaba), no de `r2_lib.sh`; rev3 lo corrige (rev2 intacto).
- **T-0026 en espera:** la petición del 2026-11-14 (sudo/montaje/imágenes = VERDE, 3 niveles) contradice D-0022 (NARANJA) y quita controles al Director: necesita su confirmación con sus palabras.
- **Siguiente (verde): T-0028** (ronda completa de 49 mutantes sobre rev3, con guardia de disco).
- Otras esperas: T-0004 (R2, sin autorización), T-0019 (archivar lab-full), T-0023/T-0016 (decisiones de arquitectura).

---

## Relevo anterior: H-0006 — T-0025 lista salvo los 2 sudo (2026-11-13)
- **Hecho:** T-0007 (E-0026), T-0005 (E-0027: 46/49 detectados; R07 abierto → T-0027), D-0020 (excluir los 2 `U+0E33`, KI-0006), D-0021 (autorización roja `privileged-or-mount`, un solo uso), D-0022 (nivel NARANJA: **solo registrado; implementarlo es T-0026**), D-0023, D-0024, `tools/ios-root-lab/` (copia con adaptador, 17 pruebas), staging restaurado y renombrado, imagen nueva vacía `lab-full-xnu.img.partial`. Ver `docs/herolte-unicode-imagen.md`.
- **Pendiente de una persona:** ejecutar `COMANDOS_SUDO_XNU.md` (populate y verify). El ingeniero no tiene sudo. Después: leer `ver.full-xnu.*` en `r3/out`, archivar, registrar evidencia y cerrar T-0025.
- **Siguiente (verde):** T-0026 (política NARANJA), T-0027 (R07), `python3 tools/governance.py next`.
- **Cuidado:** el scratchpad de /tmp es volátil: `r3/work`, la imagen nueva y sus logs deben archivarse en NTFS tras la verificación.

---

## Relevo anterior: H-0005 — el Director aprueba el gobierno; Unicode: herramienta lista, imagen pendiente (2026-11-13)
- **Decisiones del Director (sus palabras en `approval_ref`):** D-0001 (gobierno) y D-0017 (Unicode) **APPROVED**; D-0018 levanta la congelación del generador (D-0006 sustituida) solo para esto; **D-0019**: la jefatura técnica (Qwen) decide lo técnico en su nombre. **No** autoriza por sí sola acciones rojas ni toca reglas X: el S7 sigue prohibido hasta una autorización roja explícita.
- **Hecho:** T-0013 (cargador clang, D-0016), T-0003, T-0010 (`S7GE_HARDWARE.md`: tablas de página de AS0 escribibles desde un job, por lectura de código), T-0011 (`S7GE_LICENCIAS.md`), T-0022, T-0024 (`xnu_names_stage.py`; 30 de 32 nombres se arreglan solo renombrando, 2 con U+0E33 necesitan `nodecompose`).
- **En curso:** T-0005 (mutación rev2 ronda 2, en segundo plano en el scratchpad; guardia de disco 3 GiB; salida `t0005_ronda2b_out.txt`). Si el proceso ya no existe, ver `mutation_summary3-*` más reciente y registrar el resultado.
- **Bloqueado a la espera de una autorización roja:** T-0025 (imagen nueva; monta HFS+), T-0004 (R2).
- **Siguiente (verde):** `python3 tools/governance.py next`.

---

## Relevo anterior: H-0004 — T-0008 cerrada (ABI real de `HeroGPU`), 2026-11-13
**Rama `herolte-drop-v2`**, worktree `~/HackiOS/repos/wardevsa-ios-a5xelte-v2`, sin push; árbol principal del responsable intacto.
- **Hecho:** T-0008 → `done`. `docs/S7GE_ABI.md`: los 8 selectores de `HeroGPU`, qué valida el kernel y qué no, y la brecha frente a S7GE. **Hallazgos graves (nivel de código leído, no probados en hardware):** una sola address space **AS0 compartida por todos los clientes**; `Submit` acepta la VA de la cadena de jobs **sin validarla**; `SurfaceBO` busca por id **globalmente**; **ningún entitlement** ni presupuesto de memoria; handles `índice+1` reutilizables. Lo bueno: se desmapea de la GPU antes de liberar; los jobs están serializados; la memoria se pone a cero; no se exponen MMIO ni direcciones físicas.
- **Propuesta (no aplicada):** **D-0015** y la tarea bloqueada **T-0023** (aislamiento de clientes). Antes, T-0010: auditar qué mapea AS0.
- **Evidencia de la herramienta de gobierno:** batería final de mutantes **E-0025** (control sin mutar pasa; 22/22 detectados) sobre las 97 pruebas definitivas.
- **Siguiente (verde):** `python3 tools/governance.py next` → **T-0022** (`ci_check`: nombre completo del parche), después T-0010 y T-0011 (documentos), y T-0005 (ronda 2 de mutación de rev2).
- **Pasar al S7:** ver el informe a la dirección; sigue sin tocarse el teléfono.

---

## Relevo anterior: H-0003 — T-0009 cerrada (integración con `origin/herolte`), 2026-11-13
**De:** ingeniero principal. **Estado:** trabajo en rama **`herolte-drop-v2`** (worktree `~/HackiOS/repos/wardevsa-ios-a5xelte-v2`), sin push; el árbol principal del responsable no se ha tocado (sus 28 ficheros sin confirmar conservan su SHA-256).
- **Hecho:** T-0009 → `done`. Informe `docs/herolte-integracion-origin-herolte.md`; resultados archivados (E-0024). **Conclusión:** los contenidos **no** chocan (un único conflicto de texto en `HEROLTE_PROGRESS.md`, resoluble conservando ambas secciones); los 5 parches de las dos series **aplican en ambos órdenes**; solo colisionan los números `0332` y `0334` (upstream no usa `0335`, de modo que D-0008 —que lo daba por colisión— queda `SUPERSEDED` por **D-0014**).
- **Hallazgo de riesgo silencioso:** `ci_check.py`/`preflight.py` identifican el parche por el prefijo `0334-`, que casa con nuestro DROP v2 **y** con `0334-present-wait-asleep` de upstream: puede dar un falso "aplicado". Nueva tarea **T-0022** (verde): exigir el nombre completo, con pruebas.
- **El repositorio es un clon parcial** (`blob:none`): una fusión local falla por blobs ausentes; el análisis se hizo en un clon temporal con la URL pública de `origin` como remoto *promisor* (solo lectura).
- **Siguiente (verde):** `python3 tools/governance.py next` → **T-0008** (ABI real de `HeroGPU`) y **T-0022** (`ci_check`), ambas sin autorización. Después T-0005 (ronda 2 de mutación de rev2).
- **Decisiones para la jefatura técnica:** D-0014 (renumerar solo 0332→0336 y 0334→0337 y exigir nombre completo en `ci_check`; reemplaza a D-0008), además de D-0001, D-0007, D-0009, D-0011, D-0012, D-0013.
- **Pasar al S7:** ver §"¿Hay que pasar al S7?" del informe a la dirección: las candidatas N1/N2 están verificadas en el PC; falta la decisión del cargador (T-0013) y una **autorización roja** del Director (T-0012). No se ha tocado el teléfono.

---

## Relevo anterior: H-0002 — Auditoría de `tools/governance.py` y mecanismos de continuidad, 2026-11-13
**De:** ingeniero principal (Claude). **Para:** jefe de dirección técnica (revisión independiente) y Director. **Estado:** T-0001 sigue `in_review`; la auditoría está hecha y corregida; **nada consolidado ni publicado**.

### 1. Repositorio, rama y Git
- Worktree del ingeniero `~/HackiOS/repos/wardevsa-ios-a5xelte-v2`, rama **`herolte-drop-v2`**. Commits locales de gobierno: `a7e9138` (implantación) y el commit siguiente (esta auditoría: `git log --oneline -3`). **Sin push.**
- **Árbol principal del responsable** (`…/wardevsa-ios-a5xelte`, `herolte-drop-fixes`, HEAD `8d1cf43`): sus **10 entradas sin confirmar (28 ficheros) tienen exactamente el mismo SHA-256 antes y después** de esta auditoría, y el estado Git es idéntico. No se limpiaron, restauraron, movieron ni sobrescribieron.
- Nota de honestidad: antes de esta misión ya había ejecutado `git status` en ese árbol (lectura); `git status` puede refrescar `.git/index` (hallazgo F-01). No cambia ningún fichero, pero es exactamente el efecto que la herramienta corregida evita.

### 2. Archivos creados o modificados en esta auditoría
- **Reescrito:** `tools/governance.py` (de 369 a ~600 líneas) · `tools/test_governance.py` (de 37 a **96 pruebas**).
- **Nuevos:** `tools/onboarding_drill.py`, `tools/test_onboarding.py` (6 pruebas), `tools/governance_mutation.py` (22 mutantes), `governance/AUDIT_GOVERNANCE_TOOL.md`, `governance/KNOWN_ISSUES.md`, `governance/ONBOARDING_DRILL.md`, `governance/data/policy.pin.toml`.
- **Modificados:** `governance/data/{policy,tasks,decisions,evidence,regression}.toml` (colores, `authorizes`, niveles de evidencia, deuda cuantificada, T-0020/T-0021, D-0011..D-0013, E-0021/E-0022), `README`, `CONSTITUTION` (I-23), `AUTHORITY`, `AUTONOMY_POLICY` (colores verde/amarillo/rojo y qué aplica la herramienta), `STATE`, `HANDOFF` y las vistas generadas.
- **No tocados:** `AGENTS.md` (salvo el puntero ya existente), kernel, parches, generador del root, `validate-repo.py`, imágenes y evidencias.

### 3. Auditoría de la herramienta (resumen; detalle en `AUDIT_GOVERNANCE_TOOL.md`)
17 hallazgos, todos corregidos y cubiertos por pruebas citadas por nombre. Los más graves: `status` podía escribir `.git/index`; `regress` ejecutaba cualquier comando; una acción desconocida contaba como verde (falla abierta); **cualquier decisión del director servía de autorización roja** (D-0002 habría "autorizado" borrar datos); una tarea amarilla podía pasar a `done` sin revisión; `next` ignoraba propietario, bloqueos y decisiones sin aprobar; las evidencias no distinguían estados ni niveles; una estructura de datos equivocada validaba una cola vacía en silencio (defecto encontrado por las propias pruebas).
**Qué aplica ahora:** rojo denegado salvo autorización registrada que **nombre la acción** y esté vigente; amarillo no se integra sin `review_ref`; falla cerrada; `check` y los demás comandos de lectura dejan el clon y `.git` **byte-idénticos**; `render` solo escribe 4 vistas, de forma atómica y sin pisar ficheros ajenos; `evidence` solo da por válido lo que coincide en hash y tamaño; niveles y dominios se **declaran** y nunca se elevan.

### 4. Pruebas ejecutadas y resultados (2026-11-13)
| Qué | Resultado |
|---|---|
| `python3 -W ignore tools/test_governance.py` | **96 OK** (permisos, operaciones prohibidas, integridad de evidencias, generación de vistas, recuperación ante errores, selección de tareas, solo lectura, independencia de rutas, coherencia documental) |
| `python3 -W ignore tools/test_onboarding.py` | **6 OK** (README literal en clon con `HOME` vacío; afirmaciones de STATE/HANDOFF frente al estado real; simulacro de reanudación; simulacro en frío) |
| `python3 tools/governance_mutation.py` | **control sin mutar: pasa; 22 mutantes, 22 detectados, 0 sobreviven** (E-0023; E-0021 es la pasada previa, sin control) |
| `python3 tools/governance.py check` | 0 errores; 2 avisos esperados (política sin ratificar; STATE un commit por detrás) |
| `python3 tools/governance.py evidence --all --strict` | **22 OK, 0 sin verificar**: hashes reales de los 22 ficheros, incluida la imagen de laboratorio de 20 GiB y los TAR |
| `validate-repo.py` | **XFAIL cuantificado: 5 errores, sin corregir** (KI-0001); la suite falla si aumentan |
| Regresión previa | verify-boot 22 · plutil 7 · tune-root 30 · stage-portable 20 · hfsplus-names 16 · DROP v2 36/36 · preflight 14/1/0 |
**Separación de niveles:** todo es host **L2** o compilación **L1**. No hay ninguna evidencia de hardware de esta unidad (L3/L4 `this-unit`); ninguna herramienta puede declararla.

### 5. Limitaciones y riesgos pendientes
1. **Disciplina asistida, no cortafuegos** (KI-0004): la herramienta informa; no impide que un agente ejecute un comando. Alinear los permisos de Claude Code es una acción roja (T-0021, D-0013).
2. La pantalla de `regress` es una red de seguridad, no un sandbox.
3. El pin de la política hace visible un cambio, no lo impide al mismo actor; la ratificación es humana (D-0001).
4. `STATE.md` envejece con cada commit (`check --strict` lo exige al día).
5. La parte 2 de la prueba de incorporación (modelo en frío) **no se ha ejecutado**: la demostración completa del criterio de finalización queda pendiente de T-0020.
6. Siguen abiertos KI-0002 (colisión de numeración con `origin/herolte`), KI-0003 (evidencia volátil: `lab-full` solo en `/tmp`) y KI-0005 (baterías rev2 incompletas).

### 6. Instrucciones exactas para retomar el trabajo
```
cd ~/HackiOS/repos/wardevsa-ios-a5xelte-v2          # worktree del ingeniero (NO el árbol principal)
git branch --show-current                              # herolte-drop-v2
python3 tools/governance.py check                      # 0 errores
python3 tools/governance.py status                     # rama, HEAD, cola, bloqueos
python3 tools/governance.py next                       # siguiente: T-0009 (informe de integración con origin/herolte), verde
python3 tools/governance.py evidence                   # hashes de las evidencias presentes
python3 -W ignore tools/test_governance.py && python3 -W ignore tools/test_onboarding.py
```
Después: marcar T-0009 `in_progress` en `governance/data/tasks.toml`, `python3 tools/governance.py render`, escribir el primer checkpoint y trabajar. Antes de cualquier acción dudosa: `python3 tools/governance.py can <acción>` / `gate <acción> --task T-NNNN`.

### 7. Decisiones que necesitan la revisión de la jefatura técnica
- **D-0001** (el gobierno completo y el cambio en `AGENTS.md`), **D-0011** (mecanismo `authorizes`/`review_ref`), **D-0012** (niveles de evidencia declarados, sin elevación automática) y **D-0013** (alinear los permisos de Claude Code).
- Ya pendientes: D-0007, D-0008, D-0009 y las decisiones del Director de T-0003, T-0013, T-0014.
- Pedir al jefe técnico o al Director que ejecute la parte 2 de `ONBOARDING_DRILL.md` con un modelo en frío (T-0020).

### 8. Siguiente misión recomendada
T-0009 (informe de integración con `origin/herolte`, verde), después T-0008 (ABI de HeroGPU) y T-0005 (ronda 2 de mutación de rev2).

---

## Relevo anterior: H-0001 — Misión 0 (implantación del gobierno), 2026-11-13
**De:** ingeniero principal (Claude). **Para:** jefe de dirección técnica (revisión independiente) y Director (ratificación). **Estado de la misión:** implantada y en revisión (`T-0001 in_review`); **no consolidada**.

### 1. Repositorio y rama
- Repositorio: `wardevsa-ios-a5xelte` (remotos `origin` = upstream `wardevsa/ios-a5xelte`, `mio` = fork del responsable).
- **Worktree del ingeniero:** `~/HackiOS/repos/wardevsa-ios-a5xelte-v2`, rama **`herolte-drop-v2`**. Elegido porque estaba limpio, contiene todo el trabajo reciente y no interfiere con los cambios sin confirmar del responsable.
- Árbol principal del responsable: `~/HackiOS/repos/wardevsa-ios-a5xelte`, rama `herolte-drop-fixes`, **10 ficheros sin confirmar, no tocados**.
- **Sin push.** `origin/herolte` avanzó y colisiona en numeración de parches (D-0008, T-0009): decidir la rama definitiva de gobierno es una de las decisiones pendientes.

### 2. Qué se creó o modificó
- `governance/`: `README`, `CONSTITUTION`, `AUTHORITY`, `AUTONOMY_POLICY`, `SECURITY_POLICY`, `ARCHITECTURE`, `ROADMAP`, `STATE`, `HANDOFF`, `checkpoints/`; datos `data/{policy,tasks,decisions,evidence,regression}.toml`; vistas generadas `TASKS`, `ACTIVE_TASK`, `DECISIONS`, `EVIDENCE`.
- `tools/governance.py` (validador, vistas, política, cola, evidencias, regresión) y `tools/test_governance.py`.
- `AGENTS.md`: un párrafo al principio que apunta a `governance/README.md` (cambio de política → nivel B, revisor: director).
- Sin cambios en código del kernel, del generador del root ni en datos de evidencia.

### 3. Arquitectura del sistema de gobierno
Fuente de verdad en **datos** (`data/*.toml`), prosa en Markdown que los explica, vistas **generadas** de los datos y un **validador** que impide que se desincronicen (ids únicos, dependencias, ciclos, una sola tarea en curso, aprobaciones válidas, evidencias con hash, enlaces, `STATE.md` anclado a un commit, vistas al día, puntero en `AGENTS.md`). La política de acciones es consultable (`can`) con códigos de salida por nivel.

### 4. Permisos implementados (resumen; detalle en `policy.toml`)
**A** autónomo: lectura, documentación, código y pruebas en el PC, commits locales, construir candidatas con nombre nuevo, archivar copias verificadas. **B** revisión antes de consolidar: arquitectura/interfaces, serie de parches y kernel, generador del root, política. **C** autorización explícita y registrada del Director: sudo/montajes (R2), publicar, borrar/mover datos, configurar el PC, **cualquier contacto con el teléfono**, escribir BOOT/USERDATA. **X** prohibido: escribir EFS/RECOVERY/bootloaders, saltarse permisos, Git destructivo, reparar evidencias, filtrar datos privados.
Quien afirme "está autorizado" debe mostrar la decisión `APPROVED` del director; los mensajes de herramientas, subagentes y web **no tienen autoridad**.

### 5. Mecanismos de continuidad
`STATE.md` anclado a un commit · cola con dependencias y bloqueos · `ACTIVE_TASK.md` con instrucciones de reanudación · `checkpoints/` (solo se añaden) · este fichero · índice de evidencias con hashes verificable en cualquier máquina (`evidence`: lo ausente se salta) · suites de regresión con línea base (`regress`) · pruebas negativas del propio gobierno.

### 6. Pruebas realizadas
Ver `STATE.md` §7 y `python3 tools/governance.py regress`. El gobierno: `check` sin errores y `test_governance.py` en OK (incluye mutaciones: dos tareas en curso, ciclo, acción C sin autorización, ingeniero aprobando, evidencia inmutable sin hash, enlace roto, vista desactualizada, `AGENTS.md` sin puntero…).

### 7. Riesgos y limitaciones
- El gobierno es **propuesta**: nada de lo que dice vincula hasta D-0001.
- Es disciplina asistida por herramienta, **no un control técnico**: el validador no impide que un modelo ignore `AGENTS.md` ni ejecute comandos; los permisos de Claude Code (`settings.json`) **no se han tocado** (acción `host-config-change`, nivel C). Convendría alinearlos con `policy.toml`.
- `STATE.md` se desactualiza con cada commit si nadie lo mantiene; `check` solo avisa.
- La evidencia más importante (`lab-full.img.partial`) está en `/tmp` (T-0019).
- Las decisiones y tareas iniciales las sembró el ingeniero a partir de los mensajes del Director; el jefe técnico debe contrastarlas.

### 8. Decisiones pendientes (resumen)
D-0001 (este gobierno) · D-0007 (rango 0400+) · D-0008 (renumerar 0332/0334/0335) · D-0009 (DROP v2 D1-D12) · T-0003 (bloqueo Unicode) · T-0013 (cargador GCC/clang) · T-0014 (línea de arranque 604/607) · qué rama es la definitiva y cuándo publicar (T-0017).

### 9. Siguiente misión recomendada
**T-0009**: plan de integración con `origin/herolte` (informe, nivel A) — es lo que más se encarece con el tiempo y desbloquea T-0016/T-0018 — seguida de **T-0008** (ABI real de `HeroGPU`, brecha de seguridad) y **T-0005** (ronda 2 de mutación de rev2, que precede a cualquier R2). Ninguna requiere autorización.

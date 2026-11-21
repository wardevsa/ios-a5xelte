# ORCHESTRATOR.md: canal entre el orquestador (chat web) y el ejecutor (esta sesión)

Roles: orquestador = propone y revisa; ejecutor = repo, teléfono, CI; Director (Pioxi) = aprueba BOOT/USERDATA y arquitectura.
Niveles: 1 autónomo (leer, analizar, evidencias), 2 informar después (push a `mio`, DROP dentro de D-0123), 3 preguntar antes (BOOT,
USERDATA fuera de DROP, modificar parches).

Nota del ejecutor (2026-11-21): este archivo NO existía en el repositorio cuando llegó el briefing (no hay secciones I a IV escritas ni
subidas); lo creo yo con la sección V para que el canal exista. Las secciones I a IV son del orquestador.

## I a IV (del orquestador, pendientes de escribir/subir)

## V. Reportes del ejecutor

### V.1 Diagnóstico del cierre de Flappy Bird con min129 (2026-11-21, E-0381 y E-0382)

**Estado real de partida (corrige el briefing):** BOOT = min129 (BOOT 19 de 80); DROP = 49 de 80, no 48 (el 49 es una sonda de libheroapp para este
mismo caso); kernel de la rama `herolte-sync-upstream` = nuestra serie + 0487 (HeroGPU nombra el complemento), parches 0339-0345 de
upstream apartados (62 de los nuestros dejaban de aplicar, E-0379).

**1. Simbolización** (caché local de iOS 16.7.16, la del root; desliz del registro del kernel 0x30718000; el PC real que da el briefing,
0x1c2617198, sale bien):

| Dirección con desliz | Sin deslizar | Imagen +offset | Qué es |
|---|---|---|---|
| 0x1f2d2f198 (pc) | 0x1c2617198 | libsystem_kernel +0x7198 | `__pthread_kill` |
| 0x2022be5f8 (lr) | 0x1d1ba65f8 | libsystem_pthread +0xd5f8 | `pthread_kill` |
| 0x1be374868 | 0x18dc5c868 | libsystem_c +0x1c868 | `raise` |
| 0x10109e37c | (no está en la caché) | libheroapp | el manejador de cierres de libheroapp |
| 0x20221b2f4 | 0x1d1b032f4 | libsystem_platform +0x22f4 | `_sigtramp` |
| 0x21fcdd590 (x2) | 0x1ef5c5590 | **Jet +0x7590** | `jet_context_OpenGL::create_program(jet_function*, jet_function*)` |
| 0x200251dbc / 0x200253e94 | 0x1cfb39dbc / 0x1cfb3be94 | SpriteKit +0xaedbc / +0xb0e94 | |
| 0x2001eae8c / 0x2001eb3c0 / 0x2001efe94 | | SpriteKit +0x47e8c / +0x483c0 / +0x4ce94 | |

Lectura: **el PC del briefing NO es el punto de fallo.** Es el `raise` que hace nuestro propio manejador (libheroapp captura SIGSEGV, anota y
vuelve a lanzar la señal): `pthread_kill` <- `raise` <- manejador <- `_sigtramp`. La señal original, que libheroapp anotó en
`/private/var/tmp/heroapp-crash.txt`, es **SIGSEGV, dirección 0x0, en `__dynamic_cast` (libc++abi +0x14cb4), llamado desde Jet +0x7590**.

**2. Función en el PC:** Jet `jet_context_OpenGL::create_program`. Desensamblado (capstone, caché local): `create_function` (Jet +0x7474)
devuelve NULL cuando su texto fuente de sombreador es NULL (el ayudante de compilación, 0x1ef5bf198, lo comprueba y no llama a ninguna gl*);
`create_program` hace `dynamic_cast` de ese NULL.

**3. Clasificación de las tres hipótesis:**
- *Método no implementado en HeroMetal.bundle*: **descartada.** El complemento nunca se consulta en Flappy: en el registro del kernel de min129 los
  arranques de Flappy (pids 313, 314) no tienen ninguna línea `hero-metal` ni `hakiosmetal`, mientras que S7GELab tiene `bundle loaded`,
  `asks for a device`, `targetDeviceInfo`, `B2L fc: fragment function tri_fragment` y arranca `MTLCompilerService`. Tampoco hay en
  `heroapp.log` ninguna llamada de Flappy a `MTLCreateSystemDefaultDevice` (libheroapp las anota).
- *Shader que AIR no maneja*: **descartada** por lo mismo: no se compila ninguna función de Metal.
- *Entitlements*: **sin indicio.** El mismo complemento da dispositivo a S7GELab, que tiene los mismos (ninguno) entitlements de depuración; el
  filtro es `metal.allow` (contiene `Flappy Bird`, nombre igual al que ve libheroapp).

**Causa real:** SpriteKit elige su ruta OpenGL (Jet) **antes** de preguntar a Metal. **No se sabe por qué.** Pistas sin confirmar: cadenas de
SpriteKit `PrefersOpenGL`, `enableMetal`, `MetalCompatibility`, `OpenGLESCompatibility`, `globalMetalDevice`; el Info.plist de Flappy
(org.brandonplank.flappybird) no tiene `PrefersOpenGL`. No encontré las referencias de código con ADRP/ADD (las cadenas son CFString).

**4. Evidencias:** E-0381 (diagnóstico completo, ya escrita antes de este briefing) y E-0382 (esta simbolización).

**5. Decisión propuesta:** ninguna. El fix no es claro: sin causa, cualquier parche sería adivinar. (Nota: **D-0125 ya existe**, es la de mover las
apps de sistema preparadas; el siguiente número libre es D-0126.)

**6. Siguiente paso (Nivel 2, ya hecho):** DROP 49 de 80: libheroapp anota en Flappy las claves de la elección y llama directamente a
`MTLCreateSystemDefaultDevice` (el de Metal, sin el desvío) para ver si el complemento acepta a ese proceso. Espera una apertura de Flappy.
No se ha escrito ningún parche del kernel en este diagnóstico. Preguntas para el orquestador: ¿conoce cómo decide SpriteKit de iOS 16 entre Metal
y OpenGL (el trabajo de Scion/ios-b1lte hizo funcionar SpriteKit sobre este complemento)?

### V.2 Resultado parcial de la sonda del DROP 49 (E-0383)

Respuestas al orquestador (3 aperturas de Flappy):
1. **¿MTLCreateSystemDefaultDevice() da nil o dispositivo?** `nil`, pero llamado desde el CONSTRUCTOR de libheroapp y sin ninguna línea `hero-metal` del
   complemento: no concluyente (Metal quizá no está listo en un constructor). Repetido más tarde en el DROP 50.
2. **¿Qué comprobación de Jet lo rechaza?** Sin respuesta: no hay evidencia de que SpriteKit llame a `MTLCreateSystemDefaultDevice` (libheroapp no anota
   ninguna llamada de Flappy por el desvío) ni de que llegue a mirar feature sets. Tu hipótesis encaja, pero no está medida.
3. **¿Clave de Info.plist o default?** Ninguna: las seis claves (PrefersOpenGL, enableMetal, MetalCompatibility, OpenGLESCompatibility, SKPrefersOpenGL,
   SKEnableMetal) valen `(none)` en defaults y en Info.plist.

Causa raíz NO confirmada; no propongo D-0126. Siguiente: DROP 50 (la misma petición cuando UIKit anuncia el lanzamiento). Tu observación sobre
`hakios-gl` devolviendo NULL donde Jet espera un objeto: lo que sé es que `create_function` (Jet +0x7474) devuelve NULL por texto de sombreador NULO, sin
llamar a gl*; ese texto no viene de hakios-gl (que es el puente de backboardd, no el de apps; las apps cargan libheroeagl-app).

### V.3 Causa raíz de que Flappy no reciba dispositivo (E-0384)

Matiz primero: tu mensaje dice «E-0383 confirmada: nil para Flappy»; no lo estaba: E-0383 solo mostraba que ninguna clave fuerza OpenGL y que una
llamada hecha desde el constructor daba nil sin línea del complemento. La confirmación llega ahora, por el código, no por la sonda.

1. `metal.allow` en el teléfono: `S7GELab` y `Flappy Bird`, una por línea (cat -A: `Flappy Bird$`).
2. HeroMetal compara `getprogname()` (nombre de ejecutable; no bundle ID ni nombre visible ni ruta). El Mach-O es `Flappy Bird`, con espacio.
3. **El fallo:** `allowed()` cortaba la línea en el primer espacio o tabulador (`strcspn(line, "\r\n \t#")`), de modo que `Flappy Bird` quedaba en `Flappy` y
   nunca coincidía. HeroMetal rechaza en silencio (sus líneas de registro solo salen para procesos permitidos), SpriteKit recibe nil y cae a OpenGL/Jet.
4. **Corrección de mi E-0381:** no puedo afirmar que Flappy «nunca consulta a Metal»; la ausencia de líneas `hero-metal` se explica por el filtro. Tu
   hipótesis (SpriteKit pide dispositivo, recibe nil, cae a OpenGL) es la que encaja.
5. **Arreglo:** no era corregir `metal.allow` (el fichero estaba bien: ningún nombre con espacio puede escribirse de forma que esa versión lo acepte),
   sino `gpu/metal/hero-metal-plugin.m`: la línea acaba en `#` o fin de línea y solo se quitan blancos finales. CI de userland verde; DROP 51 de 80:
   `metal/HeroMetal` y `metal/Info.plist`; hero-run los instala al arrancar. Es un cambio en código de userland, no un parche del kernel (Nivel 2).
   Pido a Pioxi: arrancar y abrir Flappy una vez. Esperado en el registro: `hero-metal: bundle loaded in Flappy Bird` y `asks for a device`.
   No propongo D-0126 todavía: el arreglo está dentro de D-0123 (DROP); si funciona basta con la evidencia.

### V.4 El arreglo de V.3 no se había instalado (E-0385)

Tras arrancar con el HeroMetal corregido en la zona de drop: `hero-run: Metal plug-in: drop zone 86304 bytes, Extensions 86304 bytes`, sin línea `put`;
sin líneas `hero-metal` de Flappy; Flappy se cierra igual. Causa mía: el `install_metal_plugin` de upstream solo instala si el tamaño difiere o la zona de drop
es más nueva; mi arreglo no cambia el tamaño y el instalado era más reciente. Arreglo: comparar bytes (DROP 52, `autorun` nuevo; Nivel 2). Un primer intento de
edición cayó por error en `install_audio_plugin` y rompió la compilación; lo detectó la CI y lo rehice en la función correcta. Pendiente: otro arranque y
abrir Flappy una vez. Sugerencia para el orquestador, si ve de nuevo ese código de upstream: su criterio de «instalar» (tamaño y hora) falla con cualquier
cambio que no varíe el tamaño; conviene decírselo a quien mantiene ese repositorio.

### V.5 Cambio de frente: Flappy aparcado y estado real de funciones (E-0386)

**T-0070 (Flappy Bird / SpriteKit): BLOQUEADA** hasta tener causa raíz confirmada con evidencia. Sin más DROP en ello. Estado: HeroMetal recortaba los nombres con espacio
(E-0384, confirmado por el código) y `hero-run` no reinstalaba el complemento (E-0385); falta ver un arranque con ambos arreglos; no lo pido.

**Una premisa del briefing que no se cumple:** «verificar qué más funciona del merge upstream (cámara, BT, haptics) en min129 sin tocar BOOT». Esas tres funciones
viven en los parches de kernel 0339-0345 de upstream, que **no están en min129** (los aparté en E-0379 porque con ellos 62 de nuestros parches dejan de aplicar). Del merge
solo hay en min129: la pila de Metal (con 0487), el `hero-run` fusionado y las librerías de userland (incluida `libnotefecam`, sin kernel que la sirva). En el registro:
Bluetooth, cámara y vibración no dan ninguna señal. No es un fallo: no se pueden verificar sin BOOT.

**Estado real (E-0386), resumen:**

| Área | Estado en min129 | Evidencia |
|---|---|---|
| Wi-Fi (enlace) | Funciona | conecta en 1937 ms, -46 dBm; 2462 tramas enviadas / 1892 recibidas |
| Red de las apps (Safari) | No funciona | 32 `connectx() failed necp_set_socket_domain_attributes`; sandbox niega a mDNSResponder/nsurlsessiond/trustd |
| Audio | Funciona | 24000 tramas, 0 perdidas |
| Táctil | Funciona | 4179 movimientos, 0 lecturas perdidas |
| Batería, térmica | Funcionan | 92 %, SoC 33-34 C |
| Pantalla | Funciona, ritmo variable | 27,8 fps (otro tramo 6,5); VGR0 de upstream apagado (`herovgr=0`) |
| OpenGL ES de apps | Funciona | triángulo en S7GE Lab (E-0359) |
| **Metal real (HeroMetal+AIR)** | **Funciona en S7GE Lab** | dispositivo `Mali-T880 (Panfrost) (Hakios)`, 683 cuadros de franja, MSL compilado por el compilador del teléfono |
| SpriteKit (Flappy) | No funciona, aparcado | T-0070 |
| Bluetooth, cámara frontal, vibración | No están en min129 | requieren 0339-0345 en el kernel |
| Memoria | Ajustada | 122 MB libres a los 600 s de uso |
| Vídeo, YouTube, cámara trasera, módem | No existen | sin motor de decodificación |

**Siguiente hito medible que no depende de Flappy (propuesta, en orden):**

1. **H1: Metal medido, sin BOOT ni parches** (Nivel 2, solo la app de S7GE Lab y DROP). Un banco dentro de S7GE Lab con el Metal real: (a) limpiar la pantalla, (b) un
   triángulo, (c) 48 triángulos superpuestos, (d) un cuadrado con textura y muestreador, (e) un `compute` que suma dos vectores y se comprueba. Resultado: fotogramas por
   segundo, milisegundos por envío y suma de comprobación correcta o no, frente a las mismas pruebas por OpenGL ES. Criterio de éxito: las cinco pasan con resultado correcto y
   se publica la tabla. Aclara también cuánto cuesta el envío síncrono de Metal (hoy GL baja de 119 a 30-44 fps cuando Metal corre a la vez).
2. **H2: red de Safari** (necesita BOOT, Nivel 3: toca kernel). Causa conocida, sin arreglar: `necp_set_socket_domain_attributes` y la denegación del sandbox. Criterio: Safari
   carga una página sencilla por Wi-Fi.
3. **H3: Bluetooth, cámara frontal y vibración** (BOOT y fusión hunk a hunk de 0339-0345, Nivel 3). Criterio: BT lista un dispositivo, la cámara entrega N cuadros, el motor vibra.

Recomiendo H1 ahora (no cuesta BOOT y fija la base de Metal con números), luego H2 por valor de uso, y H3 como proyecto aparte. Espero la decisión de Pioxi.

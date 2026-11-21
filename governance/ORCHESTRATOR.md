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

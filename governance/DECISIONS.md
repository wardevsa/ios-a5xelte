<!-- GENERADO por tools/governance.py render desde governance/data/*.toml. NO EDITAR A MANO: se pierde en el siguiente render. -->

# Registro de decisiones

Estados: `PROPOSED` (propuesta, **sin efecto**), `APPROVED` (aprobada por quien tiene autoridad para ese ámbito, con referencia), `REJECTED`, `SUPERSEDED`. Una propuesta del ingeniero **no es una decisión aprobada**. Una decisión autoriza una acción roja solo si la lista en `authorizes` (y está vigente).

| ID | Estado | Ámbito | Fecha | Título | Propone | Aprueba | Autoriza | Referencia |
|---|---|---|---|---|---|---|---|---|
| D-0001 | APPROVED | process | 2026-11-13 | Sistema de gobierno de ingeniería autónoma (carpeta governance/, herramienta tools/governance.py) | ingeniero | director | — | Mensaje del Director, 2026-11-13: 'Apruebo D-0001 y D-0017, autorizo cambiar el generador sin R2. Y si, la directiva responde por mi, por razones de seguridad yo seguire leyendo todo para que no haya problemas e intervendre de forma extraordinaria si se requiere.' |
| D-0002 | SUPERSEDED | policy | 2026-11-13 | Política de almacenamiento: ext4 para trabajo activo, NTFS para archivo histórico; NTFS nunca como scratchpad de Claude | ingeniero | director | — | Mensaje del Director 'Recuperar espacio real y completar la organización' (apartado 4, configuración permanente), 2026-11-13; documento IOS-S7-archive/05-manifests-and-hashes/POLITICA_ALMACENAMIENTO.md |
| D-0003 | APPROVED | architecture | 2026-11-13 | Dirección de S7GE: Metal como interfaz principal, IR común S7GIR, backend Midgard específico T880, OpenGL ES como API adicional, GPU física como ruta objetivo | jefe-tecnico | jefe-tecnico | — | S7GE_ARCHITECTURE.md Parte XXII 'Decisiones oficiales de dirección' (el jefe técnico define la arquitectura); el Director lo recibió y ordenó conservarlo para el proyecto el 2026-11-13. No es una autorización de ninguna acción de nivel C |
| D-0004 | APPROVED | process | 2026-11-13 | Criterios de la candidata N2 de solo lectura: sin ufsrw/rootrw distintos de =0, con ufsrw=0 herolog=0 herodrop=0 explícitos, verificada con herolte-verify-boot.py --profile n2-readonly | ingeniero | director | — | Mensaje del Director 'cerrar correctamente el verificador BOOT y producir una candidata N2 inequívocamente de solo lectura', 2026-11-13 |
| D-0005 | APPROVED | operation | 2026-11-13 | El experimento R2 (monta imágenes, usa sudo) no está autorizado | ingeniero | director | — | Restricciones reiteradas del Director en todos los mensajes de la serie T04-R2/Unicode: 'No ejecutes R2', 'No autorices R2', 'No monta imágenes' |
| D-0006 | SUPERSEDED | operation | 2026-11-13 | Generación del root: no cambiar el generador ni regenerar lab-full.img.partial hasta decidir sobre el bloqueo Unicode | ingeniero | director | — | Mensajes del Director 'Espera mi decisión antes de implementar cambios que afecten a la generación del root filesystem' y 'No repares, regeneres ni sustituyas esa imagen todavía', 2026-11-13 |
| D-0007 | PROPOSED | architecture | 2026-11-13 | Reservar el rango de parches 0400+ para S7GE (el 0300-0309 propuesto en S7GE_ARCHITECTURE.md ya está ocupado) | ingeniero | — | — | — |
| D-0008 | SUPERSEDED | architecture | 2026-11-13 | Renumerar nuestros 0332 (marcador DROP), 0334 (DROP v2) y 0335 (splash) antes de fusionar con origin/herolte, que ya usa 0332-0334 para gráficos | ingeniero | — | — | — |
| D-0009 | PROPOSED | architecture | 2026-11-13 | Ratificar las decisiones D1-D12 de DROP v2 de xnu/drop-v2/DECISIONES.md, tomadas por el jefe de proyecto suplente | ingeniero | — | — | — |
| D-0010 | APPROVED | operation | 2026-11-13 | Escribir en BOOT del S7 (peldaños N1/N2) requiere una autorización C específica; la candidata verificada del PC no la sustituye | ingeniero | director | — | Mensaje del Director 'Todavía NO hemos comenzado las pruebas reales en el Galaxy S7... No confundas imágenes generadas con un arranque real', 2026-11-13; AGENTS.md (solo BOOT) |
| D-0011 | PROPOSED | process | 2026-11-13 | Mecanismo de autorización roja y de revisión amarilla: authorizes + valid_until + gate; review_ref antes de pasar a done | ingeniero | — | — | — |
| D-0012 | PROPOSED | process | 2026-11-13 | Los niveles de evidencia (domain, level, device) se declaran y nunca se elevan automáticamente; una suite del PC no puede declarar hardware | ingeniero | — | — | — |
| D-0013 | PROPOSED | policy | 2026-11-13 | Alinear los permisos de Claude Code (settings.json) con policy.toml para convertir la disciplina asistida en un control técnico | ingeniero | — | — | — |
| D-0014 | APPROVED | architecture | 2026-11-13 | Renumerar solo los dos parches nuestros que colisionan con origin/herolte (0332 marcador -> 0336, 0334 DROP v2 -> 0337, manteniendo el orden relativo) y hacer que ci_check/preflight identifiquen el parche por nombre completo | ingeniero | director | — | Mensaje del Director (pioxi), 2026-11-14: 'Por parte del director, apruebo y firmo lo siguiente: [directiva de jefatura técnica: D-0029 NVMe como zona de trabajo, D-0030 push y CI, fusión T-0016 con renumeración 0332->0336 y 0334->0337, reconstrucción de la candidata y verificación de copias de seguridad]. Firmado Pioxi' (la directiva ordena exactamente esta renumeración) |
| D-0015 | PROPOSED | architecture | 2026-11-13 | Aislamiento de clientes de HeroGPU: address space por cliente, jc_va validada contra los BO del cliente, entitlement en initWithTask, presupuesto de memoria y SurfaceBO con comprobación de propiedad | ingeniero | — | — | — |
| D-0016 | APPROVED | architecture | 2026-11-13 | Cargador de las pruebas: usar el compilado con clang (loader-clang/, E-0008); no ejecutar el GCC descargado | ingeniero | jefe-tecnico | — | Directiva de jefatura técnica del 2026-11-13 (Qwen, relayada por el Director), apartado 'D-0013: Cargador para xnu_boot: clang'. La directiva la numeró D-0013, que ya existe (permisos de Claude Code): registrada aquí como D-0016. No autoriza ninguna acción de nivel C |
| D-0017 | APPROVED | architecture | 2026-11-13 | Corrección Unicode: regenerar en el generador del root los nombres en forma XNU (sin tocar el kernel), antes de repetir R2 | jefe-tecnico | director | — | Mensaje del Director, 2026-11-13: 'Apruebo D-0001 y D-0017, autorizo cambiar el generador sin R2. Y si, la directiva responde por mi, por razones de seguridad yo seguire leyendo todo para que no haya problemas e intervendre de forma extraordinaria si se requiere.' |
| D-0018 | APPROVED | operation | 2026-11-13 | Levantar la congelación del generador del root (D-0006) solo para aplicar D-0017: imagen NUEVA con nombre nuevo, sin R2 previo y sin tocar la anterior | ingeniero | director | — | Mensaje del Director, 2026-11-13: 'Apruebo D-0001 y D-0017, autorizo cambiar el generador sin R2. Y si, la directiva responde por mi, por razones de seguridad yo seguire leyendo todo para que no haya problemas e intervendre de forma extraordinaria si se requiere.' |
| D-0019 | APPROVED | process | 2026-11-13 | Delegación: la jefatura técnica (Qwen) decide lo técnico en nombre del Director; el Director lee todo e interviene de forma extraordinaria | director | director | — | Mensaje del Director, 2026-11-13: 'Apruebo D-0001 y D-0017, autorizo cambiar el generador sin R2. Y si, la directiva responde por mi, por razones de seguridad yo seguire leyendo todo para que no haya problemas e intervendre de forma extraordinaria si se requiere.' |
| D-0020 | APPROVED | architecture | 2026-11-13 | Excluir del root los 2 ficheros con U+0E33 (WorkflowKit th.lproj): sin nodecompose y sin parchear XNU | jefe-tecnico | director | — | Mensaje del Director, 2026-11-13: 'He aprobado el siguiente informe' (directiva de jefatura técnica: excluir del root los 2 nombres con U+0E33, sin nodecompose ni parche de XNU) |
| D-0021 | SUPERSEDED | operation | 2026-11-13 | Autorización roja de un solo uso: privileged-or-mount para generar la imagen NUEVA de T-0025 (perfil full-xnu) con los comandos del laboratorio | ingeniero | director | — | Mensaje del Director, 2026-11-13: 'Autorizo privileged-or-mount para generar la imagen nueva de T-0025 con los comandos de COMANDOS_SUDO.md, usándola con nombre nuevo y sin tocar la anterior' |
| D-0022 | SUPERSEDED | policy | 2026-11-13 | Reformulación de niveles: nuevo nivel NARANJA (la jefatura técnica puede autorizar operaciones privilegiadas de host) y ROJO CRÍTICO solo para el dispositivo físico | jefe-tecnico | director | — | Mensaje del Director (pioxi), 2026-11-13: 'Yo el director pioxi, autorizo el siguiente informe' (directiva de jefatura técnica: nivel NARANJA, autorización de T-0007, copia de scripts del laboratorio y continuación de T-0025) |
| D-0023 | APPROVED | operation | 2026-11-13 | Autorización roja de un solo uso: borrar de ext4 los 224 sandboxes ya archivados en NTFS (T-0007) | jefe-tecnico | director | delete-or-overwrite | Mensaje del Director (pioxi), 2026-11-13: 'Yo el director pioxi, autorizo el siguiente informe' (directiva de jefatura técnica: nivel NARANJA, autorización de T-0007, copia de scripts del laboratorio y continuación de T-0025) |
| D-0024 | APPROVED | architecture | 2026-11-13 | Copiar los scripts del laboratorio a tools/ios-root-lab/ con un adaptador de nombres XNU en un solo punto | jefe-tecnico | director | — | Mensaje del Director (pioxi), 2026-11-13: 'Yo el director pioxi, autorizo el siguiente informe' (directiva de jefatura técnica: nivel NARANJA, autorización de T-0007, copia de scripts del laboratorio y continuación de T-0025) |
| D-0025 | APPROVED | policy | 2026-11-14 | sudo en el host, montaje de imágenes, compilación pesada y generación de imágenes de prueba pasan a nivel VERDE (autónomo); sustituye a D-0022 | jefe-tecnico | director | — | Mensaje del Director (pioxi), 2026-11-14: 'Confirmo que sudo en host, montaje de imágenes, compilación pesada y generación de imágenes de prueba pasan al nivel VERDE. Esto contradice y sustituye a D-0022. El ingeniero puede ejecutar estas operaciones de forma autónoma sin solicitar autorización adicional.' |
| D-0027 | APPROVED | operation | 2026-11-14 | Borrar de /tmp dos artefactos ya archivados y con hash en NTFS (lab-full-xnu.img.valid y r3/work) para liberar ~24 GiB para T-0028 | jefe-tecnico | director | — | Mensaje del Director (pioxi), 2026-11-14: 'con el antiguo sistema estabamos perdiendo eficiencia y tiempo ... estoy leyendo tooodo, por si tengo que actuar extraordinariamente y cancelar, entonces la idea es que tu y el jefe tecnico seais mas autonomos, asi que modifica como veas, tienes mi autorizacion, la idea es agilizar el proceso. PIOXI DIRECTIVA' |
| D-0028 | APPROVED | policy | 2026-11-14 | Mayor autonomía del ingeniero y de la jefatura técnica para agilizar: borrar temporales ya archivados pasa a verde (delete-archived); el Director lee todo e interviene de forma extraordinaria | director | director | — | Mensaje del Director (pioxi), 2026-11-14: 'con el antiguo sistema estabamos perdiendo eficiencia y tiempo ... estoy leyendo tooodo, por si tengo que actuar extraordinariamente y cancelar, entonces la idea es que tu y el jefe tecnico seais mas autonomos, asi que modifica como veas, tienes mi autorizacion, la idea es agilizar el proceso. PIOXI DIRECTIVA' |
| D-0029 | APPROVED | policy | 2026-11-14 | Permitir el NVMe NTFS como zona de trabajo temporal para imágenes grandes y staging (sustituye a D-0002) | jefe-tecnico | director | — | Mensaje del Director (pioxi), 2026-11-14: 'Por parte del director, apruebo y firmo lo siguiente: [directiva de jefatura técnica: D-0029 NVMe como zona de trabajo, D-0030 push y CI, fusión T-0016 con renumeración 0332->0336 y 0334->0337, reconstrucción de la candidata y verificación de copias de seguridad]. Firmado Pioxi' |
| D-0030 | APPROVED | operation | 2026-11-14 | Autorizar push de la rama herolte-drop-v2 al fork darkcloud9998/ios-a5xelte, lanzar el CI xnu y descargar sus artefactos, para fusionar los parches de upstream y reconstruir la candidata BOOT | jefe-tecnico | director | publish | Mensaje del Director (pioxi), 2026-11-14: 'Por parte del director, apruebo y firmo lo siguiente: [directiva de jefatura técnica: D-0029 NVMe como zona de trabajo, D-0030 push y CI, fusión T-0016 con renumeración 0332->0336 y 0334->0337, reconstrucción de la candidata y verificación de copias de seguridad]. Firmado Pioxi' |
| D-0031 | APPROVED | architecture | 2026-11-14 | OSMesa: mantenerlo nosotros (Opción B) en lugar de quedarse en Mesa 25.0.7 o migrar ya a otra superficie; política en docs/S7GE_OSMESA_FORK_POLICY.md | jefe-tecnico | jefe-tecnico | — | Decisión de jefatura técnica del 2026-11-14 (Qwen), ratificada como AMARILLO; la propia decisión dice 'no implementar el fork hasta que el Director confirme'. Delegación D-0019 (el Director lee todo e interviene si hace falta) |
| D-0032 | APPROVED | architecture | 2026-11-14 | El Director confirma la Opción B2 de OSMesa: mantener solo el frontend OSMesa (osmesa.c, ~1 286 líneas) sobre un Mesa más nuevo; refina y confirma D-0031 | jefe-tecnico | director | — | Mensaje del Director (pioxi), 2026-11-14: 'Autorizo B2, firmado Pioxi.' |
| D-0033 | APPROVED | operation | 2026-11-14 | Autorización roja de un solo intento: fase 1 del primer arranque N2 — escribir xnu-boot-v2-s7-min-20261114.img en la partición BOOT del S7 desde TWRP | ingeniero | director | device-write-boot, device-read | Mensaje del Director (PioXI), 2026-11-14: 'Autorizo la fase 1, firmado PioXI'. Se refiere a la fase 1 de docs/herolte-solicitud-n2.md (§0, §1, §7), leída por el ingeniero tal como la propone el documento |
| D-0034 | APPROVED | operation | 2026-11-14 | Autorización roja: segundo intento del primer arranque N2 — escribir xnu-boot-v2-s7-min2-20261114.img (variante mínima + vm_compression_limit=98304 vm_compressor=2) en la partición BOOT del S7 desde TWRP | ingeniero | director | device-write-boot, device-read | Mensaje del Director (PioXI), 2026-11-14: 'Autorizo min2, firmado PioXI'. Se refiere a la candidata xnu-boot-v2-s7-min2-20261114.img propuesta en docs/S7GE_FIRST_BOOT_ANALYSIS.md §6 y E-0045 (SHA-256 595316aae927b3e7c960301790fa34557e5a296073a29df62522b67050edae21), con el mismo alcance que la fase 1 (D-0033) |

## D-0001 — Sistema de gobierno de ingeniería autónoma (carpeta governance/, herramienta tools/governance.py)
- **Estado:** APPROVED (director, 2026-11-13)
- **Razón:** La Misión 0 pide una estructura permanente y verificable para continuar el proyecto entre sesiones y modelos. Se implanta como propuesta: ningún modelo debe darla por aprobada hasta que la revise el jefe técnico y la ratifique el director.
- **Consecuencias:** Si se aprueba, las reglas de AUTONOMY_POLICY.md y policy.toml pasan a vincular a cualquier ingeniero que trabaje en el repositorio. Si se rechaza, se retira la carpeta y el puntero de AGENTS.md.
- **Cómo se revierte:** git revert del commit de implantación; quitar el puntero a governance/ en AGENTS.md.

## D-0002 — Política de almacenamiento: ext4 para trabajo activo, NTFS para archivo histórico; NTFS nunca como scratchpad de Claude
- **Estado:** SUPERSEDED
- **Razón:** El disco raíz llegó a 0 bytes libres; ntfs3 no conserva propietarios, nlink ni modos que las pruebas necesitan.
- **Consecuencias:** Los scratchpads son efímeros (viven en /tmp): lo que importe se archiva en el NTFS con tar+compare+SHA-256 y se indexa en evidence.toml.
- **Cómo se revierte:** Nueva decisión que la sustituya.

## D-0003 — Dirección de S7GE: Metal como interfaz principal, IR común S7GIR, backend Midgard específico T880, OpenGL ES como API adicional, GPU física como ruta objetivo
- **Estado:** APPROVED (jefe-tecnico, 2026-11-13)
- **Razón:** Fijada por la dirección técnica como objetivo, no como implementación. El estado real del árbol (S7GE_STATUS.md) matiza el punto de partida: hoy acelera OpenGL ES vía EAGL/OSMesa/Panfrost y no existe proveedor de Metal.
- **Consecuencias:** Aprobada como DIRECCIÓN. No autoriza escribir registros de GPU ni sustituir la ruta de presentación existente (el propio documento lo excluye).
- **Cómo se revierte:** Nueva decisión de arquitectura que la sustituya.

## D-0004 — Criterios de la candidata N2 de solo lectura: sin ufsrw/rootrw distintos de =0, con ufsrw=0 herolog=0 herodrop=0 explícitos, verificada con herolte-verify-boot.py --profile n2-readonly
- **Estado:** APPROVED (director, 2026-11-13)
- **Razón:** En el driver UFS, writable = (ufsrw != 0): cualquier valor distinto de exactamente 0 habilita escrituras.
- **Consecuencias:** Construir la candidata NO autoriza escribirla en el teléfono: eso es la acción device-write-boot (nivel C).
- **Cómo se revierte:** Nueva decisión; el verificador y sus pruebas codifican la regla.

## D-0005 — El experimento R2 (monta imágenes, usa sudo) no está autorizado
- **Estado:** APPROVED (director, 2026-11-13)
- **Razón:** Falta validar el ejecutor rev2 (ronda 2 de mutación pendiente) y su revisión independiente nueva.
- **Consecuencias:** T-0004 queda bloqueada hasta una decisión APPROVED del director que la autorice, acotada a comandos concretos.
- **Cómo se revierte:** Una decisión posterior del director que autorice R2 y cite la lista exacta de comandos.

## D-0006 — Generación del root: no cambiar el generador ni regenerar lab-full.img.partial hasta decidir sobre el bloqueo Unicode
- **Estado:** SUPERSEDED
- **Razón:** Hay 32 nombres Unicode que Linux escribió distinto de XNU (docs/herolte-unicode-hfsplus.md); las opciones son la corrección 1-5, la alternativa (B) o la (C).
- **Consecuencias:** T-0003 es una decisión pendiente; hasta entonces el generador y la imagen de laboratorio no cambian.
- **Cómo se revierte:** Decisión del director que elija una de las opciones.

## D-0007 — Reservar el rango de parches 0400+ para S7GE (el 0300-0309 propuesto en S7GE_ARCHITECTURE.md ya está ocupado)
- **Estado:** PROPOSED
- **Razón:** 0300-0335 existen en el árbol (0301 audio, 0307 L3 de GPU, 0317 WebKit...). Reutilizar números rompe aplicabilidad y trazabilidad.
- **Consecuencias:** Los nombres de parche de S7GE empezarían en 0400. Requiere revisión del jefe técnico porque toca la numeración de la serie.
- **Cómo se revierte:** Renombrar los parches S7GE; no hay ninguno creado todavía.

## D-0008 — Renumerar nuestros 0332 (marcador DROP), 0334 (DROP v2) y 0335 (splash) antes de fusionar con origin/herolte, que ya usa 0332-0334 para gráficos
- **Estado:** SUPERSEDED
- **Razón:** origin/herolte (2026-11-13) tiene 0332-surface-wrap, 0333-gpu-wait-asleep y 0334-present-wait-asleep. Colisión de números con ramas distintas del mismo proyecto.
- **Consecuencias:** Cambia nombres de fichero, no contenido; el kernel de la candidata N2 (construido con nuestro 0334) no cambia, pero habría que reconstruirlo y reverificar la imagen si se rehace sobre la nueva serie.
- **Cómo se revierte:** Revertir el renombrado antes de publicar.

## D-0009 — Ratificar las decisiones D1-D12 de DROP v2 de xnu/drop-v2/DECISIONES.md, tomadas por el jefe de proyecto suplente
- **Estado:** PROPOSED
- **Razón:** Ese documento dice que sus decisiones están 'pendientes de ratificación por el responsable del proyecto'. El sistema de gobierno distingue propuesta de decisión aprobada.
- **Consecuencias:** Hasta la ratificación, DROP v2 se trata como propuesta madura, no como diseño aprobado.
- **Cómo se revierte:** Rechazar o sustituir las decisiones individuales.

## D-0010 — Escribir en BOOT del S7 (peldaños N1/N2) requiere una autorización C específica; la candidata verificada del PC no la sustituye
- **Estado:** APPROVED (director, 2026-11-13)
- **Razón:** Nada se ha probado en hardware: las candidatas pasan comprobaciones de consistencia del PC, no arrancan.
- **Consecuencias:** T-0012 queda bloqueada hasta que el director autorice la escritura de BOOT con imagen, hash y copias previas nombrados.
- **Cómo se revierte:** Decisión posterior del director que autorice la prueba.

## D-0011 — Mecanismo de autorización roja y de revisión amarilla: authorizes + valid_until + gate; review_ref antes de pasar a done
- **Estado:** PROPOSED
- **Razón:** La auditoría de tools/governance.py (F-09, F-10) encontró que cualquier decisión del director servía de autorización para cualquier acción roja y que una tarea amarilla podía pasar a done sin revisión. La corrección exige que la decisión nombre la acción, sea vigente y del director, y que lo amarillo tenga review_ref del revisor que fija la política.
- **Consecuencias:** Cambia cómo se registran las autorizaciones del Director (campo authorizes en decisions.toml) y las revisiones del jefe técnico (review_ref en tasks.toml). Ninguna herramienta ejecuta nada por ello.
- **Cómo se revierte:** Quitar los campos y las comprobaciones de tools/governance.py (git revert).

## D-0012 — Los niveles de evidencia (domain, level, device) se declaran y nunca se elevan automáticamente; una suite del PC no puede declarar hardware
- **Estado:** PROPOSED
- **Razón:** El director pidió separar pruebas del host, compilación, GPU física e integración iOS y prohibió elevar un nivel automáticamente (F-13). Se codifica en el esquema de evidence.toml y regression.toml y en check.
- **Consecuencias:** Toda evidencia nueva debe llevar dominio, nivel y dispositivo; una tarea puede exigir min_evidence (p. ej. L3 en this-unit para las pruebas en el S7).
- **Cómo se revierte:** Retirar los campos y las reglas de check.

## D-0013 — Alinear los permisos de Claude Code (settings.json) con policy.toml para convertir la disciplina asistida en un control técnico
- **Estado:** PROPOSED
- **Razón:** La herramienta informa pero no puede impedir que un agente ejecute un comando (KI-0004, límite 1 de la auditoría). Solo la configuración de permisos del propio agente lo impide.
- **Consecuencias:** Requiere cambiar la configuración del agente: acción roja host-config-change; no se ha tocado.
- **Cómo se revierte:** Restaurar el settings.json anterior (copia previa obligatoria).

## D-0014 — Renumerar solo los dos parches nuestros que colisionan con origin/herolte (0332 marcador -> 0336, 0334 DROP v2 -> 0337, manteniendo el orden relativo) y hacer que ci_check/preflight identifiquen el parche por nombre completo
- **Estado:** APPROVED (director, 2026-11-14)
- **Razón:** T-0009 midió que solo colisionan 0332 y 0334 (upstream no usa 0335, que D-0008 daba por colisión) y que los 5 parches aplican en ambos órdenes sin pisarse. El riesgo real es de identificación: el prefijo 0334- de ci_check.py casa con el parche de DROP v2 y con present-wait-asleep de upstream, y podría dar un falso 'aplicado'. Informe: docs/herolte-integracion-origin-herolte.md (E-0024).
- **Consecuencias:** Cambia nombres de dos ficheros de la serie y unas 25 referencias documentales/herramientas (no los nombres de artefacto kernel-0334-*). El kernel de la candidata N2 no cambia por el renombrado, pero sí si se fusiona y reconstruye con 0332-0334 de upstream; entonces la candidata N2 se regenera con nombre nuevo y se reverifica.
- **Cómo se revierte:** git revert de los renombrados antes de publicar.
- **Sustituye a:** D-0008

## D-0015 — Aislamiento de clientes de HeroGPU: address space por cliente, jc_va validada contra los BO del cliente, entitlement en initWithTask, presupuesto de memoria y SurfaceBO con comprobación de propiedad
- **Estado:** PROPOSED
- **Razón:** docs/S7GE_ABI.md (T-0008) leyó HeroGPU.cpp y herolte_gpu.c y encontró: una sola AS0 compartida por todos los clientes, Submit con la VA de la cadena de jobs aportada por el cliente y sin validar, ningún entitlement ni presupuesto de memoria, SurfaceBO con búsqueda global por id y handles sin generación. Incumple los principios 2.5 y 23 de S7GE. T-0010 (docs/S7GE_HARDWARE.md §3) añade, por lectura de código y sin prueba en hardware, que el bloque de trabajo de 2 MiB mapeado RW en AS0 contiene la tabla L2 de los búferes de usuario y las L3 de presentación: un job podría reescribirlas y alcanzar memoria física arbitraria.
- **Consecuencias:** Es una modificación del kernel y de la serie de parches (nivel B, revisor jefe técnico): se haría con una tarea nueva y tras esa revisión. Hasta entonces la GPU solo debe usarla software del proyecto en el teléfono de pruebas.
- **Cómo se revierte:** Es una propuesta; si se implementa, git revert del parche.

## D-0016 — Cargador de las pruebas: usar el compilado con clang (loader-clang/, E-0008); no ejecutar el GCC descargado
- **Estado:** APPROVED (jefe-tecnico, 2026-11-13)
- **Razón:** clang ya está disponible en ~/HackiOS/builds/device-day/loader-clang/ y se usó en E-0008; no requiere compilar ni ejecutar nada nuevo.
- **Consecuencias:** T-0013 se cierra sin ninguna acción roja. No autoriza escribir BOOT ni tocar el teléfono. El preflight seguirá avisando de que no hay GCC aarch64: es un aviso conocido y aceptado.
- **Cómo se revierte:** Nueva decisión que elija GCC (requeriría host-config-change, roja).

## D-0017 — Corrección Unicode: regenerar en el generador del root los nombres en forma XNU (sin tocar el kernel), antes de repetir R2
- **Estado:** APPROVED (director, 2026-11-13)
- **Razón:** La directiva de jefatura técnica del 2026-11-13 elige 'Opción 3: regenerar nombres en el generador del root usando la tabla de XNU' (sin cambios de kernel, reversible). La numeró D-0003, que ya es la dirección de S7GE; el texto no mapea con exactitud a las opciones de docs/herolte-unicode-hfsplus.md (1-5, B, C, D): se interpreta como la corrección 1-5 sin la parte del kernel.
- **Consecuencias:** Cambiar el generador del root es decisión del DIRECTOR (AUTHORITY.md §2) y D-0006 lo mantiene congelado hasta que decida: por eso queda PROPUESTA y T-0003 sigue bloqueada. Además, mi informe (sección 3) recomienda la corrección solo si R2 la confirma, y R2 sigue sin autorizar (D-0005, de nivel rojo): se necesita la confirmación del Director de si acepta aplicarla sin R2 previo.
- **Cómo se revierte:** git revert del cambio del generador; las imágenes viejas se conservan (E-0010).

## D-0018 — Levantar la congelación del generador del root (D-0006) solo para aplicar D-0017: imagen NUEVA con nombre nuevo, sin R2 previo y sin tocar la anterior
- **Estado:** APPROVED (director, 2026-11-13)
- **Razón:** El Director aprueba D-0017 y autoriza cambiar el generador sin R2. Mantiene las demás restricciones de la serie (D-0005: no se autoriza R2).
- **Consecuencias:** Permite modificar el generador/herramientas del root en el árbol de trabajo y generar una imagen nueva con nombre nuevo. NO autoriza: R2, montar imágenes, sudo, sustituir o borrar lab-full.img.partial, escribir en el teléfono. La imagen anterior y sus hashes quedan intactos.
- **Cómo se revierte:** git revert del cambio del generador; las imágenes anteriores se conservan (E-0010).
- **Sustituye a:** D-0006

## D-0019 — Delegación: la jefatura técnica (Qwen) decide lo técnico en nombre del Director; el Director lee todo e interviene de forma extraordinaria
- **Estado:** APPROVED (director, 2026-11-13)
- **Razón:** El Director lo dispone por razones de seguridad y rapidez. Qwen ocupa el puesto de jefe técnico.
- **Consecuencias:** Las directivas de la jefatura técnica valen para objetivos, arquitectura, prioridades y decisiones técnicas sin nueva confirmación. LECTURA DEL INGENIERO (conservadora, a confirmar si se discrepa): no incluye autorizar acciones de nivel C (sudo, montar, publicar, borrar, tocar el teléfono) ni cambiar reglas X: esas siguen exigiendo una decisión del Director que nombre la acción (AUTHORITY.md §4), y la herramienta lo comprueba. Las directivas de jefatura que piden tocar el S7 ya dicen que necesitan 'autorización ROJO explícita'.
- **Cómo se revierte:** Nueva decisión del Director.

## D-0020 — Excluir del root los 2 ficheros con U+0E33 (WorkflowKit th.lproj): sin nodecompose y sin parchear XNU
- **Estado:** APPROVED (director, 2026-11-13)
- **Razón:** La tabla de Linux descompone U+0E33 y XNU lo conserva (docs/herolte-unicode-aplicacion.md). Excluir 2 ficheros de localización tailandesa evita montar con nodecompose y modificar la tabla de XNU. La jefatura afirma que iOS hace fallback a en.lproj: NO verificado por el ingeniero.
- **Consecuencias:** Los 2 ficheros no estarán en el root (KI-0006). NO autoriza ninguna acción roja: generar la imagen sigue necesitando la autorización del Director que nombre privileged-or-mount (T-0025).
- **Cómo se revierte:** Nueva decisión que elija nodecompose (roja) o el parche de la tabla.

## D-0021 — Autorización roja de un solo uso: privileged-or-mount para generar la imagen NUEVA de T-0025 (perfil full-xnu) con los comandos del laboratorio
- **Estado:** SUPERSEDED
- **Razón:** Aplicar D-0017/D-0020: imagen con los nombres en forma XNU y los 2 con U+0E33 excluidos.
- **Consecuencias:** [SUSTITUIDA por D-0025 el 2026-11-14: privileged-or-mount pasó a nivel A, ya no hace falta autorización; se conserva como historia. Fue la autorización roja registrada para el populate/verify de T-0025, que se ejecutaron bajo ella.] ALCANCE (lectura del ingeniero): solo los comandos de COMANDOS_SUDO.md (populate_image.sh, verify_image.sh), con el perfil NUEVO full-xnu (imagen lab-full-xnu.img.partial; make_image.sh full-xnu no necesita sudo); los ejecuta el Director con sudo, o el ingeniero solo si la sesión dispone de sudo y el Director lo pide. NO incluye: tocar lab-full.img.partial ni sus .populated/.sha256 (populate_image.sh se niega por diseño a repoblar una imagen con .populated), r6_failure_tests.sh (otros ~12 GB), R2, borrar sandboxes (T-0007), ni tocar el teléfono. Un solo uso; caduca el 2026-11-20.
- **Cómo se revierte:** Desmontar y desasociar el loop con cleanup_image; la imagen nueva es desechable; la anterior no se toca.

## D-0022 — Reformulación de niveles: nuevo nivel NARANJA (la jefatura técnica puede autorizar operaciones privilegiadas de host) y ROJO CRÍTICO solo para el dispositivo físico
- **Estado:** SUPERSEDED
- **Razón:** El sistema de niveles resultaba demasiado burocrático para operaciones rutinarias de desarrollo.
- **Consecuencias:** Nivel NARANJA (autorizador: jefatura técnica): sudo y montaje en el host, compilación pesada, generación de imágenes de prueba, uso intensivo de recursos, sin tocar el dispositivo. ROJO CRÍTICO (solo Director): flashear el S7, particiones reales, bootloader o firmware, borrar datos del dispositivo, toda operación física irreversible. La directiva NO reclasifica el borrado de ficheros del host ni la publicación (push/CI): el ingeniero los mantiene en rojo hasta que se diga lo contrario. AGENTS.md sigue mandando (EFS, RECOVERY y bootloader no se escriben nunca).
- **Cómo se revierte:** Nueva decisión del Director; restaurar policy.toml anterior (git revert).

## D-0023 — Autorización roja de un solo uso: borrar de ext4 los 224 sandboxes ya archivados en NTFS (T-0007)
- **Estado:** APPROVED (director, 2026-11-13)
- **Razón:** Los sandboxes están en el TAR E-0011 (sha256 verificado y comparados byte a byte con el disco antes de borrar). Hacen falta ~25 GiB para T-0025.
- **Consecuencias:** ALCANCE (lectura del ingeniero): solo los 224 directorios sandboxes-* que son miembros del TAR (tests/ y rev2/tests/ bajo t04r/r2/v2), sin sudo ni comodines (lista exacta, rm solo de esos directorios). NO se borra: results-*, battery*, mutants3-*, mutation_summary*, los sandboxes posteriores al TAR (ronda 2 de T-0005 en curso), review-independiente/prod, ni nada fuera de la lista.
- **Cómo se revierte:** Restaurar desde el TAR E-0011.

## D-0024 — Copiar los scripts del laboratorio a tools/ios-root-lab/ con un adaptador de nombres XNU en un solo punto
- **Estado:** APPROVED (director, 2026-11-13)
- **Razón:** Los originales (fuera de git, con sumas fijadas) no se tocan; la adaptación vive en el repositorio con pruebas.
- **Consecuencias:** Resuelve el obstáculo 3 de T-0025. Los originales del laboratorio quedan intactos.
- **Cómo se revierte:** Borrar tools/ios-root-lab/ (git revert).

## D-0025 — sudo en el host, montaje de imágenes, compilación pesada y generación de imágenes de prueba pasan a nivel VERDE (autónomo); sustituye a D-0022
- **Estado:** APPROVED (director, 2026-11-14)
- **Razón:** El Director quita la burocracia de las operaciones de laboratorio en el host y mantiene su control sobre lo irreversible.
- **Consecuencias:** Acciones privileged-or-mount (ahora A) y heavy-compile (nueva, A). NO se reclasifican: borrar o mover datos (delete-or-overwrite), publicar/push/PR/CI, host-config-change, y todo lo que toque el teléfono (device-*, write-protected-partitions): siguen en su nivel. R2 sigue sin autorizar (D-0005, restricción específica). El criterio de seguridad de los ejecutores (guardas de img_common.sh/guard.py) no cambia. La estructura de niveles sigue siendo A verde, B amarillo, C/X rojo (tres colores): no se creó un nivel naranja.
- **Cómo se revierte:** Nueva decisión del Director; git revert del cambio de policy.toml.
- **Sustituye a:** D-0022

## D-0027 — Borrar de /tmp dos artefactos ya archivados y con hash en NTFS (lab-full-xnu.img.valid y r3/work) para liberar ~24 GiB para T-0028
- **Estado:** APPROVED (director, 2026-11-14)
- **Razón:** E-0031 (imagen, sha256 747d0245…ec27f idéntico en NTFS) y E-0013 (r3/work, restaurable). Se necesitan >= 12 GiB libres y hoy hay ~6.
- **Consecuencias:** Autorizado por el Director (D-0028). Alcance exacto: lab-full-xnu.img.valid y r3/work del scratchpad, por ruta exacta, tras releer los hashes del archivo. Es un caso de delete-archived (nivel A desde D-0028).
- **Cómo se revierte:** Restaurar desde E-0031 y E-0013.

## D-0028 — Mayor autonomía del ingeniero y de la jefatura técnica para agilizar: borrar temporales ya archivados pasa a verde (delete-archived); el Director lee todo e interviene de forma extraordinaria
- **Estado:** APPROVED (director, 2026-11-14)
- **Razón:** El sistema anterior hacía perder eficiencia y tiempo. El Director está aprendiendo, no puede autorizar lo que no conoce, y prefiere supervisar leyendo y cancelando.  Delega en el ingeniero la forma de aplicarlo (modifica como veas).
- **Consecuencias:** Aplicación (decisión del ingeniero, reversible): (1) delete-archived, nueva acción de nivel A, para borrar artefactos temporales YA archivados con hash verificado, por ruta exacta; (2) se aprueba además D-0027. NO cambia, para que el Director conserve el control de lo irreversible o externo: tocar el teléfono (device-*, write-protected-partitions), reglas X y AGENTS.md (solo BOOT en pruebas XNU; nunca EFS, RECOVERY ni bootloaders), borrado GENERAL (evidencia sin copia, ficheros del repositorio), publicar/push/PR/CI en el repositorio público, R2 (D-0005), host-config-change. El Director puede ampliar cualquiera de esos con una frase. Las directivas de la jefatura técnica valen como dirección técnica y prioridades; las acciones de nivel C solo las cubre una decisión del Director.
- **Cómo se revierte:** Nueva decisión del Director; git revert del cambio de policy.toml.

## D-0029 — Permitir el NVMe NTFS como zona de trabajo temporal para imágenes grandes y staging (sustituye a D-0002)
- **Estado:** APPROVED (director, 2026-11-14)
- **Razón:** Más espacio de trabajo sin saturar /dev/sda2.
- **Consecuencias:** ext4 sigue preferido para código, repositorios y lo que se monta en bucle (NTFS es más lento y frágil para eso); el NVMe vale para imágenes grandes, staging y temporales de más de 10 GiB; el archivo verificado sigue en IOS-S7-archive. Borrar sigue las reglas de delete-archived (copia verificada por hash) o requiere al Director.
- **Cómo se revierte:** Nueva decisión del Director.
- **Sustituye a:** D-0002

## D-0030 — Autorizar push de la rama herolte-drop-v2 al fork darkcloud9998/ios-a5xelte, lanzar el CI xnu y descargar sus artefactos, para fusionar los parches de upstream y reconstruir la candidata BOOT
- **Estado:** APPROVED (director, 2026-11-14)
- **Razón:** Es el único camino para compilar el kernel combinado (macOS runners).
- **Consecuencias:** ALCANCE (lectura del ingeniero): solo la rama herolte-drop-v2 y solo el remoto mio (https://github.com/darkcloud9998/ios-a5xelte.git), tras un escaneo del contenido a publicar en busca de datos privados (AGENTS.md); lanzar el workflow xnu y descargar sus artefactos; sin push a origin (wardevsa/ios-a5xelte), sin PR, sin force-push. NO autoriza tocar el teléfono.
- **Cómo se revierte:** Borrar la rama remota del fork; lo publicado puede haberse copiado: no es reversible del todo.

## D-0031 — OSMesa: mantenerlo nosotros (Opción B) en lugar de quedarse en Mesa 25.0.7 o migrar ya a otra superficie; política en docs/S7GE_OSMESA_FORK_POLICY.md
- **Estado:** APPROVED (jefe-tecnico, 2026-11-14)
- **Razón:** OSMesa fue eliminado en Mesa 25.1.0 (S7GE_MESA_VERSION_ANALYSIS.md). Mesa 25.0.7 funciona y está probada; mantener el frontend da control sin reescribir toda la integración; la migración de superficie se decide en la fase S7GL.
- **Consecuencias:** Es DIRECCIÓN, no implementación: NO autoriza crear gpu/mesa/osmesa-fork/ ni tocar parches ni gpu/mesa. La implementación espera la confirmación del Director y la elección entre B1 (congelar Mesa 25.0.7 entera) y B2 (solo el frontend sobre un Mesa más nuevo); condiciones previas en la política §4.
- **Cómo se revierte:** Nueva decisión de arquitectura; no hay código que revertir.

## D-0032 — El Director confirma la Opción B2 de OSMesa: mantener solo el frontend OSMesa (osmesa.c, ~1 286 líneas) sobre un Mesa más nuevo; refina y confirma D-0031
- **Estado:** APPROVED (director, 2026-11-14)
- **Razón:** La jefatura la recomienda: Mesa moderno sigue manteniendo Panfrost para Midgard v5 (T760/T820/T830/T860/T880 constan en docs/drivers/panfrost.rst de 26.2.4, con correcciones recientes en 26.1 y 26.2) y recibe correcciones de seguridad; B1 (congelar 25.0.7) las perdería.
- **Consecuencias:** Cumple la condición (a) de S7GE_OSMESA_FORK_POLICY.md §4: queda autorizado trabajar en gpu/mesa/ (NO en xnu/, kernel ni parches): documentar y construir la integración del frontend. Siguen siendo condiciones propias del trabajo: (c) un entorno de compilación de Mesa (en el PC solo se puede probar una compilación de comprobación en Linux; la de iOS es del CI de macOS), (d) quién vigila los avisos de seguridad, (e) licencia declarada del código propio. NO autoriza publicar (push/CI) más allá de lo que ya cubre D-0030, ni tocar el teléfono.
- **Cómo se revierte:** Nueva decisión de arquitectura; si se crea gpu/mesa/osmesa-frontend/, git revert.

## D-0033 — Autorización roja de un solo intento: fase 1 del primer arranque N2 — escribir xnu-boot-v2-s7-min-20261114.img en la partición BOOT del S7 desde TWRP
- **Estado:** APPROVED (director, 2026-11-14)
- **Razón:** Primer peldaño real en el hardware (N2 de menor huella): comprobar que cargador, kernel y ADT arrancan en esta unidad. Almacenamiento de solo lectura y sin Wi-Fi, energía ni GPU.
- **Consecuencias:** ALCANCE EXACTO (lectura del ingeniero del texto de la solicitud §7): escribir SOLO la imagen xnu-boot-v2-s7-min-20261114.img (SHA-256 07ddfa069c7f53936964e05f174ddced6a75b6ff690180e648a082c941115db3, 18 618 384 bytes) en la partición BOOT (by-name/BOOT = /dev/block/sda5), desde TWRP, con tools/herolte-flash-boot.sh, y leer del teléfono BOOT y EFS (solo lectura) para comprobarlos antes y después; vuelta atrás con el BOOT original (E-0009, sha256 adc519d0f16fd314ea05b072820a81c3a623db2ba446397c87c7ed70776c3348), que también queda autorizada como escritura de BOOT si hace falta restaurar. Se acepta que SYSTEM y USERDATA no están verificados porque la fase 1 no los toca. NO autoriza: ninguna otra imagen (la candidata normal, fase 3, exige otra autorización con su hash), escribir EFS, RECOVERY ni bootloaders (AGENTS.md; regla X), escribir en USERDATA ni en /sdcard, ni usar Download/Odin. El reinicio para el arranque y la observación los hace el Director con la pantalla grabada.
- **Cómo se revierte:** Restaurar BOOT con el original verificado (docs/S7GE_FLASH_PROCEDURE.md §4).

## D-0034 — Autorización roja: segundo intento del primer arranque N2 — escribir xnu-boot-v2-s7-min2-20261114.img (variante mínima + vm_compression_limit=98304 vm_compressor=2) en la partición BOOT del S7 desde TWRP
- **Estado:** APPROVED (director, 2026-11-14)
- **Razón:** El primer arranque (D-0033, imagen mínima 1) hizo panic en kmem_range_init; la causa más probable es la ausencia de vm_compression_limit con un ADT de 2 GiB (S7GE_FIRST_BOOT_ANALYSIS.md). Este intento cambia una sola variable.
- **Consecuencias:** ALCANCE EXACTO: escribir SOLO la imagen xnu-boot-v2-s7-min2-20261114.img (SHA-256 595316aae927b3e7c960301790fa34557e5a296073a29df62522b67050edae21, 18 618 384 bytes) en BOOT (by-name/BOOT = /dev/block/sda5), desde TWRP, con tools/herolte-flash-boot.sh, leyendo BOOT y EFS del teléfono (solo lectura) antes y después; vuelta atrás con el BOOT original (E-0009, adc519d0…3348), también autorizada. NO autoriza ninguna otra imagen, escribir EFS, RECOVERY ni bootloaders, escribir en USERDATA ni /sdcard, ni cambiar el ADT. El reinicio y la observación los hace el Director con la pantalla grabada; con el panic anterior en bucle, el reinicio no es necesario para escribir (el teléfono debe estar en TWRP).
- **Cómo se revierte:** Restaurar BOOT con el original verificado (S7GE_FLASH_PROCEDURE.md §4).


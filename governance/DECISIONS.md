<!-- GENERADO por tools/governance.py render desde governance/data/*.toml. NO EDITAR A MANO: se pierde en el siguiente render. -->

# Registro de decisiones

Estados: `PROPOSED` (propuesta, **sin efecto**), `APPROVED` (aprobada por quien tiene autoridad para ese ámbito, con referencia), `REJECTED`, `SUPERSEDED`. Una propuesta del ingeniero **no es una decisión aprobada**.

| ID | Estado | Ámbito | Fecha | Título | Propone | Aprueba | Referencia |
|---|---|---|---|---|---|---|---|
| D-0001 | PROPOSED | process | 2026-11-13 | Sistema de gobierno de ingeniería autónoma (carpeta governance/, herramienta tools/governance.py) | ingeniero | — | — |
| D-0002 | APPROVED | policy | 2026-11-13 | Política de almacenamiento: ext4 para trabajo activo, NTFS para archivo histórico; NTFS nunca como scratchpad de Claude | ingeniero | director | Mensaje del Director 'Recuperar espacio real y completar la organización' (apartado 4, configuración permanente), 2026-11-13; documento IOS-S7-archive/05-manifests-and-hashes/POLITICA_ALMACENAMIENTO.md |
| D-0003 | APPROVED | architecture | 2026-11-13 | Dirección de S7GE: Metal como interfaz principal, IR común S7GIR, backend Midgard específico T880, OpenGL ES como API adicional, GPU física como ruta objetivo | jefe-tecnico | jefe-tecnico | S7GE_ARCHITECTURE.md Parte XXII 'Decisiones oficiales de dirección' (el jefe técnico define la arquitectura); el Director lo recibió y ordenó conservarlo para el proyecto el 2026-11-13. No es una autorización de ninguna acción de nivel C |
| D-0004 | APPROVED | process | 2026-11-13 | Criterios de la candidata N2 de solo lectura: sin ufsrw/rootrw distintos de =0, con ufsrw=0 herolog=0 herodrop=0 explícitos, verificada con herolte-verify-boot.py --profile n2-readonly | ingeniero | director | Mensaje del Director 'cerrar correctamente el verificador BOOT y producir una candidata N2 inequívocamente de solo lectura', 2026-11-13 |
| D-0005 | APPROVED | operation | 2026-11-13 | El experimento R2 (monta imágenes, usa sudo) no está autorizado | ingeniero | director | Restricciones reiteradas del Director en todos los mensajes de la serie T04-R2/Unicode: 'No ejecutes R2', 'No autorices R2', 'No monta imágenes' |
| D-0006 | APPROVED | operation | 2026-11-13 | Generación del root: no cambiar el generador ni regenerar lab-full.img.partial hasta decidir sobre el bloqueo Unicode | ingeniero | director | Mensajes del Director 'Espera mi decisión antes de implementar cambios que afecten a la generación del root filesystem' y 'No repares, regeneres ni sustituyas esa imagen todavía', 2026-11-13 |
| D-0007 | PROPOSED | architecture | 2026-11-13 | Reservar el rango de parches 0400+ para S7GE (el 0300-0309 propuesto en S7GE_ARCHITECTURE.md ya está ocupado) | ingeniero | — | — |
| D-0008 | PROPOSED | architecture | 2026-11-13 | Renumerar nuestros 0332 (marcador DROP), 0334 (DROP v2) y 0335 (splash) antes de fusionar con origin/herolte, que ya usa 0332-0334 para gráficos | ingeniero | — | — |
| D-0009 | PROPOSED | architecture | 2026-11-13 | Ratificar las decisiones D1-D12 de DROP v2 de xnu/drop-v2/DECISIONES.md, tomadas por el jefe de proyecto suplente | ingeniero | — | — |
| D-0010 | APPROVED | operation | 2026-11-13 | Escribir en BOOT del S7 (peldaños N1/N2) requiere una autorización C específica; la candidata verificada del PC no la sustituye | ingeniero | director | Mensaje del Director 'Todavía NO hemos comenzado las pruebas reales en el Galaxy S7... No confundas imágenes generadas con un arranque real', 2026-11-13; AGENTS.md (solo BOOT) |

## D-0001 — Sistema de gobierno de ingeniería autónoma (carpeta governance/, herramienta tools/governance.py)
- **Estado:** PROPOSED
- **Razón:** La Misión 0 pide una estructura permanente y verificable para continuar el proyecto entre sesiones y modelos. Se implanta como propuesta: ningún modelo debe darla por aprobada hasta que la revise el jefe técnico y la ratifique el director.
- **Consecuencias:** Si se aprueba, las reglas de AUTONOMY_POLICY.md y policy.toml pasan a vincular a cualquier ingeniero que trabaje en el repositorio. Si se rechaza, se retira la carpeta y el puntero de AGENTS.md.
- **Cómo se revierte:** git revert del commit de implantación; quitar el puntero a governance/ en AGENTS.md.

## D-0002 — Política de almacenamiento: ext4 para trabajo activo, NTFS para archivo histórico; NTFS nunca como scratchpad de Claude
- **Estado:** APPROVED (director, 2026-11-13)
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
- **Estado:** APPROVED (director, 2026-11-13)
- **Razón:** Hay 32 nombres Unicode que Linux escribió distinto de XNU (docs/herolte-unicode-hfsplus.md); las opciones son la corrección 1-5, la alternativa (B) o la (C).
- **Consecuencias:** T-0003 es una decisión pendiente; hasta entonces el generador y la imagen de laboratorio no cambian.
- **Cómo se revierte:** Decisión del director que elija una de las opciones.

## D-0007 — Reservar el rango de parches 0400+ para S7GE (el 0300-0309 propuesto en S7GE_ARCHITECTURE.md ya está ocupado)
- **Estado:** PROPOSED
- **Razón:** 0300-0335 existen en el árbol (0301 audio, 0307 L3 de GPU, 0317 WebKit...). Reutilizar números rompe aplicabilidad y trazabilidad.
- **Consecuencias:** Los nombres de parche de S7GE empezarían en 0400. Requiere revisión del jefe técnico porque toca la numeración de la serie.
- **Cómo se revierte:** Renombrar los parches S7GE; no hay ninguno creado todavía.

## D-0008 — Renumerar nuestros 0332 (marcador DROP), 0334 (DROP v2) y 0335 (splash) antes de fusionar con origin/herolte, que ya usa 0332-0334 para gráficos
- **Estado:** PROPOSED
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


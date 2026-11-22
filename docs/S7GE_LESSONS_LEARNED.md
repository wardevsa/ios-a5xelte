# S7GE — lecciones de los tres primeros arranques (min1, min2, min3) — 2026-11-14

Nivel de evidencia: observaciones del Director a ojo o con vídeo transcrito por IA (L2); código leído (L1). Nada de esto sube de nivel sin vídeo archivado con hash.

## 1. Los tres intentos
| | Imagen | Cambio respecto al anterior | Autorización | Lo observado (L2) | Lectura prudente |
|---|---|---|---|---|---|
| min1 | `xnu-boot-v2-s7-min-20261114` | variante mínima (UFS solo lectura, sin Wi-Fi/energía/GPU) | D-0033 | panic en `kmem_range_init`; texto rápido en el arranque | el kernel llega a C y a `kmem_range_init` con ADT de 2 GiB sin `vm_compression_limit` (KI-0009) |
| min2 | `…min2…` | `vm_compression_limit=98304 vm_compressor=2` | D-0034 | bloques azul, cian y magenta; `XNU MMU ON`; pantalla fija; sin panic | cuelgue silencioso; **no** demuestra avance ni retroceso |
| min3 | `…min3…` | ADT 1536 MiB (2 bytes) | D-0035 | `XNU MMU ON`; sin texto `A5 XNU STAGE` | **igual que min2**: la RAM no cambió el síntoma; el ADT no rompió el arranque temprano |

## 2. Errores de interpretación (de jefatura y del ingeniero) y su corrección
- "No hay panic, luego `vm_compression_limit` funcionó": ausencia de texto no es avance (un cuelgue mudo produce lo mismo).
- Los bloques de color son de **XNU** (`start.s`), no del cargador; `NO XNU ON` no existe (es `XNU MMU ON`).
- `BOOTARGS` del cargador imprime la **dirección** de `boot_args`, no la línea de arranque; no sirve para comprobar argumentos (se comprueba en la imagen).
- `kext_range_init` era `kmem_range_init`; "handshake structure not initialized" es la fase de coredump, no la causa.
- "RS XNU STAGE" era `A5 XNU STAGE`; `arm_limit`/`cpu_limit` eran `arm_init entered`/`cpu_init done`.
- `kmem_range_init` va **después** de la marca 7: un texto que acabe en la 6 no la implica.
- "min3 sin MMU": falso; el bloque azul se dibuja tras encenderla y se vio.
- Mi propio fallo: verifiqué la estructura de las candidatas pero no las comparé con la configuración que el upstream documentó como funcional (KI-0009, punto 20 de la lista previa).
- Las autorizaciones rojas nombran imagen y hash; "autorizo seguir con min3 o lo que veas" no lo hacía. El número de serie del teléfono no va en documentos ni en textos de autorización.

## 3. Cómo observar (lo que de verdad falta)
- **Cuidado con este sesgo:** el texto `A5 XNU STAGE` es rápido y XNU puede borrarlo al inicializar su consola. Que **no se vea** en min2/min3 **no prueba** que no se imprimiera; los **bloques de color** (que no se borran) son la única señal fiable que tenemos. Las marcas C 6a-6c de 0338 son texto: pueden pasar igual de desapercibidas.
- Grabar en cámara lenta (la mayor tasa disponible), de cerca, desde `HEROLTE XNU LOADER` hasta pantalla fija; pausar fotograma a fotograma; anotar de qué imagen es cada grabación. Transcribir literal, sin interpretar.
- Contar los bloques por posición y color (verde y=88, azul 120, cian 152, magenta 184, amarillo 216; naranja 312 y 344 en min4).

## 4. Hipótesis
| Hipótesis | Estado |
|---|---|
| El ensamblador de `start.s` entre magenta y amarillo se detiene | sin mecanismo en el código (adenda de MIN2 §6.1); se comprobará con los bloques naranja de min4 |
| RAM de 2 GiB / `kmem_range_init` explica min2 | **no sostenida** para min2/min3: min3 con 1536 MiB se comporta igual |
| Cuelgue en C antes de la marca 7 | **abierta**; es lo que miden 6a-6c si el texto se ve |
| Texto de etapas visible solo en el primer arranque | **sin explicar**; posible borrado por la consola, o transcripción incompleta |

## 5. Decisiones y evidencia
D-0033 (min1), D-0034 (min2), D-0035 (min3); E-0043/44 (min1), E-0045/46 (min2), E-0048/49 (min3); KI-0008, KI-0009. La imagen min4 (parche 0338) está pendiente del CI.

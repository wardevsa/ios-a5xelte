# Panic `turnstile promotion for type 1 not yet implemented` (16-nov-2026)

Observaciones del Director (L0, foto/texto de pantalla) y logs del anillo (L2). Ninguna causa demostrada todavía.

| Imagen | Kernel | Línea | Resultado |
|---|---|---|---|
| min37 (`7db96c99…520d`) | CI 43734698003 (c833e11) | línea de 597 car. | arranca, pantalla de inicio, 120 s de latidos (log min37d) |
| min40 (`518afd1e…`) | CI 43959616603 (bb2bad0, +0335-0338, +0428, +0429) | sin herohalt/herogl/herosb/sweettop, +heroaudio=3 | panic (sin texto) |
| min41 (`ca3f46e9…`) | idem | min40 sin heroaudio | panic |
| min42 (`2b6dec00…`) | idem | línea de min37 exacta | panic: `A5 XNU PANIC: turnstile promotion for type 1 not yet implemented @:2412` |
| min43 (`a10e7766…`) | idem | min42 sin herohalt=1, +herovgr=0 | panic `turnstile` |
| min44 (`ed1ef7c7…`) | CI 43969438696 (55336ce) = bb2bad0 sin 0428/0429 | línea de min37 exacta | panic (pantalla: `A5 XNU PANIC` sin texto) |

Descartado: audio (min41), valores por defecto de 0428 (min42 los lleva explícitos), VGR0 por defecto de 0338 (min43; además el kernel de min38d, que arrancó, ya llevaba 0335-0338), 0429 (solo corre al apagar), deriva del compilador (imagen del runner idéntica en ambos CI: macos-15 20260824.0482.1, Xcode 16).
El panic (`osfmk/kern/turnstile.c:2412`, `turnstile_compute_thread_push`) solo se alcanza con una política de promoción desconocida: estructura de turnstile corrupta o tipo inválido, no un fallo lógico del planificador.
Todos los paneles ocurren en el primer minuto o minuto y medio (un solo volcado del anillo).
Descartados también 0428 y 0429 (min44). Siguiente prueba: CI 43972623049 (bb2ade7) = sin 0335-0338 (los parches VGR0 de upstream, la última diferencia con el kernel de min37). Si aun así cae: recompilar hoy el commit exacto c833e11 como control.

## Causa encontrada (17-nov-2026)
Los paneles de min40-min47 NO venían del kernel: las imágenes se empaquetaron con `boot-candidates-n2/embedded.adt`, que la otra sesión modificó el 16-nov a las 10:05 (después de min37); min37 se construyó con `boot-candidates/herolte-3g.adt` (la reconstrucción de min37 con ese ADT reproduce su SHA `7db96c99…520d`; con embedded.adt sale otro). min48 (kernel con 0363, línea de min37, herolte-3g.adt; `6da972b0…4596`) arrancó a la pantalla de inicio (log min48: 60 s de vida, 3058 MB libres, SoC 37 C). Lección: reproducir el SHA de la imagen buena antes de construir variantes, y no reutilizar ficheros de entrada compartidos entre sesiones sin fijar su hash. `tools/herolte-build-min.sh` usa ya herolte-3g.adt por defecto.

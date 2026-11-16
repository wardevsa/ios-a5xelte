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

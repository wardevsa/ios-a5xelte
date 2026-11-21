# S7GE — plantilla de observación de min4 (bloques de color primero)

**Principio:** los bloques de color de `start.s` se quedan en pantalla; el texto `A5 XNU STAGE` es fugaz y puede borrarse. Se cuenta **por posición (y)**, nunca por orden de aparición.

## 1. Grabar
Cámara lenta a la mayor tasa disponible, de cerca (esquina superior izquierda y la columna de bloques a la derecha del texto), desde el logo de Samsung hasta que la pantalla quede fija **más 2 minutos**. Una grabación por imagen; decir en voz alta o escribir qué imagen es. Pausar la **última imagen fija** y hacer una captura nítida.

## 2. Checklist (rellenar con SÍ / NO / DUDOSO; x = 240 px, cada bloque 36×21 px)
| y | Color | Qué lo dibuja | Origen | ¿Visible? |
|---|---|---|---|---|
| 88 | verde | entrada a `start.s` | existente | |
| 120 | azul | MMU encendida | existente | |
| 152 | cian | FPU habilitada | existente | |
| 184 | magenta | `tunables_done` | existente | |
| 216 | amarillo | justo antes del `ret` a `arm_init()` | existente | |
| 312 | naranja | tras el salto de arranque en caliente (`cbnz x21`) | **nuevo, 0338** | |
| 344 | naranja claro | tras calcular la dirección de `boot_args` | **nuevo, 0338** | |
Texto (anotar literal, aunque sea parcial): `XNU ENTRY` (24,256), `XNU MMU ON` (24,288), líneas `A5 XNU STAGE n: …` (incluidas `6a`, `6b`, `6c`), `A5 XNU PANIC`, `HEROLTE KMEM`.
Orden en el código: verde → azul → cian → magenta → **naranja 312 → naranja claro 344 → amarillo 216**; el amarillo se dibuja el **último**, aunque esté más arriba en pantalla.

## 3. Interpretación (cuando todo lo demás sea igual)
| Bloques visibles | Lectura |
|---|---|
| hasta magenta, sin naranjas | el ensamblador se detiene tras `tunables_done` (inesperado según el código) o los bloques nuevos no se dibujan: revisar el parche antes de concluir |
| magenta + naranja 312, sin 344 | se para entre el salto de arranque en caliente y el cálculo de `boot_args` (dos instrucciones de aritmética: improbable, mirar `x20-x23`) |
| magenta + ambos naranjas, sin amarillo | se para en el bloque amarillo mismo: problema de escritura al framebuffer o de dirección |
| los siete bloques | el ensamblador termina; el cuelgue está en C |
| los siete + texto `A5 XNU STAGE` hasta 6a/6b/6c/7 | la última marca visible acota el cuelgue en C; la siguiente es donde para |
| los siete, sin texto | no se concluye nada del texto (ver §0 de `S7GE_LESSONS_LEARNED.md`); siguiente paso: marcas de color en C |
| menos bloques que min2 (azul, cian, magenta) | regresión de la imagen: restaurar BOOT |
| `A5 XNU PANIC` o `HEROLTE KMEM` | transcribir literal; hay consola |

## 4. Entrega
Texto literal + la captura de la pantalla final + qué imagen es. Sin interpretar ni resumir: la interpretación la hace el ingeniero con esta tabla y el código.

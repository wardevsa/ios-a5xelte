# S7GE — resultado de min6 (2026-11-14; observación del Director, L2, E-0057)
**Observado (literal):** "nada, no apareció nada entre HEROLTE… y los 3 colores con XNU MMU ON". Es decir: ni columna derecha, ni texto `A5 XNU STAGE`, ni bloques de `arm_vm_init`.

## Lectura prudente
- **Contradice min5**, donde se vieron texto de etapas y 7 bloques. Con el mismo ADT y los mismos argumentos, solo cambia el kernel (0340). Dos explicaciones:
  1. **Observación**: el tramo C dura una fracción de segundo y es fácil perderlo sin cámara lenta (en min5 se vio, y cada intento depende de la atención del observador). **No es una conclusión**: nadie ha archivado un vídeo de min5 ni de min6.
  2. **Regresión de 0340**: por código es poco probable (0340 solo cambia la desactivación de la consola tras la marca 7 y añade dibujos en x=1300; no toca nada antes de la etapa 1), pero no se puede descartar.
- Importa lo que **no** dice: sigue sin saberse en qué fase se reinicia el kernel, porque la pantalla "final" es la de tras el reinicio.

## Consecuencia de método
Hemos hecho cuatro escrituras seguidas (min3-min6) cuyo resultado depende de ver unos fotogramas de ~100 ms. **Esto no escala.** Propuesta (parche `0341`, `xnu/patches/0406-herolte-herostop-bisect.patch`, aplica sobre 0340; en CI): boot-arg **`herostop=N`** que, tras dibujar el bloque N, **congela la CPU** (`wfe` en bucle). La pantalla queda fija mostrando los bloques 0..N si la ejecución llega a N; si no llega, se ve el reinicio de siempre. Así:
- cada prueba tiene un resultado **estático y legible** (sin cámara lenta): "pantalla congelada con N+1 bloques" o "reinicio";
- **bisección solo cambiando la línea de arranque** (se regenera la imagen en el PC en minutos; sin CI), p. ej. `herostop=8` → 12 → 16 → 19;
- cada imagen sigue necesitando su autorización roja con hash (una por paso), pero el cuello de botella (el ojo) desaparece.
Sin la boot-arg el comportamiento no cambia (valor por defecto −1). Limitación: el slot 0 (entrada a `arm_init`) está antes de leer la boot-arg y no puede congelar; los slots 1-8 (`arm_init`) sí, tras `PE_init_platform` (se lee justo después).

## Pendiente
Si el Director prefiere repetir min6 con vídeo antes de seguir: su BOOT sigue siendo min6 y no hace falta escribir nada. La restauración del BOOT original sigue cubierta por D-0039.

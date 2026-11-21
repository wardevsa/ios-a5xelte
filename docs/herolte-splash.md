# Imagen de arranque (boot splash) del S7

Estado: **escrito y probado en el PC; nunca probado en el teléfono.** Es opcional y está apagado por defecto: sin `splash.bin` el cargador
se comporta como siempre.

## Qué es y qué no es
La manzana de iOS **no** la dibuja el kernel ni el cargador: la dibuja el propio iOS (backboardd) cuando arranca. Antes de ese momento la
pantalla muestra lo último que escribió el cargador (`xnu_boot`) y, después, el texto de la consola del kernel. Lo que se puede personalizar
es esa franja: **una imagen que sustituye a ese texto hasta que aparece la manzana**. No se cambia la manzana en sí.

## Cómo funciona
1. `tools/herolte-make-splash.py FOTO shim/herolte/splash.bin` convierte una imagen a 720×1280 RGB565 (con RLE si ayuda). El cargador la
   escala ×2 y la centra en el panel de 1440×2560. `--demo` genera una imagen de muestra; `--preview X.png` enseña cómo la decodificará
   el cargador; `--fit contain|cover|stretch` y `--bg RRGGBB` controlan el encaje.
2. `shim/herolte/build.sh` incrusta `splash.bin` en `xnu_boot.Image` si existe (si no, deja un bloque vacío). La imagen solo ocupa el
   `.rodata` del cargador; el resto del empaquetado no cambia. `splash.c` es un decodificador sin libc que respeta que el cargador corre
   con la MMU apagada (solo accesos alineados, lectura por bytes).
3. Con imagen puesta, el cargador **no escribe su texto de progreso** (para no ensuciarla). Si falla algo, `fail()` sigue mostrando el motivo.
4. Parche de kernel `0335`: con `herosplash=1` el kernel deja de pintar su consola de texto y sus marcadores de arranque temprano desde
   `arm_init`, así que la imagen sigue ahí hasta que iOS presenta la suya. El texto sigue llegando al registro persistente y **un pánico
   vuelve a dibujar**.

## Pruebas hechas (solo PC)
- `python3 shim/herolte/test_splash.py`: el decodificador en C frente a una referencia independiente en Python (ruido, zonas planas con RLE,
  distintas escalas y márgenes, 8 blobs inválidos, también bajo ASan/UBSan).
- El cargador se compila (clang+lld) con y sin imagen y pasa las comprobaciones de `build.sh` (cabecera arm64, `_image_end`, sin relocaciones
  absolutas). El parche 0335 aplica limpio sobre el árbol exacto del CI.
- **No** se ha compilado 0335 en XNU ni se ha visto nada en la pantalla del S7.

## Límite que hay que decidir: la línea de arranque
`herosplash=1` ocupa 13 caracteres (con el espacio) y la línea diaria mide 604 de 607. Hay que quitar algún argumento. Sin `herosplash=1`
la imagen se ve igualmente mientras el cargador salta al kernel, pero el texto del kernel la cubrirá en cuanto empiece a escribir.

## Riesgos
Con la consola muda, un **cuelgue sin pánico** deja solo la imagen: se pierde la pista visual que hoy dan las fotos de pantalla (el registro
persistente sigue ahí). Por eso es opcional. El cargador escribe unos 3,7 millones de píxeles con la MMU apagada (memoria de dispositivo):
se espera menos de un segundo, pero no está medido.

## Siguiente: animación
Una animación real exigiría un hilo del kernel que dibuje fotogramas hasta que iOS tome la pantalla (`AppleCLCD::present`), sobre el mismo
framebuffer y la misma ruta DECON que ya usa la consola. Es viable pero toca la ruta de pantalla del kernel y solo se puede validar en el
teléfono; los fotogramas tendrían que ir en el payload (todavía no hay raíz montada). Propuesta: primero validar la imagen estática.

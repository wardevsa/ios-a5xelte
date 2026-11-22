# Hito: iOS en pantalla con táctil en el Galaxy S7 (2026-11-15, min27)

**Observación del Director (L1, texto suyo, sin foto ni log todavía):** con `xnu-boot-v2-s7-min27-20261115.img` (BOOT escrito en D-0064): a los 30 s aparece el logo de Apple; después la pantalla de bloqueo de iOS con el fondo negro; el táctil funciona; se llega a la pantalla de inicio (home screen), «un poco lag pero ya va».

**Qué cambió respecto a min26 (donde la pantalla quedaba negra):** solo la línea de arranque: `+sweetfb_scale=1 sweetfb_lw=750 sweetfb_lh=1334` (sobre `sweetfb_native=1 a5fb_keep_on=1 a5fb_noconsole=1 heroring=0 herogpu=1 ...`). Mismo kernel (0332-0355). Causa probable (L2 + comentario del driver): el lienzo anunciado (1440x2560) no coincidía con el que pide iOS (750x1334, ADT iPhone 8) y «a mismatch left every swap layer empty» (E-0217).

**Qué NO está medido todavía:** fps reales, uso de CPU, temperatura, si la GPU participa (sweetfb_gpu no activo), el log persistente de esta prueba (pendiente de leer desde TWRP), el fondo de pantalla (negro: Metal; upstream usa `herosb=1`), Wi-Fi/energía/audio (desactivados a propósito).

Siguiente: leer el log de min27 (E-xxxx), registrar la evidencia, y mejorar fluidez (sweetfb_gpu=1, herosb, hero-run vía DROP) una cosa cada vez.

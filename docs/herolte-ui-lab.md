# S7UI lab: la pantalla de iPhone en un panel 9:16, con evidencia y no con adivinanzas

Estado a 2026-11-20. Decisión de partida del Director: gestos de iPhone (barra de abajo), una pantalla que llene el teléfono y una barra de estado correcta, "aunque se tarde".

## 1. El problema, en una frase
El panel del S7 es 1440×2560 (9:16). Un iPhone con gestos (X, XR, 11…) es 9:19,5 y UIKit decide su maquetación (muesca, barra de estado, márgenes seguros, indicador de inicio) por **tabla de modelos**, no por cálculo. No existe ninguna pantalla real "9:16 con gestos", así que alguna de las tres cosas tiene que ceder: la proporción, el aspecto de la barra de estado o la coherencia del modelo.

## 2. Lo medido hasta ahora (todo en `governance/data/evidence.toml`)
| Configuración | Resultado | Evidencia |
|---|---|---|
| 750×1334 + botón (iPhone 8) | Funciona, llena el panel, sin gestos | min100-min117 |
| 828×1792 (iPhone XR) + gestos, ADT con el lienzo antiguo | Líneas: UIKit maquetaba a 750×1334 dentro de un lienzo de 828×1792 (superficies de tamaños mezclados) | E-0341 |
| 828×1792 + gestos, ADT corregida (min119) | Sin líneas, gestos, muesca; franjas negras a los lados (proporción 9:19,5 sobre 9:16); el menú de arriba falla a ratos | E-0342 |
| 750×1334 + gestos (min121) | "Algunas cosas mal puestas, la barra de arriba no se ve" (el fallo de la barra roja conocido, rdar:45025538) | informe del Director |
| 828×1792 estirado a todo el panel (min120, `sweetfb_fill=1`) | Escrita; sin probar | parche 0483 |

## 3. Por qué no se puede seguir probando "a ojo"
Cada variante exige dos arranques y una descripción verbal ("se ve raro"). Eso no distingue una barra de estado invisible de una barra roja ni un gesto perdido de uno mal mapeado. El laboratorio quita al Director de la cadena de medida.

## 4. Arquitectura del laboratorio
1. **Capturas hechas por el propio teléfono** (parche 0484, `hsnap=<s>`): el kernel lee el búfer del panel que se está mostrando (tras un volcado de caché), lo reduce a 288×512 RGB565 y lo vuelca al registro en base64, una línea por fila. `tools/herolte-snap-decode.py` reconstruye los PNG y una hoja de contactos.
2. **Guion de gestos por la ruta táctil real** (`hs_swipe`, `sweet_hid_touch`): inicio, Centro de Control desde arriba a la derecha, Centro de Notificaciones desde arriba a la izquierda, gesto de inicio desde el borde inferior, cambio de página, tecla de inicio. Una captura tras cada paso.
3. **Generador de variantes** (`tools/herolte-ui-variant.py`): parte de la ADT que ya usan las imágenes y cambia solo lo que la pantalla necesita (lienzo, subtipo, escala, tipo de botón), imprime los argumentos de la línea de arranque que deben acompañarlo y reproduce byte a byte la ADT de min119 (comprobado). Una variante cuesta segundos y ninguna compilación del kernel.
4. **Ciclo:** el Director arranca una vez y no mira nada; yo leo las capturas y el registro unificado del teléfono (`tools/herolte-tracev3-strings.py`).

## 5. Hipótesis a descartar con el laboratorio, en orden
- H1: la barra de arriba de min121 no se ve porque UIKit pinta la barra roja o porque la deja fuera del lienzo. *Captura de la franja superior.*
- H2: el Centro de Control falla porque el gesto empieza en la franja negra o en el borde. *Compara min119 (franjas) con min120 (estirado) en la misma secuencia de gestos.*
- H3: la barra de estado vuelve a ser correcta con otro subtipo/escala (por ejemplo una escala de 3 con un lienzo de 1125×2436, el del iPhone X real, que cabe en el alto del panel con franjas). *Variante dedicada.*
- H4: un gancho de libheroapp en SpringBoard puede corregir la barra roja (cambiar la clase de barra de estado) sin tocar el modelo.

## 6. Criterios de éxito (medibles en las capturas)
1. La pantalla de inicio llena el panel o deja franjas solo si el Director las prefiere.
2. La barra de estado (hora, batería, red) es visible y no es roja.
3. El Centro de Control y el de Notificaciones se abren en 4 de 4 intentos del guion y se cierran con el gesto de abajo.
4. El gesto de inicio cierra una app y vuelve a los iconos.
5. Sin líneas ni superficies de tamaños mezclados en el registro.

## 7. Riesgos
- El volcado de capturas ocupa unos 400 KB de registro cada una: son siete por arranque y el anillo es de 4 MB.
- Las capturas reducen 5 veces: sirven para la maquetación, no para leer el texto.
- Estirar un lienzo 9:19,5 a 9:16 deforma un 21 %; es una preferencia del Director, no un defecto.
- La variante con el lienzo del iPhone X (1125×2436) cuesta 2,7 veces más píxeles que la actual de 750×1334.

## 8. Qué sigue
Imagen del laboratorio con la configuración de min120 y `hsnap`, leer las capturas, decidir entre H1-H4 y construir las variantes que hagan falta.

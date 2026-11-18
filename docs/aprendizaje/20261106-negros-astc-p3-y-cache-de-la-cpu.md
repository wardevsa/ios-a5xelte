# Informe de aprendizaje: por qué Safari y los fondos salían negros

> *Informe retroactivo (D-0091), reconstruido a partir de `HEROLTE_PROGRESS.md` y del historial de Git. Este trabajo de octubre y principios de noviembre lo hizo el proyecto upstream y es la base heredada; las medidas son las que ese registro anota.*

## 1. Qué hicimos y por qué
Con Wi-Fi y GPU funcionando, Safari y algunos fondos de pantalla salían **negros**. Se encontraron tres causas independientes (coherencia de caché, formatos de textura y espacio de color) y se corrigieron una a una.

## 2. El concepto
- **Coherencia entre CPU y GPU:** cuando otro proceso dibuja una superficie con la CPU, la GPU puede leer la RAM vieja si nadie limpia la caché.
- **ASTC:** formato de textura comprimida (aquí 4x4). La Mali T880 dice aceptarlo pero muestra negro; Mesa puede decodificar por CPU si se le oculta esa capacidad.
- **Gama de color (P3 y sRGB):** el iPhone X anuncia P3 y entonces WebKit dibuja en superficies de 10 bits (`w30r`); CoreAnimation sobre este OpenGL ES no las muestra.
- **MobileGestalt:** base de datos de capacidades de iOS; sus respuestas se guardan en una caché que persiste entre arranques.

## 3. La evidencia (medido)
- Registro del IOSurface: cada cuadro decía `0 textures refilled`. Tras sincronizar la caché cuando cambia el *seed*, hubo 20 limpiezas anotadas y **el negro seguía**: no era la única causa.
- Los fondos de iOS 16 llegan como **ASTC 4x4 (`0x93b0`, 750x1334)**. Tras ocultar los bits ASTC de `TEXTURE_FEATURES0` (`0xfffe003f`), no hubo subidas ASTC en ese arranque: sin confirmar.
- WebKit dibujaba en superficies `'w30r'` (750x1024) y `'b3a8'`, nunca BGRA/RGBA de 8 bits. Causa: `artwork-display-gamut = "P3"` en `/product`.
- Con el ADT en `"sRGB"`, PosterBoard pasó a `'BGRA'`, pero el proceso GPU de WebKit seguía en 10 bits: la respuesta P3 estaba en la **caché de MobileGestalt**. Se borra una vez al arrancar (`mgcache.gone`).
- Aparte: WebContent se lanzaba 56 veces y moría con `sig 11, pc 0x0` (JIT de selectores CSS). Con `herojit=1` y `MAP_JIT` rechazado, 5 lanzamientos y página negra.
- Resultado final de este informe: **sin resolver**; la causa del negro de Safari seguía abierta.

## 4. Cómo defenderlo
**Pregunta posible:** ¿Por qué la sincronización de caché no arregló el negro?
**Respuesta modelo:** Porque había varias causas. La caché era una (se limpió y se registró), pero los fondos ASTC y las superficies de 10 bits seguían mostrando negro por motivos distintos.

**Pregunta posible:** ¿Qué relación tiene el espacio de color con las superficies de 10 bits?
**Respuesta modelo:** Si el dispositivo anuncia P3, WebKit elige superficies de 10 bits para el color extendido; nuestra capa OpenGL ES no las muestra. Anunciando sRGB, dibuja en 8 bits.

**Pregunta posible:** ¿Por qué había que borrar una caché además de cambiar el ADT?
**Respuesta modelo:** Porque MobileGestalt guarda la respuesta ya calculada; sin borrarla, iOS seguiría usando P3 aunque el ADT diga sRGB.

## 5. Para profundizar
Parches `0316`-`0317`, `gpu/hakios-gl` (eagl.c), `tools/mkadt_herolte.py`, `HEROLTE_PROGRESS.md`.

# Informe de aprendizaje: hacer que la GPU Mali-T880 dibuje, paso a paso

> *Informe retroactivo (D-0091), reconstruido a partir de `HEROLTE_PROGRESS.md` y del historial de Git. Este trabajo de octubre y principios de noviembre lo hizo el proyecto upstream y es la base heredada; las medidas son las que ese registro anota.*

## 1. Qué hicimos y por qué
iOS dibujaba con la CPU y era lento. Para acelerarlo hacía falta que la GPU del S7 (Mali-T880) hiciera trabajo útil. No hay driver de Apple para ella, así que se programó desde cero, en escalones pequeños, hasta llegar a OpenGL con Mesa/Panfrost.

## 2. El concepto
- **Mali Midgard:** GPU con `job manager` que recibe **cadenas de trabajos** (tiler, vertex, fragment) y varios **shader cores** (12 en este modelo).
- **Tiler:** divide la pantalla en baldosas; su lista de polígonos exige una cabecera de tamaño concreto.
- **Descriptores de framebuffer:** SFBD (simple) y MFBD (multi-target). El segundo es el que Mesa usa en Midgard.
- **Coherencia de caché:** la GPU no ve las cachés de la CPU (`COHERENCY_FEATURES=0`). Si la CPU escribe y la GPU lee, hay que limpiar la caché antes.
- **Panfrost/Mesa:** driver abierto de la familia Mali. Aquí se compiló para iOS con una capa (HeroGPU) que traduce sus llamadas al driver del kernel.

## 3. La evidencia (medido)
- `GPU_ID=0x08802000` (T880 r2p0), 12 shaders (`0xff0f`), 1 tiler. El dominio G3D y los relojes ya venían encendidos de S-Boot.
- Primer trabajo: `WRITE_VALUE` sin fallos. Luego, con el descriptor MFBD y el tiler «desactivado con jerarquía», el fragment job escribió 256/256 píxeles y **pintó 1440x2560 de verde en 16,6 ms con un núcleo** (3,26 ms con los 12).
- Primer triángulo con shader ensamblado a mano; salía casi negro (`02020202`) por escribir r0 en fp32 con constantes fp16.
- Primera textura: una imagen de 180x320 ampliada 8x con filtro bilineal en 3,26 ms.
- iOS a través de la GPU (parche 0235): ~4,4 ms por cuadro, pero el cuello de botella pasó a CoreAnimation en la CPU (3-11 fps).
- HeroGPU (0239): WRITE_VALUE en 115 µs desde iOS; fragment clear 64x64 con 4096/4096 píxeles correctos en 197 µs.
- **Primer OpenGL en la Mali desde iOS:** `GL_RENDERER = Mali-T880 (Panfrost)`, 256x256 a **159 fps**. Hicieron falta configurar la GPU como Linux para un T880 y devolver a Mesa el tamaño real del heap del tiler (32 MiB, no 128): con el valor falso, el tiler escribía sobre otros buffers y daba `DATA_INVALID_FAULT`.
- Hipótesis anotada: que el descriptor «simple» de la T720 sirviera; era falsa.

## 4. Cómo defenderlo
**Pregunta posible:** ¿Por qué se avanzó con un triángulo y no con una app completa?
**Respuesta modelo:** Porque cada escalón (trabajo vacío, rellenar un píxel, un triángulo, una textura) aísla una sola causa de fallo; con una app completa un fallo no se podría atribuir a nada concreto.

**Pregunta posible:** ¿Qué significa que la GPU no sea coherente con la CPU?
**Respuesta modelo:** Que no consulta las cachés de la CPU; para que lea lo que la CPU escribió hay que vaciar (limpiar) esa caché a memoria antes. Si no, la GPU lee datos viejos.

**Pregunta posible:** ¿Cuál fue el fallo del tiler en OpenGL?
**Respuesta modelo:** Mesa pedía un heap de 128 MiB y el kernel solo daba 32 MiB sin decírselo; el tiler escribía fuera de su zona y corrompía otros buffers. Se arregló devolviendo el tamaño real.

## 5. Para profundizar
Parches `0225`-`0243`, `tools/herolte-midgard-shader.py`, `gpu/mesa`, `bsd/dev/herolte_gpu.c`.

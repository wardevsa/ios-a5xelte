# S7GE Metal: diseño de la base (2026-11-21)

**Decisión del Director (2026-11-21):** empezar por Metal como base sólida, no por parches de OpenGL ES. Motivo técnico que lo respalda (E-0369/E-0370): en iOS 16 CoreAnimation, CoreImage, SpriteKit/Jet y WebKit eligen Metal primero; la ruta GL es heredada y frágil (Jet recibe texto de sombreador nulo aunque los `.vsh/.fsh` se leen bien).

## Qué existe hoy
`MTLCreateSystemDefaultDevice()` devuelve `nil` en el teléfono (S7GE Lab). Debajo hay OpenGL ES 3.1 real sobre la Mali-T880 (Mesa/Panfrost) y un puente EAGL que ya dibuja (E-0359). Eso es el **backend** de Metal: no hay AGX.

## Arquitectura
`libheromtl.dylib` (se inserta con `libheroapp`, mismo mecanismo y bit 6 de AMFI):
1. **Entrada**: interposición de `MTLCreateSystemDefaultDevice`, `MTLCopyAllDevices` (y `MTLCopyAllDevicesWithObserver`) → un `HeroMTLDevice` que cumple `MTLDevice`.
2. **Objetos** (clases Objective-C que implementan los protocolos): `MTLDevice`, `MTLCommandQueue`, `MTLCommandBuffer`, `MTLBuffer` (memoria compartida de CPU: la GPU es de memoria unificada), `MTLTexture` (textura GL + copia CPU cuando haga falta), `MTLSamplerState`, `MTLLibrary`/`MTLFunction`, `MTLRenderPipelineState`, `MTLRenderCommandEncoder`, `MTLBlitCommandEncoder`, `MTLComputeCommandEncoder` (más tarde), `CAMetalLayer`/`CAMetalDrawable` (`nextDrawable` → textura respaldada por un IOSurface, `present` → `presentRenderbuffer`-equivalente del puente).
3. **Ejecución**: cada `MTLCommandBuffer` se reproduce en un hilo propio con un contexto GLES (`OSMesa` por el puente): un encoder de render = una pasada con FBO, `setVertexBuffer` → atributos, `drawPrimitives` → `glDrawArrays`. `commit`/`waitUntilCompleted`/handlers se respetan.
4. **Sombreadores (lo difícil)**: una app trae `.metallib` (contenedor `MTLB`, AIR = bitcode de LLVM). Sin compilador en el teléfono hay dos vías: (a) un **traductor AIR→GLSL ES** (en el teléfono: lector de bitcode LLVM + generador; es un proyecto grande), (b) **tabla de sombreadores conocidos**: reconocer por nombre de función y por hash los de Apple (SpriteKit `default.metallib`, CoreImage/CoreAnimation) y sustituirlos por GLSL escrito a mano. Se empieza por (b) y se medirá si hace falta (a). Es la decisión de coste más importante.

## Hitos (cada uno verificable en S7GE Lab)
- **M1** (siguiente): `MTLCreateSystemDefaultDevice() != nil`, `name`, `newCommandQueue`, `newBufferWithLength`, `newTextureWithDescriptor`; `CAMetalLayer.nextDrawable` y un pase de render que **limpia la pantalla a un color** y se presenta. Sin sombreadores.
- **M2**: un `MTLLibrary` y un par de funciones propias; triángulo con sombreadores de la tabla (b).
- **M3**: `default.metallib` de SpriteKit (traducción o tabla): Flappy Bird.
- **M4**: CoreImage/CoreAnimation sobre Metal (quitar los parches de CI de `libheroapp`).
- **M5**: cómputo y rendimiento.

## Riesgos honestos
- Es un proyecto de meses de trabajo normal; aquí se avanza por hitos medibles y cada uno puede dejar de ser viable (traducción AIR).
- Los protocolos de Metal son enormes; se implementan los usados y los demás responden «no soportado» con registro, nunca con valores inventados.
- Metal que ve el kernel de iOS (`IOAccelerator`/AGX) no existe: nada de esto toca el kernel salvo el bit 6 ya puesto.

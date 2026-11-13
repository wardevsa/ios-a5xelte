<!--
PROCEDENCIA: documento de dirección técnica de IOS S7 Graphics Engine (S7GE), recibido del responsable del proyecto (Pioxi) el 2026-11-13,
tal como se entregó (texto íntegro, sin editar). Es DISEÑO (nivel L0): no describe código existente salvo donde el propio texto lo dice.
Las afirmaciones sobre repositorios y estados de otros desarrolladores NO han sido verificadas por quien lo guarda; la contrastación con el árbol real
y con la red está en docs/S7GE_STATUS.md. Donde ambos difieren, manda S7GE_STATUS.md para el estado y este documento para la dirección.
-->

Voy a asumir la dirección técnica de **IOS S7 Graphics Engine** y tratarlo como un subsistema de ingeniería real, no como una idea experimental ni como una colección de parches.

Quiero que el resultado sea un documento de arquitectura que podamos utilizar para desarrollar, auditar, dividir tareas y tomar decisiones durante los próximos meses.

Hay una decisión que voy a establecer desde el principio:

**No vamos a construir un traductor de Metal que simplemente consiga dibujar triángulos. Vamos a construir una infraestructura gráfica completa, especializada en el Exynos 8890 y su Mali-T880 MP12, capaz de servir de puente entre los frameworks gráficos de iOS y el hardware real.**

Tampoco vamos a asumir que todo está por hacer. Primero identificaremos lo que ya existe, lo que funciona, lo que está parcialmente implementado y lo que podemos reutilizar de otros desarrolladores.

El macroinforme tendrá dos niveles:

- **Arquitectura objetivo:** cómo debería ser el sistema terminado.
- **Plan de implementación verificable:** qué podemos desarrollar realmente sobre nuestra versión de XNU, con qué dependencias y cómo demostrar que funciona.

No voy a presentar como implementado algo que todavía sea solamente diseño.

## **Primera auditoría: el repositorio real**

He localizado el repositorio público que corresponde al árbol de trabajo que aparece en nuestras conversaciones:

[**Xpl0itU/ios-a5xelte-wardevsa**](https://github.com/Xpl0itU/ios-a5xelte-wardevsa)

Esto es importante: ya no estamos diseñando sobre una arquitectura imaginaria. Tenemos un repositorio concreto contra el que contrastar las decisiones.

Su raíz contiene, entre otros elementos:

- `xnu/`: kernel y adaptaciones.
- `shim/`: componentes de compatibilidad.
- `userland/`: espacio de usuario.
- `tests/`: pruebas.
- `tools/`: herramientas.
- `docs/`: documentación.
- `A5XELTE_PROGRESS.md`: registro extenso de progreso.
- `NOTES.md`: notas técnicas acumuladas.
- `DISPLAY_APPS_PAYLOAD.md`: documentación relacionada con display y aplicaciones.

Voy a dar prioridad a `A5XELTE_PROGRESS.md`, `NOTES.md`, los parches de XNU y cualquier código existente relacionado con framebuffer, display, IOKit, GPU y memoria. Son los que pueden cambiar radicalmente el diseño que propongamos.

## **Hallazgo crítico: tenemos una base gráfica mucho más avanzada de lo que parecía**

He encontrado algo que cambia el planteamiento del motor.

El README actual documenta una implementación Samsung `a5xelte` (Galaxy A5 2016, Exynos 7580), con:

- XNU 8796 arrancando físicamente.
- Home Screen de iOS verificada.
- Touch y botones funcionales.
- Un puente `AppleCLCD` / `IOSurface`.
- Ejecución de trabajos de shaders de QuartzCore en una Mali-T720.
- Una batería de 21 pruebas privadas de GPU con referencias de píxeles, cuyos resultados se documentan como satisfactorios.

Pero el mismo README advierte que esto **no demuestra todavía renderizado completo del compositor de iOS, compatibilidad completa con Metal ni estabilidad de `backboardd`.**

Hay una distinción que no quiero perder:

> **Importante**
>
> El repositorio público que he localizado es la variante A5XELTE, no una demostración de que esas capacidades estén ya trasladadas al Galaxy S7 `herolte` con Exynos 8890.

Esto es una oportunidad excelente: podemos estudiar una implementación gráfica previa, identificar qué partes son reutilizables conceptualmente y diseñar una adaptación para la Mali-T880.

No vamos a empezar desde cero, pero tampoco vamos a copiar ciegamente un controlador de otra GPU.

He terminado una primera comparación técnica bastante profunda. Hay una conclusión importante antes de fijar la arquitectura:

**La referencia más valiosa que he encontrado no es un simple controlador OpenGL: es el trabajo de integración de Metal con Mali que existe en la línea A5XELTE de WardevSA.** Incluye investigación del ABI privado de Metal, traducción de shaders, construcción de descriptores Midgard, importación de IOSurface, colas, fences y pruebas de píxeles.

He localizado también una limitación documental que debemos resolver: el `main` público de tu cuenta, `darkcloud9998/ios-a5xelte`, todavía contiene esencialmente la base `ios-sweet`, sin los cambios `herolte` que hemos visto en nuestras conversaciones. No puedo inspeccionar los cambios locales que aún no se hayan publicado. Por eso separaré las conclusiones verificadas de la arquitectura propuesta para S7.

La referencia de implementación gráfica que vamos a estudiar es esta:

- [Repositorio WardevSA A5XELTE](https://github.com/Xpl0itU/ios-a5xelte-wardevsa).
- [Documentación técnica del port gráfico](https://github.com/Xpl0itU/ios-a5xelte-wardevsa/tree/main/docs).
- [Metal to Mali: shared lowering layer](https://github.com/Xpl0itU/ios-a5xelte-wardevsa/blob/main/docs/a5xelte-metal-mali-layer.md).
- [Frontera de integración Metal/iOS](https://github.com/Xpl0itU/ios-a5xelte-wardevsa/blob/main/docs/a5xelte-ios-metal-backend-boundary.md).
- [Auditoría del protocolo Panfrost](https://github.com/Xpl0itU/ios-a5xelte-wardevsa/blob/main/docs/a5xelte-panfrost-kernel-audit.md).

La diferencia de hardware es decisiva: el A5XELTE de esa implementación utiliza Mali-T720, mientras que nuestro objetivo es la Mali-T880 MP12. Ambas son Midgard, pero no comparten necesariamente la misma configuración, descriptores, erratas ni secuencias de inicialización.

A partir de aquí, establezco la especificación de arquitectura.

# IOS S7 GRAPHICS ENGINE

## Macroinforme de arquitectura, ingeniería, traducción de APIs y aceleración gráfica por hardware

**Proyecto:** IOS S7 / WardevSA\
**Subsistema:** IOS S7 Graphics Engine\
**Nombre interno:** S7GE\
**Hardware objetivo:** Samsung Galaxy S7 Exynos 8890 (`herolte`)\
**GPU:** ARM Mali-T880 MP12\
**Kernel objetivo:** XNU 8796.141.3\
**Sistema objetivo de referencia:** iOS 16.7.x\
**Estado del documento:** Especificación arquitectónica inicial\
**Clasificación:** Diseño técnico y plan de implementación\
**Dirección técnica:** Arquitectura S7GE

---

# PARTE I. VISIÓN GENERAL Y OBJETIVOS

## 1. Resumen ejecutivo

IOS S7 Graphics Engine (S7GE) será el subsistema responsable de proporcionar aceleración gráfica real al entorno iOS ejecutado sobre el Samsung Galaxy S7.

Su misión es conectar tres mundos que originalmente no fueron diseñados para trabajar juntos:

1. El ecosistema gráfico de Apple.
2. El kernel XNU y sus interfaces de aceleración.
3. La arquitectura de ejecución de la GPU ARM Mali-T880 MP12.

No pretendemos sustituir el sistema gráfico de Apple por una interfaz gráfica diferente. Queremos que los frameworks de iOS puedan utilizar las capacidades gráficas del dispositivo Samsung mediante una implementación de compatibilidad que respete sus contratos de funcionamiento.

El objetivo es que las aplicaciones y los servicios de iOS puedan:

- Crear dispositivos gráficos.
- Crear buffers y texturas.
- Compilar y seleccionar shaders.
- Crear pipelines gráficos.
- Enviar comandos de renderizado.
- Ejecutar operaciones de composición.
- Sincronizar CPU y GPU.
- Compartir recursos mediante IOSurface.
- Presentar los resultados en pantalla.
- Gestionar errores y recuperar recursos.

Todo ello utilizando la GPU física, no un renderizador de CPU que simule los resultados.

### 1.1. Objetivo final

La meta es conseguir que la GPU participe en la generación de los fotogramas de iOS, incluyendo SpringBoard, BackBoard, Core Animation y las aplicaciones compatibles.

No consideraremos que S7GE está terminado porque:

- Metal encuentre un dispositivo.
- OpenGL ES inicialice.
- Un shader compile.
- Una textura se importe.
- Un trabajo GPU termine.
- Un rectángulo aparezca en pantalla.

Cada uno es un hito independiente.

La definición de aceleración gráfica funcional exige que un trabajo real originado por el sistema de iOS llegue al hardware, produzca el resultado correcto, se sincronice y termine presentado en el panel.

## 2. Principios de diseño

S7GE se regirá por ocho principios.

**2.1. Hardware first**

Siempre que una operación pueda ejecutarse en la Mali-T880, se ejecutará en la GPU.

La CPU se reservará para:

- Preparación de comandos.
- Gestión de recursos.
- Compilación.
- Sincronización.
- Operaciones no compatibles.
- Recuperación y fallback.

No se permitirá utilizar un renderizador por software como ruta normal de composición una vez que exista una ruta GPU validada.

**2.2. Compatibilidad semántica**

No basta con que dos APIs permitan dibujar un triángulo.

Una operación traducida debe conservar su significado:

- Formato de textura.
- Precisión numérica.
- Orden de operaciones.
- Máscaras de escritura.
- Blend state.
- Profundidad.
- Stencil.
- Resolución.
- Viewport.
- Sincronización.
- Visibilidad de memoria.

Una traducción que produce una imagen aproximada, pero cambia el significado de la operación, no se considerará correcta.

**2.3. Traducción, no emulación**

No vamos a crear una GPU virtual completa ni emular un chip Apple AGX.

Vamos a proporcionar una implementación de las interfaces que espera iOS y traducir sus operaciones al modelo de ejecución real de Midgard.

**2.4. Aislamiento de subsistemas**

El controlador de GPU no dependerá directamente de DROP V2, UFS o HFS+.

Las interfaces entre subsistemas serán explícitas.

**2.5. Seguridad de memoria**

Ningún cliente podrá proporcionar libremente:

- Direcciones físicas.
- Direcciones de GPU.
- Entradas de tablas de páginas.
- Descriptores Mali arbitrarios.
- Registros MMIO.

El kernel será propietario de los recursos y construirá los trabajos que se ejecutan.

**2.6. Observabilidad**

Cada operación importante deberá poder diagnosticarse.

Un error no podrá reducirse a un simple `kIOReturnNotReady` si se conoce su causa real.

**2.7. Rendimiento medido**

No optimizaremos basándonos únicamente en intuiciones.

Registraremos latencias, utilización, consumo de CPU, tiempo de GPU, transferencias y frecuencia de presentación.

**2.8. Fallback seguro**

Si una operación no está soportada, debe rechazarse explícitamente o utilizar una ruta alternativa compatible.

Nunca debemos informar de que una operación ha terminado cuando realmente no ha realizado su trabajo.

---

# PARTE II. HARDWARE Y LÍMITES DE LA PLATAFORMA

## 3. Plataforma física

El Galaxy S7 Exynos utiliza:

| Componente              | Característica      |
| ----------------------- | ------------------- |
| SoC                     | Samsung Exynos 8890 |
| GPU                     | ARM Mali-T880 MP12  |
| Arquitectura GPU        | ARM Midgard v5      |
| CPU principal           | Exynos M1           |
| CPU secundaria          | Cortex-A53          |
| Memoria                 | 4 GB LPDDR4         |
| Pantalla                | Super AMOLED        |
| Resolución física       | 1440 × 2560         |
| Arquitectura del kernel | ARM64               |
| Almacenamiento          | UFS 2.0             |

La identificación de modelo y configuración del dispositivo debe mantenerse específica para `herolte` y no heredarse de las configuraciones del Exynos 7580.

Referencia de especificaciones: documentación del dispositivo [Galaxy S7 herolte](https://doc.e.foundation/devices/herolte/).

## 4. Mali-T880 MP12

La Mali-T880 es una GPU de arquitectura Midgard de quinta generación.

Esto es importante porque podemos aprovechar el conocimiento acumulado en el ecosistema Panfrost.

Mesa clasifica la T880 dentro de Midgard v5 y documenta soporte para OpenGL 3.1 y OpenGL ES 3.1 en su tabla de hardware. Esto demuestra que existe una base abierta para estudiar su ISA, descriptores, formatos y protocolos. No significa que podamos ejecutar directamente el controlador Linux dentro de XNU.

Referencia: documentación oficial de [Mesa Panfrost](https://docs.mesa3d.org/drivers/panfrost.html).

### 4.1. Bloques funcionales

S7GE debe considerar separadamente:

- Job Manager.
- Tiler.
- Fragment processors.
- Shader cores.
- Texture units.
- GPU MMU.
- Address Spaces.
- Command descriptors.
- GPU cache.
- Interrupt handling.
- Power domains.
- Clock domains.

La presencia de doce núcleos de ejecución gráficos no significa que debamos programarlos individualmente.

El controlador debe descubrir y configurar la topología real de la GPU.

### 4.2. Diferencia respecto a Mali-T720

El trabajo de A5XELTE constituye una referencia de enorme valor.

Sin embargo:

| Elemento              | A5XELTE           | IOS S7            |
| --------------------- | ----------------- | ----------------- |
| GPU                   | Mali-T720         | Mali-T880 MP12    |
| Midgard               | v4                | v5                |
| SoC                   | Exynos 7580       | Exynos 8890       |
| Configuración GPU     | MC2               | MP12              |
| Plataforma de memoria | Diferente         | Diferente         |
| PMU/CMU               | Exynos 7580       | Exynos 8890       |
| Interconexión         | Específica        | Específica        |
| Descriptor ABI        | Base reutilizable | Validación propia |
| Erratas               | T720              | T880              |

Podremos reutilizar conceptos y partes del trabajo de Mesa, pero no copiar las secuencias de inicialización del T720.

### 4.3. Investigación de hardware obligatoria

Antes de habilitar operaciones de escritura sobre los registros de la GPU debemos identificar:

1. Dirección física de la ventana MMIO.
2. Tamaño real del espacio de registros.
3. IRQ de Job Manager.
4. IRQ de MMU.
5. IRQ global de GPU.
6. Fuente de alimentación.
7. Reguladores.
8. Relojes.
9. Dominios de energía.
10. Dependencias de interconexión.
11. Frecuencias y OPP.
12. Configuración de memoria.
13. Estado de GPU heredado del bootloader.

La secuencia de alimentación es especialmente delicada.

No debemos utilizar registros del Exynos 7580 como si pertenecieran al Exynos 8890.

Tampoco debemos habilitar una frecuencia superior sin verificar primero la tensión y los límites térmicos correspondientes.

## 5. Controlador de pantalla frente a GPU

Esta distinción es fundamental.

La Mali-T880 renderiza imágenes, pero no es el controlador físico que escanea el panel.

La ruta de visualización requiere dos subsistemas:

**Renderizado:**

Mali-T880 produce los píxeles.

**Presentación:**

El controlador de pantalla del Exynos transmite los píxeles al panel mediante la interfaz correspondiente.

Por tanto, S7GE debe comunicarse con el subsistema de display de XNU.

No debemos mezclar el trabajo de renderizado con el trabajo de scanout.

Un fotograma puede estar correctamente renderizado y no aparecer en pantalla por un error de presentación.

También puede aparecer en pantalla un fotograma que ha sido generado completamente por CPU.

Son situaciones diferentes.

---

# PARTE III. ARQUITECTURA GENERAL

## 6. Arquitectura por capas

La arquitectura propuesta será la siguiente:

```
                  APLICACIONES iOS
                         |
                         v
       Core Animation / Core Graphics / QuartzCore
                         |
                         v
                  METAL FRAMEWORK
                         |
                         v
              S7 METAL COMPATIBILITY
                         |
                         v
                 S7GE USERLAND
                         |
             +-----------+-----------+
             |                       |
             v                       v
       Shader Compiler          Resource Runtime
             |                       |
             +-----------+-----------+
                         |
                         v
                  S7GE KERNEL ABI
                         |
                         v
                 S7GE IOKIT DRIVER
                         |
             +-----------+-----------+
             |           |           |
             v           v           v
          GPU MMU     JOB QUEUE    MEMORY
             |           |           |
             +-----------+-----------+
                         |
                         v
                  MALI-T880 MP12
                         |
                         v
                 OUTPUT / SCANOUT
                         |
                         v
                  DISPLAY ENGINE
                         |
                         v
                     PANEL
```

La arquitectura estará dividida en cuatro grandes dominios:

1. Compatibilidad de API.
2. Traducción y compilación.
3. Ejecución GPU.
4. Presentación.

## 7. Componentes oficiales de S7GE

Establezco la siguiente nomenclatura.

| Identificador | Subsistema                    |
| ------------- | ----------------------------- |
| S7GPU         | Controlador físico Mali-T880  |
| S7MMU         | Gestión de memoria GPU        |
| S7JMQ         | Job Manager y colas           |
| S7FENCE       | Sincronización y finalización |
| S7MEM         | Gestión de recursos gráficos  |
| S7IOS         | Integración IOSurface         |
| S7MCL         | Metal Compatibility Layer     |
| S7GTE         | Graphics Translation Engine   |
| S7SHC         | Shader Compiler               |
| S7GL          | Backend OpenGL ES             |
| S7PPL         | Pipeline Manager              |
| S7COMP        | Integración de composición    |
| S7PRES        | Presentación y scanout        |
| S7DVFS        | Frecuencia y energía          |
| S7TRACE       | Diagnóstico y telemetría      |

Estos identificadores son nombres de arquitectura propuestos. No implican que existan ya archivos con esos nombres.

---

# PARTE IV. METAL COMPATIBILITY LAYER

## 8. La decisión principal: Metal será la interfaz superior

Mi decisión técnica es utilizar Metal como interfaz principal de integración con iOS.

No vamos a diseñar el proyecto alrededor de OpenGL ES y después intentar introducir Metal encima.

La razón es que el sistema de iOS utiliza Metal y sus interfaces privadas de aceleración para comunicar el trabajo gráfico al hardware.

Core Animation y otros componentes pueden acceder a servicios de aceleración a través de interfaces que no se reducen a OpenGL ES.

Por eso necesitamos una implementación compatible con el contrato de Metal que espera la versión concreta de iOS.

### 8.1. Qué será S7MCL

S7MCL implementará una capa de compatibilidad para las interfaces gráficas de Apple.

Sus responsabilidades serán:

- Exponer el dispositivo gráfico.
- Informar de las capacidades soportadas.
- Crear command queues.
- Crear command buffers.
- Gestionar buffers.
- Gestionar texturas.
- Gestionar samplers.
- Crear render pipelines.
- Gestionar render encoders.
- Gestionar recursos compartidos.
- Traducir operaciones.
- Devolver errores reales.
- Gestionar finalización de comandos.

No será una implementación ficticia que devuelva valores positivos para conseguir que las aplicaciones continúen.

### 8.2. Descubrimiento de dispositivo

La investigación realizada en el port A5XELTE identificó una ruta importante de descubrimiento en la versión inspeccionada de Metal:

1. Metal busca servicios de tipo `IOAcceleratorES`.
2. Consulta propiedades como `MetalPluginName`.
3. Localiza un bundle de implementación.
4. Obtiene su clase de dispositivo.
5. Inicializa la implementación mediante `initWithAcceleratorPort:`.
6. Comprueba interfaces de `MTLDevice` y SPI privada.

Esto tiene una consecuencia arquitectónica enorme:

**No basta con registrar un servicio llamado IOAcceleratorES.**

Debe ser una implementación real de la clase esperada, con un contrato funcional de dispositivo y cliente.

El código de AGXMetalA11 no es un controlador genérico que podamos conectar a la Mali-T880.

Tampoco debemos intentar convertirlo en uno mediante simples cambios de nombres.

### 8.3. Bundle propio

La propuesta es crear un bundle de implementación Mali específico.

Nombre provisional:

`S7MaliMetal.bundle`

Su clase principal sería:

`S7MaliDevice`

Clases adicionales:

- S7MaliCommandQueue
- S7MaliCommandBuffer
- S7MaliRenderPipeline
- S7MaliComputePipeline
- S7MaliBuffer
- S7MaliTexture
- S7MaliSampler
- S7MaliLibrary
- S7MaliFence
- S7MaliEvent

La interfaz concreta dependerá de los símbolos, estructuras y métodos privados que podamos verificar en el dyld shared cache de nuestro build de iOS.

No vamos a inventar selectores.

### 8.4. Compatibilidad de versiones

S7MCL tendrá una versión de ABI propia.

Ejemplo:

```
S7MCL_ABI_MAJOR = 1
S7MCL_ABI_MINOR = 0
S7MCL_PROTOCOL  = 1
S7MCL_DEVICE    = Mali-T880
S7MCL_TARGET    = herolte
```

Cada cambio incompatible deberá incrementar la versión principal.

Las características opcionales se anunciarán mediante capacidades.

---

# PARTE V. GRAPHICS TRANSLATION ENGINE

## 9. S7GTE: el núcleo intelectual del proyecto

Esta será una de las partes más importantes de S7GE.

S7GTE será el encargado de traducir las operaciones que llegan desde el entorno de Metal a una representación intermedia que podamos ejecutar en la Mali-T880.

No quiero que cada función de Metal tenga una traducción artesanal e independiente.

Quiero una representación intermedia común.

La llamaremos:

**S7 Graphics Intermediate Representation (S7GIR).**

### 9.1. Por qué necesitamos una IR

Metal describe operaciones gráficas mediante objetos de alto nivel:

- Texturas.
- Buffers.
- Pipelines.
- Encoders.
- Draw calls.
- Recursos.
- Estados.
- Dependencias.

Midgard trabaja con:

- Descriptores.
- Direcciones GPU.
- Job headers.
- Shader binaries.
- Framebuffer descriptors.
- Polygon lists.
- Texture descriptors.
- Varying descriptors.
- Job dependencies.

Entre ambos modelos existe una diferencia considerable.

S7GIR permitirá separar la API de origen de la implementación física.

### 9.2. Tipos de nodos S7GIR

La IR tendrá inicialmente estas categorías:

| Categoría  | Contenido                 |
| ---------- | ------------------------- |
| Device     | Capacidades y dispositivo |
| Resource   | Buffer y textura          |
| Shader     | Programa compilado        |
| Pipeline   | Estado de ejecución       |
| RenderPass | Adjuntos y operaciones    |
| Draw       | Geometría y parámetros    |
| Blit       | Copias y conversiones     |
| Barrier    | Dependencias              |
| Fence      | Sincronización            |
| Present    | Entrega al display        |

### 9.3. Ejemplo conceptual

Una aplicación realiza:

```
CreateTexture
CreateBuffer
CreatePipeline
CreateCommandBuffer
BeginRenderPass
BindPipeline
BindTexture
Draw
EndRenderPass
Commit
```

S7GTE construye una representación interna:

```
RESOURCE_CREATE
BUFFER_CREATE
PIPELINE_RESOLVE
COMMAND_BEGIN
RENDER_TARGET_BIND
TEXTURE_BIND
DRAW_TRANSLATE
RENDER_END
SUBMIT
FENCE_WAIT
```

Después el backend convierte esa representación en los descriptores específicos de Midgard.

### 9.4. Validación semántica

Cada operación debe tener:

- Tipo.
- Tamaño.
- Alineación.
- Formato.
- Estado.
- Dependencias.
- Permisos.
- Límites.
- Resultado esperado.

Si una operación no se puede representar correctamente, debe fallar explícitamente.

No debemos modificar silenciosamente la semántica de una aplicación para conseguir que el trabajo termine.

---

# PARTE VI. SHADER COMPILER

## 10. S7SHC: compilador gráfico

La traducción de shaders será una de las partes más difíciles.

Un pipeline Metal no contiene simplemente una función de dibujo.

Incluye funciones compiladas, especializaciones, formatos, recursos, atributos, constantes y estados asociados.

La Mali-T880 necesita instrucciones Midgard compatibles.

Por tanto, necesitamos una ruta de compilación.

### 10.1. Pipeline de compilación

La arquitectura propuesta:

```
Metal Shader Library
          |
          v
    AIR Extraction
          |
          v
    AIR Translator
          |
          v
       SPIR-V
          |
          v
       NIR IR
          |
          v
    S7GTE Lowering
          |
          v
    Midgard Compiler
          |
          v
    Mali Binary
          |
          v
    Pipeline Linking
```

Esta ruta está basada en el trabajo de traducción observado en la implementación A5XELTE.

Pero debemos verificar qué partes pueden utilizarse para la Mali-T880 y qué partes son específicas del T720.

### 10.2. AIR

AIR es la representación intermedia utilizada por el entorno de compilación de Apple.

No vamos a suponer que todos los shaders de iOS pueden convertirse automáticamente.

Necesitamos investigar:

- Versiones de AIR.
- Funciones.
- Tipos.
- Constantes.
- Operaciones.
- Recursos.
- Especializaciones.
- Instrucciones sin equivalencia directa.

### 10.3. SPIR-V

SPIR-V puede servir como representación de transición.

Pero no debemos asumir que convertir AIR a SPIR-V significa que el shader ya está listo para ejecutarse.

Hay diferencias de semántica, precisión y recursos.

El traductor deberá preservar:

- Tipos.
- Interpolación.
- Layout.
- Acceso a buffers.
- Texturas.
- Samplers.
- Operaciones matemáticas.
- Built-ins.
- Variables especiales.

### 10.4. NIR

NIR nos ofrece una infraestructura de optimización y lowering procedente del ecosistema Mesa.

No necesitamos desarrollar desde cero todas las transformaciones de shaders.

Podemos reutilizar las partes apropiadas de Mesa y su backend Midgard, siempre respetando sus interfaces y licencias.

### 10.5. Backend Midgard

El backend final generará código ejecutable para la Mali-T880.

Necesitará información real de:

- Shader stage.
- Registros.
- Varyings.
- Uniforms.
- Texturas.
- Samplers.
- Work registers.
- TLS/WLS cuando proceda.
- Instrucciones especiales.
- Recursos auxiliares.

### 10.6. Especializaciones

No debemos crear un compilador que solamente admita una lista de shaders conocidos para siempre.

La arquitectura deberá separar:

1. Traducción general.
2. Especialización de funciones.
3. Enlace de pipelines.
4. Validación de recursos.
5. Generación de descriptores.

Podemos empezar con perfiles conocidos y ampliar progresivamente.

La diferencia es que los perfiles serán una herramienta para controlar la cobertura, no una limitación estructural permanente.

### 10.7. Caché de shaders

S7SHC mantendrá una caché persistente de compilación.

La identidad de cada entrada deberá incluir:

- Hash de AIR.
- Hash del código traducido.
- Versión del compilador.
- Versión del backend.
- Modelo GPU.
- Revisión GPU.
- Estado de especialización.
- Layout de recursos.
- Estado de pipeline.

No reutilizaremos un shader compilado para una configuración diferente sin demostrar que sus contratos son equivalentes.

---

# PARTE VII. BACKEND OPENGL ES

## 11. S7GL: OpenGL ES no desaparece

Aunque Metal sea nuestra interfaz principal, OpenGL ES seguirá teniendo un papel importante.

Sin embargo, establezco una distinción:

**OpenGL ES será una API adicional soportada por la infraestructura gráfica, no el traductor obligatorio de Metal.**

¿Por qué?

Porque Metal y OpenGL ES tienen modelos de ejecución diferentes.

OpenGL ES utiliza un modelo de estado y contexto diferente al de Metal.

Metal tiene command buffers, command encoders, recursos y sincronización explícita.

Traducir Metal a OpenGL ES podría funcionar para determinadas operaciones, pero introduce limitaciones importantes:

- Sincronización.
- Resource hazards.
- Compute.
- Gestión de memoria.
- Formatos.
- Render passes.
- Argument buffers.
- Eventos.
- Operaciones especializadas.

### 11.1. Arquitectura de S7GL

S7GL utilizará S7GIR para ejecutar las operaciones que entren desde OpenGL ES.

El flujo será:

```
OpenGL ES API
      |
      v
S7GL Frontend
      |
      v
     S7GIR
      |
      v
Midgard Backend
      |
      v
Mali-T880
```

Así evitamos mantener dos implementaciones físicas diferentes del mismo controlador.

### 11.2. Objetivo de compatibilidad

La referencia de capacidades será OpenGL ES 3.1 cuando la combinación de hardware, backend y funciones realmente implementadas lo permita.

No anunciaremos una versión de API por el mero hecho de que el chip aparezca en una tabla de soporte de Mesa.

El nivel de compatibilidad anunciado será la intersección de:

- Capacidades físicas.
- Funciones del compilador.
- Funciones del backend.
- Formatos.
- Sincronización.
- Pruebas superadas.

---

# PARTE VIII. KERNEL Y CONTROLADOR GPU

## 12. S7GPU: controlador físico

Este subsistema será el propietario de la Mali-T880.

Su ubicación propuesta es:

```
xnu/iokit/Kernel/arm/
```

Con archivos iniciales conceptuales:

```
S7GPU.cpp
S7GPU.h
S7GPURegisters.h
S7GPUPower.cpp
S7GPUInterrupts.cpp
S7GPUJobs.cpp
S7GPUDiagnostics.cpp
```

No son todavía rutas existentes.

### 12.1. Inicialización

La inicialización deberá realizarse mediante fases.

**Fase A: identificación**

- Obtener recursos desde ADT.
- Comprobar la identidad del dispositivo.
- Leer GPU_ID.
- Verificar revisión.
- Leer características disponibles.

**Fase B: seguridad**

- Comprobar el estado de alimentación.
- Comprobar clocks.
- Validar ventanas MMIO.
- Confirmar que las dependencias de bus están satisfechas.

**Fase C: preparación**

- Establecer el estado conocido del hardware.
- Inicializar la MMU.
- Preparar el Job Manager.
- Configurar las interrupciones cuando exista una ruta GIC validada.

**Fase D: disponibilidad**

- Registrar el dispositivo.
- Publicar las capacidades reales.
- Habilitar clientes autorizados.
- Mantener disponible el fallback de CPU.

### 12.2. Política de fallo

Cualquier fallo durante la inicialización deberá impedir la publicación de un dispositivo plenamente operativo.

Un servicio que solo ha registrado su presencia no puede anunciarse como acelerador funcional.

## 13. S7MMU: gestión de memoria GPU

La MMU de la Mali no es equivalente a la MMU de la CPU ARM64.

Debemos gestionar dos espacios de direcciones:

- Direcciones virtuales de CPU.
- Direcciones virtuales de GPU.

S7MMU será responsable de traducir las direcciones que utiliza la GPU hacia las páginas físicas correspondientes.

### 13.1. Responsabilidades

- Crear tablas de páginas.
- Mapear recursos.
- Validar permisos.
- Gestionar actualizaciones.
- Realizar invalidaciones TLB.
- Mantener las páginas durante DMA.
- Retirar mappings únicamente cuando sea seguro.
- Gestionar errores de traducción.
- Recuperar o aislar contextos.

### 13.2. Recursos no contiguos

No debemos asumir que todos los IOSurface tienen backing físico contiguo.

La capa de importación tendrá que inspeccionar las páginas reales y construir el mapping GPU correspondiente.

Nunca se utilizará una dirección GPU inventada a partir de un puntero de CPU.

### 13.3. Coherencia

Debemos separar tres mecanismos:

1. Coherencia de caché CPU.
2. Coherencia de caché GPU.
3. Invalidación de traducciones MMU.

Una barrera de CPU no sustituye una invalidación TLB.

Una finalización de job no sustituye necesariamente la operación de mantenimiento de caché que requiere el acceso posterior de CPU.

### 13.4. Retención

Los recursos utilizados por un trabajo deberán permanecer vivos hasta que exista una finalización verificable.

Si hay un timeout ambiguo, se conservarán las páginas y descriptores potencialmente visibles por DMA.

La seguridad de memoria tiene prioridad sobre liberar memoria rápidamente.

## 14. S7JMQ: Job Manager y ejecución

S7JMQ será la infraestructura de envío de trabajos a la GPU.

La arquitectura de Midgard se basa en trabajos que utilizan descriptores y estados específicos del hardware.

El controlador deberá generar trabajos válidos para el modelo T880.

### 14.1. Tipos de trabajos

Inicialmente:

- Vertex.
- Tiler.
- Fragment.
- Blit mediante shaders.
- Clear.
- Operaciones auxiliares compatibles.

La arquitectura no presupone que todos los tipos de trabajo tengan que exponerse directamente a los clientes.

### 14.2. Secuenciación

Los trabajos tendrán dependencias explícitas.

Ejemplo:

```
VERTEX
  |
  v
TILER
  |
  v
FRAGMENT
  |
  v
FENCE
  |
  v
RESOURCE RELEASE
```

Cada transición deberá estar verificada.

No podremos reutilizar un descriptor que la GPU todavía esté leyendo.

### 14.3. Colas

Habrá una cola física de hardware gestionada de forma centralizada y una capa lógica de colas por cliente.

Inicialmente priorizaremos:

- Una única propiedad segura del Job Manager.
- Una cola de envío serializada.
- Fences monotónicos.
- Esperas acotadas.
- Diagnóstico de fallos.
- Retención de recursos.

Más adelante podremos introducir concurrencia y planificación avanzada.

No debemos intentar implementar un scheduler complejo antes de tener una ruta de ejecución estable.

## 15. S7FENCE: sincronización

La sincronización será un componente independiente.

Cada operación aceptada tendrá un identificador de finalización.

Una fence solo se considerará completada cuando:

1. El hardware haya terminado el trabajo.
2. No exista un error de job.
3. No exista un error MMU.
4. El estado de ejecución sea terminal.
5. Se hayan realizado las operaciones de coherencia requeridas.
6. Los resultados estén disponibles para el consumidor.

Un timeout no significa que la GPU haya terminado.

Una interrupción recibida tampoco significa necesariamente que el resultado sea correcto.

### 15.1. Fallback inicial

La primera implementación puede utilizar polling acotado mientras desarrollamos y verificamos las rutas de interrupción.

El objetivo final será disponer de:

- Interrupciones reales.
- Completion callbacks.
- Fences.
- Cancelación segura.
- Recuperación.
- Gestión de timeouts.

No mantendremos polling agresivo permanente como arquitectura definitiva.

---

# PARTE IX. RECURSOS E IOSURFACE

## 16. S7MEM

S7MEM gestionará todos los recursos gráficos.

No queremos que cada subsistema cree y destruya buffers de manera independiente.

### 16.1. Tipos

- Buffers de vértices.
- Buffers de índices.
- Uniform buffers.
- Storage buffers.
- Texturas.
- Render targets.
- Depth buffers.
- Stencil buffers.
- Scratch buffers.
- Shader storage.
- Recursos temporales.

### 16.2. Alocación

Cada recurso tendrá:

- Identificador.
- Generación.
- Tamaño lógico.
- Tamaño asignado.
- Alineación.
- Formato.
- Uso.
- Propietario.
- Estado de mapping.
- Última fence.
- Estado de coherencia.

### 16.3. Pools

Se crearán pools de recursos para evitar asignaciones repetidas.

Los pools deberán tener límites y políticas de presión.

No permitiremos que un cliente mantenga recursos ilimitados.

## 17. S7IOS: integración IOSurface

IOSurface será una pieza central de la arquitectura.

Es el mecanismo que permite compartir recursos gráficos entre diferentes componentes del sistema.

En nuestro caso, es especialmente importante para conectar:

- BackBoard.
- Core Animation.
- QuartzCore.
- Metal.
- S7GE.
- Display.

### 17.1. Importación

La importación deberá validar:

- Mach port.
- Propietario.
- Formato.
- Dimensiones.
- Stride.
- Número de planos.
- Páginas físicas.
- Permisos.
- Tamaño total.

### 17.2. Vida útil

Una IOSurface no podrá liberarse mientras un job la esté utilizando.

Su referencia se mantendrá hasta que termine la última operación que dependa de ella.

### 17.3. Formatos iniciales

Propondría empezar con:

- BGRA8.
- RGBA8.
- R8.
- RG8.
- R32Float.
- RGBA16Float.

No significa que todos estén ya implementados.

Cada formato deberá tener:

- Identificación.
- Tamaño por elemento.
- Alineación.
- Stride.
- Swizzle.
- Layout.
- Reglas de lectura y escritura.
- Conversión cuando corresponda.

### 17.4. Zero-copy

El objetivo de largo plazo será reducir al mínimo las copias entre CPU, IOSurface, GPU y scanout.

Pero zero-copy no significa simplemente compartir un puntero.

Exige:

- Mapping compatible.
- Propiedad de memoria.
- Coherencia.
- Retención.
- Sincronización.
- Compatibilidad de formato.
- Compatibilidad del layout.

Primero garantizaremos que los recursos se comparten correctamente. Después optimizaremos las transferencias.

---

# PARTE X. PIPELINES Y ESTADOS GRÁFICOS

## 18. S7PPL: Pipeline Manager

El Pipeline Manager será responsable de construir y mantener los estados de ejecución.

Un pipeline no es solamente una pareja de shaders.

Debe representar el conjunto completo de condiciones que determina el resultado gráfico.

### 18.1. Render pipeline

Incluye:

- Vertex function.
- Fragment function.
- Vertex descriptor.
- Attachment formats.
- Blend state.
- Write masks.
- Sample count.
- Rasterization state.
- Primitive topology.
- Resource bindings.

### 18.2. Depth y stencil

Debemos incluir desde el diseño:

- Depth compare.
- Depth write.
- Stencil operations.
- Stencil masks.
- Stencil reference.
- Attachment formats.

Podremos posponer la implementación, pero no diseñar una arquitectura que obligue a rehacer el pipeline cuando aparezcan.

### 18.3. Blend state

El blend state requiere una traducción particularmente rigurosa.

Debe preservar:

- Operación RGB.
- Operación alpha.
- Factores RGB.
- Factores alpha.
- Write masks.
- Dependencias con el destino.
- Necesidad de lectura previa del destino.

No vamos a limitar la implementación a source-over y screen.

Esas operaciones pueden servir para las primeras pruebas, pero el objetivo será representar las ecuaciones de Metal y traducirlas a las capacidades reales de Midgard.

Cuando una ecuación no pueda representarse mediante el hardware, se evaluará su lowering a shader.

No se aceptará una aproximación silenciosa.

---

# PARTE XI. COMPOSICIÓN DE IOS

## 19. S7COMP: Core Animation y BackBoard

Esta es la razón por la que estamos construyendo todo el sistema.

No queremos una GPU que solamente ejecute pruebas independientes.

Queremos que los fotogramas del propio sistema iOS se generen mediante aceleración.

### 19.1. Ruta objetivo

```
SpringBoard
     |
     v
BackBoard
     |
     v
Core Animation
     |
     v
QuartzCore
     |
     v
IOSurface / Metal
     |
     v
S7MCL
     |
     v
S7GTE
     |
     v
S7GPU
     |
     v
Mali-T880
```

### 19.2. Operaciones de composición

S7COMP deberá poder soportar progresivamente:

- Limpieza de attachments.
- Renderizado de capas.
- Transformaciones.
- Escalado.
- Texturas.
- Alpha blending.
- Máscaras.
- Blur.
- Downsampling.
- Sombras.
- Path rendering.
- Composición multicapa.
- Presentación.

### 19.3. El problema del destino

Una de las cuestiones más importantes es conservar los píxeles anteriores cuando una operación solo modifica una parte de la pantalla.

No podemos reemplazar siempre todo el framebuffer.

Necesitamos comprender:

- Qué attachment se modifica.
- Qué regiones permanecen intactas.
- Qué canales se escriben.
- Qué operaciones leen el destino.
- Qué orden de composición debe respetarse.

Esto afecta directamente a la corrección de Core Animation.

### 19.4. Frames parciales

La arquitectura debe admitir:

- Full-frame rendering.
- Partial updates.
- Dirty rectangles.
- Clipped rendering.
- Múltiples layers.
- Múltiples attachments.

El objetivo no será copiar todo el framebuffer en cada operación si podemos actualizar únicamente las regiones modificadas.

---

# PARTE XII. PRESENTACIÓN Y DISPLAY

## 20. S7PRES

S7PRES será el puente entre el resultado final de GPU y el controlador de pantalla.

Sus funciones:

- Recibir el framebuffer final.
- Verificar la finalización de GPU.
- Gestionar la propiedad del buffer.
- Esperar al momento de presentación.
- Sincronizar con VSync.
- Entregar el buffer al controlador de pantalla.
- Evitar tearing.
- Gestionar buffers pendientes.
- Recuperarse de errores.

### 20.1. Triple buffering

Evaluaremos triple buffering como arquitectura de presentación.

Los buffers serán:

1. Front buffer.
2. Back buffer.
3. Pending buffer.

No será obligatorio utilizar siempre tres buffers.

La cantidad dependerá de la latencia, memoria disponible y comportamiento del compositor.

### 20.2. VSync

La presentación deberá estar sincronizada con el panel.

No queremos que la GPU finalice correctamente y que el display lea el buffer mientras todavía está siendo modificado.

La propiedad del buffer tendrá que estar definida en todo momento.

### 20.3. Tearing

Se considerará un error de presentación cualquier situación en la que el panel combine regiones de dos fotogramas diferentes por una transferencia fuera de sincronización.

No se considerará aceptable como comportamiento normal.

---

# PARTE XIII. RENDIMIENTO Y OPTIMIZACIÓN

## 21. S7DVFS

La Mali-T880 tiene que trabajar dentro de unos límites eléctricos y térmicos adecuados.

No vamos a fijar una frecuencia máxima arbitraria.

S7DVFS deberá coordinarse con:

- Reguladores.
- Clocks.
- PMU.
- Control térmico.
- Frecuencias disponibles.
- Estado de utilización.
- Consumo.
- Temperatura.

### 21.1. Política de frecuencia

La frecuencia deberá adaptarse a la carga.

No necesitamos la máxima frecuencia cuando el sistema está mostrando una pantalla estática.

Tampoco queremos una GPU que permanezca en una frecuencia demasiado baja cuando se está ejecutando una transición compleja.

### 21.2. Optimización de comandos

S7GTE deberá:

- Agrupar operaciones compatibles.
- Reducir cambios de estado.
- Reutilizar pipelines.
- Reutilizar recursos.
- Evitar conversiones innecesarias.
- Evitar copias intermedias.
- Minimizar sincronizaciones.
- Reducir la presión sobre la CPU.

### 21.3. Optimización de memoria

La memoria es un recurso crítico.

La GPU comparte el sistema de memoria con CPU y otros dispositivos.

Debemos medir:

- Ancho de banda.
- Latencia.
- Transferencias.
- Cache misses cuando puedan medirse.
- Coste de mapping.
- Coste de invalidación.
- Tiempo de preparación.
- Tiempo de ejecución.

### 21.4. Objetivos de rendimiento

Como objetivos de diseño, no como resultados prometidos:

| Métrica        | Objetivo                                     |
| -------------- | -------------------------------------------- |
| Presentación   | 60 Hz cuando el panel y la carga lo permitan |
| Tearing        | Ninguno en la ruta normal                    |
| CPU compositor | Reducir sustancialmente su carga             |
| GPU jobs       | Finalización verificable                     |
| Memoria        | Sin fugas sostenidas                         |
| Latencia       | Medición por percentiles                     |
| Estabilidad    | Pruebas prolongadas                          |
| Temperatura    | Sin throttling térmico descontrolado         |

Una presentación a 60 Hz no significa que todas las operaciones tengan que completarse en 16,67 ms individualmente.

Debemos medir el presupuesto completo del fotograma.

---

# PARTE XIV. DIAGNÓSTICO Y OBSERVABILIDAD

## 22. S7TRACE

No desarrollaremos un controlador opaco.

S7TRACE registrará los eventos relevantes mediante estructuras compactas.

### 22.1. Eventos

Ejemplos:

```
S7GPU: DEVICE_DISCOVERED
S7GPU: POWER_STATE_VERIFIED
S7GPU: MMU_READY
S7GPU: QUEUE_READY

S7MEM: RESOURCE_CREATED
S7MEM: RESOURCE_IMPORTED
S7MEM: RESOURCE_RELEASED

S7SHC: FUNCTION_REQUESTED
S7SHC: COMPILATION_STARTED
S7SHC: COMPILATION_COMPLETED
S7SHC: COMPILATION_FAILED

S7JMQ: JOB_SUBMITTED
S7JMQ: JOB_COMPLETED
S7JMQ: JOB_FAULT

S7FENCE: FENCE_SIGNALLED
S7FENCE: FENCE_TIMEOUT

S7PRES: FRAME_READY
S7PRES: FRAME_PRESENTED
S7PRES: FRAME_DROPPED
```

### 22.2. Métricas

Se registrarán:

- Tiempo de compilación.
- Tiempo de pipeline creation.
- Tiempo de preparación.
- Tiempo de envío.
- Tiempo de ejecución GPU.
- Tiempo de espera.
- Tiempo de presentación.
- Número de jobs.
- Número de frames.
- Número de errores.
- Recursos retenidos.
- Bytes transferidos.
- Número de mappings.
- Número de fences pendientes.

### 22.3. Errores

Los errores deberán distinguir:

- Recurso inválido.
- Memoria insuficiente.
- Mapping incorrecto.
- MMU fault.
- Job fault.
- Shader inválido.
- Pipeline no soportado.
- Timeout.
- Error de sincronización.
- Error de presentación.
- Error de alimentación.
- Error de reloj.

### 22.4. Recuperación

Ante un fallo de GPU:

1. Capturar el estado.
2. Identificar el trabajo.
3. Conservar los recursos visibles por DMA.
4. Detener nuevas operaciones del contexto afectado.
5. Intentar recuperar el estado cuando sea seguro.
6. Reinicializar el contexto o la GPU si el protocolo lo permite.
7. Mantener disponible la ruta de CPU.

Nunca liberaremos memoria por asumir que un job ha terminado cuando el estado del hardware es ambiguo.

---

# PARTE XV. SEGURIDAD E INTEGRACIÓN CON XNU

## 23. S7GE Kernel ABI

La comunicación entre userland y kernel deberá tener un contrato explícito.

Cada petición tendrá:

- Versión.
- Tamaño.
- Selector.
- Identificador de cliente.
- Parámetros.
- Resultado.
- Estado.
- Identificador de operación.

Las estructuras tendrán tamaños fijos y campos reservados inicializados a cero.

### 23.1. Handles

Los clientes recibirán handles opacos.

No recibirán direcciones físicas.

Cada handle incluirá un mecanismo de generación para impedir que una referencia antigua apunte accidentalmente a un recurso nuevo.

### 23.2. Validación

Se comprobarán:

- Tamaños.
- Overflow.
- Alineaciones.
- Rangos.
- Permisos.
- Propietario.
- Estado.
- Generación.
- Número de recursos.
- Presupuesto de memoria.

### 23.3. Entitlements

El acceso a las operaciones privilegiadas estará limitado.

El objetivo inicial es permitir el funcionamiento de los componentes gráficos de Apple que necesiten acceso al dispositivo, no crear una interfaz abierta para cualquier proceso.

### 23.4. Aislamiento

Un fallo de un cliente no deberá comprometer automáticamente los recursos de otro.

La arquitectura deberá poder aislar:

- Recursos.
- Colas lógicas.
- Contextos.
- Fences.
- Errores.
- Propiedad de memoria.

---

# PARTE XVI. ORGANIZACIÓN DEL CÓDIGO

## 24. Estructura propuesta

La organización inicial que recomiendo es:

```
ios-s7/
|
+-- xnu/
|   |
|   +-- patches/
|   |   |
|   |   +-- 0300-s7ge-gpu-discovery.patch
|   |   +-- 0301-s7ge-mali-registers.patch
|   |   +-- 0302-s7ge-power-clock.patch
|   |   +-- 0303-s7ge-gpu-mmu.patch
|   |   +-- 0304-s7ge-job-manager.patch
|   |   +-- 0305-s7ge-fences.patch
|   |   +-- 0306-s7ge-resource-manager.patch
|   |   +-- 0307-s7ge-iosurface.patch
|   |   +-- 0308-s7ge-userclient.patch
|   |   +-- 0309-s7ge-display-integration.patch
|   |
|   +-- iokit/
|       |
|       +-- Kernel/arm/
|           |
|           +-- S7GPU/
|           +-- S7MMU/
|           +-- S7JMQ/
|           +-- S7MEM/
|           +-- S7IOS/
|           +-- S7PRES/
|
+-- s7ge/
|   |
|   +-- common/
|   |   +-- S7GIR/
|   |   +-- S7Formats/
|   |   +-- S7Types/
|   |
|   +-- userland/
|   |   +-- S7MCL/
|   |   +-- S7MaliMetal/
|   |   +-- S7GL/
|   |   +-- S7Resources/
|   |
|   +-- compiler/
|   |   +-- AIR/
|   |   +-- SPIRV/
|   |   +-- NIR/
|   |   +-- Midgard/
|   |
|   +-- runtime/
|   |   +-- S7PPL/
|   |   +-- S7FENCE/
|   |   +-- S7COMP/
|   |   +-- S7DVFS/
|   |
|   +-- tests/
|       +-- compiler/
|       +-- resources/
|       +-- pipelines/
|       +-- queue/
|       +-- presentation/
|       +-- compositor/
|
+-- docs/
    |
    +-- S7GE_ARCHITECTURE.md
    +-- S7GE_HARDWARE.md
    +-- S7GE_ABI.md
    +-- S7GE_COMPILER.md
    +-- S7GE_VALIDATION.md
    +-- S7GE_STATUS.md
```

Esta estructura es una propuesta. Antes de crearla habrá que compararla con la organización real de nuestro árbol XNU y con el sistema de parches que ya estamos utilizando.

No quiero duplicar componentes existentes.

## 25. Integración con el sistema de parches

Cada fase deberá producir modificaciones pequeñas y revisables.

Reglas:

1. No mezclar GPU con UFS.
2. No modificar la ruta de almacenamiento para solucionar errores gráficos.
3. No sustituir el framebuffer funcional antes de validar su alternativa.
4. No introducir escrituras de registros sin auditoría.
5. No añadir un servicio sin su contrato de recursos.
6. No activar una característica que todavía no tenga pruebas.
7. Mantener un checkpoint funcional.
8. Registrar hashes y resultados de cada hito.
9. Separar los resultados de compilación de los resultados del dispositivo.
10. Mantener los cambios específicos de `herolte` separados de los del A5XELTE.

---

# PARTE XVII. COMPARACIÓN CON EL TRABAJO ANTERIOR

## 26. Qué podemos aprovechar de WardevSA A5XELTE

La línea A5XELTE es una referencia de diseño muy importante.

La documentación disponible muestra una progresión desde la identificación de la GPU hasta la ejecución de trabajos reales.

Entre los hitos documentados aparecen:

- Registro del servicio GPU.
- Lectura segura de GPU_ID.
- Configuración de alimentación y clocks.
- Ejecución de `WRITE_VALUE`.
- Renderizado fragment privado.
- Escritura en scanout.
- Fences serializadas.
- Cadenas de textura.
- Importación de IOSurface.
- Cliente privado de recursos.
- Descubrimiento de Metal.
- Bundle de implementación.
- Compilación de shaders.
- Ejecución de trabajos traducidos.
- Integración de recursos y pipelines reales.

Esto es exactamente el tipo de secuencia que debemos estudiar.

### 26.1. Lo que reutilizaremos conceptualmente

| Trabajo anterior    | Decisión S7GE                    |
| ------------------- | -------------------------------- |
| GPU discovery       | Reutilizar metodología           |
| MMIO safety         | Reutilizar principios            |
| GPU queue           | Reutilizar modelo                |
| Fence protocol      | Reutilizar contrato              |
| IOSurface import    | Reutilizar diseño                |
| Metal discovery     | Reauditar en nuestro iOS         |
| AIR translation     | Investigar y adaptar             |
| NIR lowering        | Reutilizar cuando sea compatible |
| Midgard descriptors | Adaptar a T880                   |
| Panfrost audits     | Utilizar como referencia         |
| Pixel oracles       | Adoptar como requisito           |

### 26.2. Lo que no copiaremos

No copiaremos directamente:

- Registros del Exynos 7580.
- Secuencias de BUCK4 del A5.
- Direcciones MMIO.
- IRQ.
- Configuración de clocks.
- Máscaras de cores.
- Erratas específicas del T720.
- Descriptores específicos de un perfil T720 sin validación.
- Configuración de memoria del A5.
- Suposiciones sobre su display.

### 26.3. Conclusión de la comparación

La principal ventaja de la investigación anterior es que ya nos enseña cómo estructurar un port gráfico Apple-to-Mali.

Nuestra tarea será convertir ese conocimiento en una implementación específica del Exynos 8890.

No es necesario reinventar el protocolo de ejecución de Midgard.

Sí es necesario demostrar que la implementación es correcta para nuestro dispositivo.

---

# PARTE XVIII. PLAN DE IMPLEMENTACIÓN

## 27. Estrategia general

Divido el desarrollo en doce fases.

No las ejecutaremos todas simultáneamente.

Cada fase tendrá una puerta de aceptación.

## Fase 0 — Auditoría de la plataforma

**Objetivo:** determinar el estado real de nuestro port S7.

Trabajo:

- Auditar XNU.
- Auditar ADT.
- Identificar la ruta de display.
- Buscar servicios existentes.
- Identificar IOSurface.
- Identificar IOMobileFramebuffer.
- Buscar referencias a IOGPU.
- Identificar recursos físicos de GPU.
- Revisar el parche `0204-herolte-exynos-ufs.patch` y los cambios posteriores del árbol local.
- Comparar con el trabajo A5XELTE.

Entregable:

`S7GE_HARDWARE_AUDIT.md`

Criterio de aceptación:

No se inicia la inicialización activa de GPU sin un mapa de hardware verificable.

## Fase 1 — Identificación GPU

**Objetivo:** conseguir identificar correctamente la Mali-T880.

Trabajo:

- ADT.
- MMIO.
- GPU_ID.
- Revisión.
- Características.
- Topología.
- IRQ.

Entregable:

`S7GPU Discovery`

Criterio:

Identificación física repetible y sin errores.

## Fase 2 — Alimentación y clocks

**Objetivo:** disponer de un estado de alimentación seguro.

Trabajo:

- Reguladores.
- Dominios.
- Clocks.
- Interconexiones.
- Secuencia de inicialización.
- Lecturas de verificación.
- Límites de frecuencia.

Entregable:

`S7GPU Power Controller`

Criterio:

GPU preparada en un estado estable y reproducible.

## Fase 3 — MMU

**Objetivo:** conseguir mappings GPU correctos.

Trabajo:

- Tablas de páginas.
- Address Spaces.
- PTE.
- Invalidaciones.
- Cache maintenance.
- Protección de páginas.
- Diagnóstico de faults.

Entregable:

`S7MMU`

Criterio:

Lecturas y escrituras GPU sobre buffers privados con validación de contenido.

## Fase 4 — Primeros trabajos

**Objetivo:** ejecutar operaciones reales.

Orden:

1. WRITE_VALUE.
2. Clear.
3. Fragment privado.
4. Textura.
5. Vertex.
6. Tiler.
7. Fragment completo.

Entregable:

`S7JMQ`

Criterio:

Trabajos terminados con fences, resultados correctos y ausencia de faults.

## Fase 5 — Memoria y recursos

**Objetivo:** gestionar recursos gráficos reales.

Trabajo:

- Buffers.
- Texturas.
- Pools.
- Handles.
- IOSurface.
- Importación.
- Retención.
- Liberación.
- Sincronización.

Entregable:

`S7MEM + S7IOS`

Criterio:

Importar y utilizar recursos con formatos y dimensiones verificadas.

## Fase 6 — Backend Midgard

**Objetivo:** ejecutar shaders y descriptores reales.

Trabajo:

- Compiler integration.
- Descriptor generation.
- Varyings.
- Uniforms.
- Textures.
- Samplers.
- Vertex input.
- Fragment output.

Entregable:

`S7GTE Midgard Backend`

Criterio:

Comparación de píxeles frente a una referencia independiente.

## Fase 7 — Shader compiler

**Objetivo:** traducir shaders procedentes de iOS.

Trabajo:

- AIR.
- SPIR-V.
- NIR.
- Midgard.
- Linking.
- Specialization.
- Shader cache.

Entregable:

`S7SHC`

Criterio:

Ejecutar funciones reales traducidas, no solamente shaders de prueba escritos para el proyecto.

## Fase 8 — Metal Compatibility

**Objetivo:** proporcionar un dispositivo reconocible y utilizable por Metal.

Trabajo:

- Device discovery.
- Device provider.
- Command queue.
- Command buffer.
- Buffers.
- Textures.
- Pipelines.
- Resource bindings.
- Error reporting.

Entregable:

`S7MCL`

Criterio:

Metal acepta el dispositivo y realiza operaciones gráficas reales.

## Fase 9 — Core Animation

**Objetivo:** integrar la GPU en la composición.

Trabajo:

- BackBoard.
- QuartzCore.
- IOSurface.
- Render passes.
- Blending.
- Layer composition.
- Partial updates.

Entregable:

`S7COMP`

Criterio:

Un fotograma generado por el compositor real llega a la Mali y produce los píxeles esperados.

## Fase 10 — Presentación

**Objetivo:** integrar el resultado con el panel.

Trabajo:

- Scanout.
- VSync.
- Buffer ownership.
- Fences.
- Double/triple buffering.
- Tearing control.

Entregable:

`S7PRES`

Criterio:

Fotogramas GPU presentados correctamente y de forma repetible.

## Fase 11 — Optimización

**Objetivo:** conseguir rendimiento sostenido.

Trabajo:

- DVFS.
- Memory bandwidth.
- Pipeline cache.
- Resource reuse.
- Batching.
- Scheduling.
- CPU/GPU overlap.
- Thermal control.

Entregable:

`S7GE Performance Suite`

Criterio:

Mejoras medidas frente a la ruta anterior, sin pérdida de corrección.

## Fase 12 — Estabilidad

**Objetivo:** convertir el subsistema en una pieza estable de IOS S7.

Trabajo:

- Stress testing.
- Resource pressure.
- Context teardown.
- Fault injection.
- Recovery.
- Suspend/resume.
- Reboot.
- Long-running tests.

Entregable:

`S7GE Stability Report`

Criterio:

Funcionamiento prolongado sin fugas, corrupción, fallos de sincronización ni bloqueos recurrentes.

---

# PARTE XIX. MATRIZ DE VALIDACIÓN

## 28. Qué significa que una función está terminada

Utilizaremos cinco niveles de evidencia.

| Nivel | Significado                        |
| ----- | ---------------------------------- |
| L0    | Diseño                             |
| L1    | Código compilable                  |
| L2    | Prueba aislada en host             |
| L3    | Ejecución real en GPU              |
| L4    | Integración con iOS y presentación |

Una función no podrá anunciarse como funcional para iOS si solamente ha alcanzado L1, L2 o L3.

Ejemplo:

| Función        | Prueba mínima             |
| -------------- | ------------------------- |
| GPU discovery  | GPU_ID y revisión         |
| MMU            | Mapping y readback        |
| Fragment       | Pixel oracle              |
| Textura        | Sampling oracle           |
| Fences         | Completion y error state  |
| IOSurface      | Importación y vida útil   |
| Metal          | Device acceptance         |
| Pipeline       | Creación y ejecución      |
| Core Animation | Frame real                |
| Display        | Presentación sincronizada |

## 29. Pruebas gráficas

La suite tendrá referencias generadas por CPU y resultados obtenidos de GPU.

Se compararán:

- Píxeles.
- Canales.
- Valores numéricos.
- Tolerancias.
- Guard regions.
- Recursos inmutables.
- Estados finales.

No se permitirá que una prueba apruebe simplemente porque el job header dice DONE.

Debe comprobarse el resultado.

### 29.1. Familias de pruebas

1. Clear.
2. Copy.
3. Texturing.
4. Blur.
5. Downsampling.
6. Geometry.
7. Paths.
8. Blending.
9. Multiple attachments.
10. Alpha.
11. Formats.
12. Partial rendering.
13. Resource lifetime.
14. Synchronization.
15. Presentation.

### 29.2. Pruebas de regresión

Cada nueva versión del compilador deberá ejecutar la suite completa de casos ya aceptados.

Un cambio en el compilador puede corregir un shader y romper otro.

No aceptaremos optimizaciones sin regresión.

---

# PARTE XX. RIESGOS Y DECISIONES PENDIENTES

## 30. Riesgo: API privada de Apple

La interfaz de Metal que utiliza internamente iOS contiene contratos privados.

No tenemos una especificación pública completa de todas las estructuras que necesita el proveedor de hardware.

Mitigación:

- Inspección de símbolos.
- Análisis del dyld shared cache.
- Trazas de IOKit.
- Captura de peticiones.
- Verificación de tamaños.
- Pruebas de cada selector.
- Versionado de ABI.

No vamos a implementar selectores a ciegas.

## 31. Riesgo: diferencia de hardware

El código A5XELTE utiliza T720 y no puede trasladarse directamente a T880.

Mitigación:

- Comparación con Panfrost.
- Identificación de revisión.
- Tabla de características.
- Erratas específicas.
- Validación de descriptores.
- Pruebas físicas.

## 32. Riesgo: traducción de shaders

No todos los shaders AIR tendrán una equivalencia sencilla.

Mitigación:

- IR intermedia.
- Lowering explícito.
- Especialización.
- Validación.
- Errores diferenciados.
- Perfiles de compatibilidad.

## 33. Riesgo: composición de iOS

Un shader correcto no garantiza una composición correcta.

Mitigación:

- Pruebas con recursos reales.
- Blend states.
- Attachments.
- Orden de capas.
- Presentación.
- Comparación de fotogramas completos.

## 34. Riesgo: memoria

El hardware puede estar utilizando una página que el kernel cree que ya puede liberar.

Mitigación:

- Handles.
- Generaciones.
- Fences.
- Retención.
- Mapping epochs.
- Teardown validado.
- Cuarentena en caso de ambigüedad.

## 35. Riesgo: consumo energético

La aceleración puede empeorar la experiencia si requiere frecuencias excesivas o mantiene el dispositivo caliente.

Mitigación:

- DVFS.
- Medición.
- Límites térmicos.
- Carga adaptativa.
- Reducción de operaciones innecesarias.

---

# PARTE XXI. INTEGRACIÓN CON EL RESTO DE IOS S7

## 36. Relación con XNU

XNU proporcionará:

- IOKit.
- Gestión de memoria.
- DMA.
- Interrupciones.
- Temporizadores.
- Mach ports.
- User clients.
- Sincronización.
- Servicios de dispositivo.

S7GE no debe duplicar funcionalidades que ya proporciona correctamente el kernel.

## 37. Relación con DROP V2

DROP V2 y S7GE serán subsistemas independientes.

DROP V2 se ocupará de las operaciones transaccionales y la recuperación de almacenamiento.

S7GE se ocupará de los recursos y la ejecución gráfica.

La caché persistente de shaders podrá utilizar los mecanismos de persistencia del sistema, pero no dependerá de que una operación gráfica se complete para consolidar datos.

Si DROP V2 todavía no está disponible, S7GE podrá trabajar con almacenamiento convencional, manteniendo las precauciones adecuadas.

## 38. Relación con UFS

UFS proporciona el almacenamiento persistente.

No proporciona memoria GPU ni sustituye a la memoria RAM.

Los recursos gráficos activos deberán permanecer en memoria de sistema y en mappings GPU válidos.

No utilizaremos UFS como sustituto de una gestión correcta de memoria gráfica.

## 39. Relación con el subsistema de pantalla

El controlador de pantalla será independiente de la GPU.

S7PRES coordinará ambos subsistemas.

La ruta de CPU seguirá disponible hasta que la ruta de GPU haya sido probada suficientemente.

---

# PARTE XXII. DECISIONES OFICIALES DE DIRECCIÓN

## 40. Decisiones que establezco

| Decisión                                      | Estado                                                     |
| --------------------------------------------- | ---------------------------------------------------------- |
| Metal como API principal                      | Aprobada como objetivo                                     |
| OpenGL ES como API adicional                  | Aprobada                                                   |
| OpenGL ES como traductor obligatorio de Metal | Rechazada                                                  |
| IR gráfica común                              | Aprobada                                                   |
| Backend Midgard específico T880               | Aprobado                                                   |
| Reutilización de Panfrost                     | Aprobada como referencia y base de componentes compatibles |
| Copia directa del driver T720                 | Rechazada                                                  |
| AGXMetalA11 reutilizado como backend Mali     | Rechazada                                                  |
| GPU física como ruta de renderizado           | Objetivo obligatorio                                       |
| CPU framebuffer como fallback                 | Aprobado                                                   |
| GPU userclient con handles opacos             | Aprobado                                                   |
| Fences verificables                           | Obligatorio                                                |
| Recuperación de faults                        | Obligatorio                                                |
| Pruebas de píxeles                            | Obligatorio                                                |
| Optimización antes de corrección              | Rechazada                                                  |

## 41. Qué no vamos a hacer

Quedan descartadas estas estrategias:

1. Fingir que Metal está soportado registrando solamente un servicio.
2. Hacer que Metal acepte pipelines que nunca se ejecutarán.
3. Traducir todas las operaciones a OpenGL ES sin estudiar sus diferencias.
4. Copiar registros de Exynos 7580 al Exynos 8890.
5. Exponer MMIO a procesos de usuario.
6. Liberar memoria después de un timeout ambiguo.
7. Sustituir el compositor por una implementación de CPU y llamarlo aceleración.
8. Dar por terminada la GPU porque se ha dibujado un rectángulo.
9. Optimizar frecuencia sin comprobar alimentación.
10. Mezclar los parches gráficos con DROP V2 y UFS.

---

# PARTE XXIII. RESULTADO QUE QUEREMOS CONSEGUIR

## 42. Definición de S7GE terminado

Consideraremos que IOS S7 Graphics Engine ha alcanzado su objetivo cuando podamos demostrar:

**Hardware**

- La Mali-T880 se inicializa correctamente.
- Su alimentación y clocks son seguros.
- La MMU funciona.
- El Job Manager ejecuta trabajos reales.

**Recursos**

- Buffers y texturas.
- IOSurface.
- Mapping.
- Coherencia.
- Retención.
- Liberación segura.

**Traducción**

- Shaders reales.
- Pipelines reales.
- Recursos reales.
- Blend state.
- Operaciones de renderizado.
- Errores correctamente propagados.

**Metal**

- El sistema descubre el dispositivo.
- Los clientes pueden utilizarlo.
- Las operaciones soportadas se ejecutan.
- Las no soportadas se rechazan correctamente.

**Composición**

- Core Animation utiliza la GPU.
- BackBoard genera fotogramas acelerados.
- SpringBoard se beneficia del backend.
- Los resultados coinciden con las referencias.

**Display**

- Los fotogramas llegan al panel.
- No existe tearing en la ruta normal.
- La sincronización funciona.
- La latencia es medible.

**Estabilidad**

- No existen fugas sostenidas.
- Los recursos no se corrompen.
- Los fallos se detectan.
- Los contextos pueden recuperarse cuando sea seguro.
- El sistema puede permanecer funcionando durante pruebas prolongadas.

---

# CONCLUSIÓN GENERAL

IOS S7 Graphics Engine no debe ser un simple controlador de GPU.

Debe ser una infraestructura completa de compatibilidad gráfica entre iOS y la Mali-T880.

La parte más importante no será únicamente escribir código para el Job Manager.

Será conseguir que los contratos de Apple, la traducción de shaders, la gestión de memoria, el protocolo Midgard y la composición de Core Animation funcionen conjuntamente.

La estrategia que establezco es:

**Metal arriba. S7GIR en medio. Midgard abajo. Hardware real ejecutando el trabajo.**

OpenGL ES coexistirá con esa infraestructura, pero no será un sustituto semánticamente incompleto de Metal.

La referencia A5XELTE nos proporciona una cantidad extraordinaria de investigación reutilizable. Nuestra obligación será adaptarla al Exynos 8890, verificar las diferencias y llevarla a un nivel de integración que no se quede en pruebas privadas.

El objetivo no es conseguir que el Galaxy S7 sea capaz de dibujar una interfaz de iOS.

El objetivo es conseguir que el sistema operativo iOS utilice realmente el hardware gráfico del Galaxy S7 como parte de su propia arquitectura.

**IOS S7 Graphics Engine: native hardware execution, Apple API compatibility, verified rendering.**

# **ANEXO A. AUDITORÍA TÉCNICA DE LA IMPLEMENTACIÓN ANTERIOR**

Esta parte es especialmente importante porque no quiero que S7GE repita errores que ya han aparecido durante el desarrollo de otros puertos.

## **A.1. Progresión real de A5XELTE**

La documentación del repositorio permite reconstruir esta progresión:

| Parches          | Hito                           | Evidencia documentada              |
| ---------------- | ------------------------------ | ---------------------------------- |
| 0125–0127        | Descubrimiento y acceso seguro | GPU identificada                   |
| 0128–0130        | Primeras operaciones           | WRITE_VALUE completado             |
| 0131–0132        | Renderizado fragment           | 256/256 píxeles correctos          |
| 0133             | Escritura en scanout           | Cuadrado verde visible             |
| 0134             | Sincronización                 | Dos fences consecutivas            |
| 0135             | Texturas                       | Cadena tiler + fragment            |
| 0138–0149        | Recursos y cliente             | Importación y operaciones privadas |
| 0150–0155        | AS1 y recursos tipados         | Colas y memoria GPU                |
| 0156–0161        | Integración Metal              | Descubrimiento y bundle            |
| 0175–0177        | Shaders y runtime              | Suite gráfica y ejecución nativa   |
| 0200 en adelante | Generalización                 | Pipelines, recursos y compositor   |

Fuentes de comparación:

- [GPU port y resultados físicos](https://github.com/Xpl0itU/ios-a5xelte-wardevsa/blob/main/docs/a5xelte-gpu-port.md).
- [Resultados de shaders](https://github.com/Xpl0itU/ios-a5xelte-wardevsa/blob/main/docs/a5xelte-shader-suite-results.md).
- [Native Metal Runtime](https://github.com/Xpl0itU/ios-a5xelte-wardevsa/blob/main/docs/a5xelte-native-metal-runtime.md).
- [Capa de traducción Metal-Mali](https://github.com/Xpl0itU/ios-a5xelte-wardevsa/blob/main/docs/a5xelte-metal-mali-layer.md).

## **A.2. Qué considero especialmente valioso**

Hay cuatro avances que quiero aprovechar especialmente.

**Primero: el modelo de ejecución.**

La implementación anterior consiguió pasar de pruebas de identificación a trabajos reales sobre GPU.

Esto nos da una secuencia de ingeniería que debemos conservar.

**Segundo: la integración de IOSurface.**

La importación de recursos reales permite dejar atrás las pruebas con buffers artificiales.

Es un paso imprescindible para llegar a Core Animation.

**Tercero: la traducción de shaders.**

La combinación AIR, SPIR-V, NIR y Midgard demuestra que podemos investigar una ruta viable para ejecutar funciones originadas en el entorno de Apple.

**Cuarto: la investigación del ABI de Metal.**

El descubrimiento del dispositivo, el bundle y las interfaces privadas nos proporciona un punto de entrada concreto.

## **A.3. Problemas que debemos evitar**

La propia auditoría Panfrost de A5XELTE documenta diferencias entre su controlador y el protocolo de referencia de Linux.

Entre los problemas identificados están:

- Configuración de `START_MMU` específica de T720.
- Configuración obligatoria de shader cores.
- Secuencia incompleta de teardown de AS1.
- Uso inconsistente de registros de interrupción enmascarados y RAW.
- Ausencia de una inicialización completa de reset.
- Recuperación limitada de errores.
- Gestión de recursos que todavía requiere ampliación.

No trasladaremos esas correcciones mecánicamente al T880. Las utilizaremos como lista de comprobación para realizar una auditoría específica del modelo T880.

Esto es fundamental: un trabajo GPU que termina correctamente en condiciones normales no demuestra que el controlador sea correcto bajo presión de memoria, errores MMU o reutilización de recursos.

# **ANEXO B. PRESUPUESTO DE MEMORIA Y RENDIMIENTO DEL S7**

## **B.1. Coste del framebuffer**

La pantalla del Galaxy S7 tiene una resolución de 1440 × 2560.

Con un formato BGRA8:

\\[ 1440 \times 2560 \times 4 = 14\\,745\\,600\text{ bytes} \\]

Aproximadamente 14,06 MiB por framebuffer completo.

Con tres buffers de presentación:

\\[ 3 \times 14\\,745\\,600 = 44\\,236\\,800\text{ bytes} \\]

Aproximadamente 42,19 MiB.

Esto es únicamente el coste de los tres buffers. No incluye:

- Texturas de aplicaciones.
- IOSurface adicionales.
- Buffers de geometría.
- Recursos temporales.
- Descriptores.
- Memoria de shaders.
- Cachés.
- Tablas de páginas.

Por eso S7MEM no puede ser una simple capa de asignación.

Necesitamos un presupuesto de memoria GPU, políticas de presión y reutilización de recursos.

## **B.2. Presupuesto temporal**

A 60 Hz:

\\[ T\_{\text{frame}} = \frac{1000}{60} = 16,67\text{ ms} \\]

Ese presupuesto debe cubrir:

- Producción del fotograma.
- Preparación de comandos.
- Ejecución GPU.
- Sincronización.
- Presentación.

No significa que cada shader tenga que terminar en 16,67 ms.

Significa que el pipeline completo debe producir fotogramas a la cadencia necesaria.

## **B.3. Métricas que exigiremos**

No aceptaremos una cifra aislada de FPS.

Mediremos:

| Métrica          | Utilidad                   |
| ---------------- | -------------------------- |
| FPS              | Cadencia                   |
| Frame time P50   | Rendimiento habitual       |
| Frame time P95   | Comportamiento bajo carga  |
| Frame time P99   | Colas y latencias extremas |
| GPU busy         | Utilización                |
| CPU time         | Coste de preparación       |
| Queue latency    | Espera                     |
| Submit latency   | Envío                      |
| Fence latency    | Finalización               |
| Present latency  | Visualización              |
| Memory bandwidth | Presión de memoria         |
| Temperature      | Estabilidad térmica        |
| Dropped frames   | Pérdida de fotogramas      |

# **ANEXO C. DECISIONES QUE QUEDAN PENDIENTES DE AUDITORÍA**

No voy a inventar información que todavía no hemos comprobado.

Estos son los puntos que necesito resolver sobre el árbol real `herolte` antes de autorizar el diseño de los primeros parches:

| Prioridad | Pregunta                                                                   |
| --------- | -------------------------------------------------------------------------- |
| Crítica   | ¿Qué soporte de framebuffer existe realmente?                              |
| Crítica   | ¿Existe ya algún servicio IOSurface funcional?                             |
| Crítica   | ¿Tenemos información fiable del display controller?                        |
| Crítica   | ¿Qué Device Tree utiliza nuestro Exynos 8890?                              |
| Crítica   | ¿Qué recursos GPU están disponibles en ese ADT?                            |
| Alta      | ¿Qué controladores Linux del Exynos 8890 podemos utilizar como referencia? |
| Alta      | ¿Qué revisión exacta de Mali-T880 tenemos?                                 |
| Alta      | ¿Qué soporte de interrupciones GIC existe?                                 |
| Alta      | ¿Qué partes de IOKit podemos reutilizar?                                   |
| Alta      | ¿Qué versión exacta de Metal espera nuestro userland?                      |
| Media     | ¿Qué funciones de QuartzCore están utilizando actualmente CPU?             |
| Media     | ¿Qué formatos necesita inicialmente BackBoard?                             |

**No autorizo todavía la escritura de registros GPU ni la sustitución de la ruta de presentación existente.** Primero necesitamos resolver los puntos críticos.

# **ANEXO D. ORDEN DE TRABAJO QUE VOY A DIRIGIR**

Mi orden de trabajo será el siguiente:

**S7GE — Roadmap de dirección**

Especificación inicial

1. **Auditoría del árbol `herolte`**

   Localizar display, IOSurface, IOKit, ADT y parches existentes.

   Siguiente trabajo
2. **Auditoría de Exynos 8890 / Mali-T880**

   Contrastar hardware, Device Tree, Linux y Panfrost.
3. **Especificación del controlador S7GPU**

   Definir recursos, inicialización, MMU y protocolo.
4. **Diseño S7GIR y S7SHC**

   Definir IR, compilación y traducción de shaders.
5. **Diseño S7MCL**

   Especificar la compatibilidad con Metal y su ABI.
6. **Integración IOSurface y Core Animation**

   Conectar recursos y composición.
7. **Pruebas y optimización**

   Validar píxeles, estabilidad y rendimiento sostenido.

## **Mi decisión final como director técnico**

Hay algo que quiero dejar muy claro: no quiero que S7GE se convierta en un proyecto que acumule cientos de parches para conseguir pequeños resultados aislados.

Quiero una arquitectura coherente en la que cada componente tenga responsabilidades, interfaces, límites y pruebas.

Y quiero que aprovechemos los avances de WardevSA en lugar de empezar desde cero.

**Nuestra ventaja no será escribir más código que los anteriores. Será integrar mejor las piezas, entender las diferencias de hardware y conseguir que el sistema gráfico completo funcione.**

## **Una última cosa que necesito para la siguiente fase**

He podido consultar el repositorio público, pero no el árbol local donde aparece el trabajo `herolte` que hemos estado desarrollando.

Necesito que me facilites la URL de la rama que contiene esos cambios, o que publiques esa rama en GitHub. En particular, quiero revisar el diff real de `0204-herolte-exynos-ufs.patch` y los parches posteriores.

Con eso podré hacer la siguiente auditoría sobre código real y convertir esta especificación en un diseño de implementación adaptado a nuestro XNU, sin duplicar nada de lo que ya hemos construido.

**S7GE queda definido como nuestro nuevo subsistema gráfico de referencia.**

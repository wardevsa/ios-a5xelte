# Proyectos públicos relacionados (iOS/XNU en teléfonos y en máquinas virtuales), 18-nov-2026

Método: búsqueda en la API pública de GitHub y lectura de los README (solo lectura, nivel L1). **No se han auditado los códigos ni compilado nada.** Las descripciones son las de cada proyecto; lo que sigue es lectura mía y puede equivocarse. No se ha copiado código; antes de reutilizar cualquier pieza hay que mirar su licencia (ver `S7GE_LICENCIAS.md`).

## 1. Portes de XNU a teléfonos (nuestra familia)
| Proyecto | Qué es | Qué nos enseña |
|---|---|---|
| `wardevsa/ios-a5xelte` (nuestro origen), ramas `herolte` y `herolte-ios18` | el mismo S7 y la misma serie 0200-0341; la rama iOS 18 usa XNU 11215 con `v80emu` y `pacstrip` (ver `S7GE_UPSTREAM_IOS18_ESTUDIO_20261118.md`) | cómo se resuelve iOS 18 sin ARMv8.1+ ni PAC |
| `plusminusios/hakios-komodo` | iOS 16 (`xnu-8796.141.3`) en un Pixel 9 Pro XL (Tensor G4), todo en RAM con `fastboot boot`; linaje ios-tegu / ios-sweet / **HakiOS** (de donde viene parte de nuestro audio y GL) | llega al PID 1; **bloqueado por el UFS Exynos** (la PHY sale de hibernación mal y el aislamiento de energía lo tiene TrustZone): nuestro `herolte_ufs.c` lo resuelve en el 8890, puede servir de referencia |
| `luuu20309/UniXNU-polaris` | Xiaomi Mi MIX 2S (SDM845, Adreno 630): la cadena antigua (XNU 8796, 93 parches, ADT con identidad iPhone X) **llegó a la pantalla de bloqueo con táctil**; ahora migra a «UniXNU» (XNU 10063) con firmware edk2-msm, un gestor de arranque en una ESP y `fastboot boot` temporal | otra forma de arrancar (UEFI en vez de un shim sobre el cargador del fabricante); prueba de que el SD845 funciona; **mismo punto al que hemos llegado nosotros con otro SoC** |
| `cu-e/s24-ios-exynos` | investigación para el Galaxy S24 (Exynos 2400): pruebas de ordenador, una prueba real de traducción de cómputo «con forma de AIR», seguimiento por tareas y un acuerdo de trabajo para agentes | método parecido al nuestro (gobierno, evidencias); GPU Xclipse con Vulkan (RADV) |
| `qianxiaochen82-hue/ios-sweet-apollo` | Xiaomi apollo (SM8250) | la familia SWEET original |
| `assergames78-glitch/ios12-tablet` | XNU de iOS 12 en una tableta MT6737T | porte a MediaTek, otro SoC |
| `merckhung/darwin_embedded` | Darwin/XNU 12377 (versión moderna) derivado de PureDarwin, se compila en Linux | construir XNU sin macOS |
| `blacktop/darwin-xnu-build` | el compilador de XNU que usa nuestro CI | ya lo usamos |

## 2. XNU en emuladores y máquinas virtuales (otra forma de llegar a iOS)
- **`alephsecurity/xnu-qemu-arm64`**, **`TrungNguyen1909/qemu-t8030`** (iPhone 11 emulado), **`ChefKissInc/QEMUAppleSilicon`**: emulan el SoC de Apple en QEMU; sirven para depurar XNU sin teléfono (vimos esto en nuestra hoja de ruta como «banco de pruebas sin teléfono»).
- **`YahiaAngelo/vphone-linux`**: arranca un iPhone virtual (iOS 27.0.1 en la captura) en un PC Linux con QEMU y tres piezas: **`reims-vgpu`** (GPU virtual sobre Vulkan) y **`metal2vulkan`**.
- **`alpersamur3/asoft-ios-android`**: iOS 16 dentro de una aplicación de Android con QEMU y un «motor EL0 nativo» en un teléfono bloqueado (otro enfoque, más cercano a una emulación).

## 3. El hallazgo que cambia el plan de Metal: `steelbrain/metal2vulkan`
Rust, **GPL-2.0-o-posterior O LGPL-3.0-o-posterior**, beta (0.x), activo (último cambio 17-nov). Lee **AIR** (metallib o bitcode) y lo compila a **pipelines de Vulkan** (cómputo, render, teselación, tile y mesh), y además ofrece **la API de Metal sobre un dispositivo Vulkan** (`metal2vulkan-runtime`). Su crate `metal2vulkan-air` es un **front end de AIR independiente** (contenedor metallib, lector de bitcode, IR tipado, metadatos, intrínsecos).
- **Corrijo lo que dije el 17-nov:** que no conocía una herramienta madura para AIR. Existe esta, aunque en beta. **Madura no es**: «0.x, la API y el SPIR-V pueden cambiar».
- **Ruta posible para la Mali (inferencia mía, no probada):** AIR → (metal2vulkan) **SPIR-V** → (`spirv_to_nir` de Mesa) **NIR** → compilador **Midgard** de Panfrost. Faltaría que su SPIR-V no exija capacidades que la T880 no tenga, y que Rust y su licencia encajen con nuestro árbol (los componentes del proyecto son MIT/APSL; GPL/LGPL exige cumplir sus condiciones).
- Su runtime exige Vulkan 1.2: no sirve tal cual para la T880 (sin Vulkan), pero su **front end de AIR y los controles de validación** (rechazos tipados, diferencias registradas) son justo lo que un `MTLDevice` propio necesitaría.

## 4. Qué haré con esto
1. Meter metal2vulkan como candidato en la evaluación de Metal (`S7GE_ARCHITECTURE`, S7GIR): primero **solo lectura y una prueba en el PC**: compilar un `.metallib` pequeño a SPIR-V y mirar qué capacidades pide.
2. Mirar el SD845 de `UniXNU-polaris` como dato para la evaluación de teléfono (puede que la plataforma Qualcomm ofrezca Vulkan y un camino de GPU más corto).
3. No reutilizar código de ningún proyecto sin revisar antes su licencia y sin que lo apruebe el Director.

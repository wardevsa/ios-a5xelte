# Fallos de userland con iOS en pantalla (min31, 2026-11-15)

Base: BOOT `min31` (CPU 2600 MHz, GPU 650 MHz, `sweetfb_gpu=1`, escala 750x1334). Evidencia: E-0220, E-0226, E-0230, E-0232 y las observaciones del Director.

| Síntoma | Qué dice el log | Causa probable | Nivel | ¿Se arregla con DROP/userland? |
|---|---|---|---|---|
| Messages (MobileSMS) abre y cierra | `CRASH MobileSMS sig 11 pc 0x0` con la pila en **CoreImage** (`CoreImage+19c58c`, `+45884`, `+7114`) invocada desde MobileIcons: **llamada a un puntero de función nulo** | CoreImage crea un contexto de Metal/GPU y no existe proveedor Metal (`IOAcceleratorES` vacío, parche 0260) | L2 (pila) / L1 (causa) | **No**: requiere Metal (S7GE) o evitar CoreImage |
| assetsd, PhotosFileProvider, fileproviderd abortan | `sig 6`, misma pila en los tres: `abort` -> `libc++abi` (terminate) -> `libobjc` -> `libdispatch`: **excepción sin capturar** dentro de un bloque de dispatch | Todos son del stack de Fotos; la excepción probable es una biblioteca de fotos inexistente al primer arranque. El texto de la excepción no está en el log | L2 (pila) / L0 (causa) | Posible: crear la biblioteca/estado inicial; hace falta ver la excepción (log de `NSException`) |
| driverkitd muere | `sig 9` (SIGKILL) | Probablemente política (entitlements/ejecución); no es crítico | L2 | No necesario |
| Ajustes > About crashea | no hay registro en el kernel (el crash reporter solo cuenta algunos) | Desconocida; About pide MobileGestalt (modelo, número de serie, capacidad) | L0 | Posible (MobileGestalt) |
| Ajustes muestra "Sign in to your iPad" | n/a | El dispositivo se presenta como clase iPad (MobileGestalt `DeviceClass`) en vez de iPhone | L1 | Posible: dato de MobileGestalt (cache) o ADT |
| Phone en blanco; apps que se quedan en negro | n/a | UI que depende de Metal/CoreImage/blur (upstream: "blur de Metal"), o de servicios no disponibles | L1 | Parcial |
| Fondo de pantalla negro | n/a | Wallpapers de iOS 16 usan Metal; upstream pone una imagen fija con `herosb=1` (hero-run) | L1 (upstream) | **Sí**, con hero-run (`herosb`) |
| `SPAWN FAILED /private/var/herolte/autorun` | log | Falta el ejecutable `autorun` (hero-run) | L2 | **Sí**: es lo que instala DROP |

## Qué se puede hacer sin tocar BOOT
`hero-run` (en `gpu/eagl/test/hero-run.c`, binario ya compilado en `~/HackiOS/builds/device-day/artifacts/mesa-ios-a43e3e5/hero-run`) se instala como `/private/var/herolte/autorun` por DROP. Hace, entre otras cosas: fondo fijo (`herosb`), mover `BTAudioHALPlugin`, lista de servicios desactivados (`disabled.list`), `apps.remove`. **Pero**: DROP v2 está escrito y probado en anfitrión (`xnu/drop-v2`), integrado en el kernel (0337) y **no probado en este teléfono**; instalarlo implica (1) `herodrop=1` en el BOOT (imagen nueva) y (2) escribir un paquete en la zona de DROP de USERDATA (por TWRP, `tools/herolte-drop.py`): dos acciones rojas con firma.

## Qué NO se arregla así
Messages, el blur y buena parte de las apps necesitan una ruta Metal/GPU: es el trabajo de S7GE (`docs/S7GE_ARCHITECTURE.md`), todavía sin empezar.

## Orden propuesto
1. Ver el texto de la excepción de assetsd (añadir al kernel el volcado de `NSException`? o leerlo con `log` desde hero-run): L0 hoy.
2. Paquete DROP mínimo: `autorun` (hero-run) con `herosb`, sin cambiar nada más; imagen `min32` = min31 + `herodrop=1`.
3. Después MobileGestalt (iPad -> iPhone) y About.
4. S7GE: primer hito pequeño.


## Actualización 16-nov (min37c, E-0278)
- **MobileSafari cae 4 veces con la MISMA pila que Messages** (`pc 0x0`, `CoreImage+19c924 <- +45884 <- +7114 <- +6f10 <- +42738`): llamada a un puntero de función nulo dentro de CoreImage. Al tocar una foto de Google Safari pide a CoreImage un contexto y no hay Metal. **Causa común de Messages, Safari (foto) y probablemente Fotos: falta de Metal (S7GE).** `com.apple.WebKit.WebContent` muere 5 veces con SIGKILL (xstat 9; sin mensaje de jetsam: no se sabe si es memoria).
- Las cadenas de `CoreImage` no ofrecen un interruptor de software (`CI_*` solo trae variables de depuración); no hay arreglo de userland.
- **Fondos de pantalla:** `hero-run: wallpaper pictures as PNG: 16 put`: los fondos oficiales de serie ya son PNG con su nombre y el Director pudo elegir uno desde Ajustes y verlo. El fondo por defecto (Clownfish) no se fija solo: hay que elegirlo en Ajustes. `herosb` (imagen de la zona DROP) no se puede verificar: SpringBoard no escribe en el log.

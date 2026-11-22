# Por qué iOS no se ve: backboardd y SpringBoard esperan (E-0208, E-0209, E-0212)

Medido con el log persistente (herolog=1) y el muestreador del kernel (`SMP ... bt`), con las direcciones mapeadas a imagen de la caché de dyld (`tools/herolte-smp-images.py`, solo nombre de librería + offset; no hay símbolos de función).

| Qué | Resultado | Nivel |
|---|---|---|
| Superficies que backboardd entrega al panel (ids 3/5) | **todo ceros, también el alfa**, antes y después de limpiar la caché del kernel (FBSRC pass 0 = pass 1), 12 min | L2 |
| Cuadros presentados | 0,1-0,3 por segundo, 25 en 12 min; `vbl=0` | L2 |
| `SpringBoard` hilo principal | casi siempre en `GSEventRunModal` (UIKitCore/GraphicsServices): **UI arrancada e inactiva**; a veces dentro de `BatteryCenter` -> IOKit (llamada síncrona) bajo `CoverSheet` | L2 |
| `backboardd` hilo principal | `CFRunLoop` en espera (mach_msg); hilo de QuartzCore en espera | L2 |
| Registro de vsync | el driver lo implementa como selector 72 y escribe una línea al usarse; **el selector 72 nunca se llama**; iOS usa 68 (2 veces), 74, 79, 84, 50, 52, 55 | L2 |
| `sweetfb_native=1` | corrige `presented as 1440x2560`, no cambia lo anterior | L2 |

Interpretación (hipótesis): `CoreAnimation` en backboardd compone con el renderer de CPU solo cuando su "display link" recibe vsync; nadie lo registra por el selector que el kernel entiende, así que nunca compone y las superficies siguen a cero. No está probado: el parche 0355 registra los argumentos de las primeras 120 llamadas para identificar la llamada de registro real.
Fuentes externas (no medidas aquí): `HEROLTE_PROGRESS.md` de upstream.

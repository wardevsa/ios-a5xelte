# S7GE_BOOT_LOG_EXPECTATIONS — qué mensajes esperar en el primer arranque de la variante mínima (Fase 10, 2026-11-14)

**Lista de expectativas; nada se ha ejecutado en el teléfono.** Se construyó leyendo **las cadenas de texto** del cargador (`loader-clang/xnu_boot.Image`) y del kernel del CI (`kernel.development.herolte`, E-0037) con `strings`, y las descripciones de `docs/herolte-bringup.md`. Una cadena presente en el binario **no prueba que se imprima** ni cuándo; el orden es el esperado por el diseño, **no medido en esta unidad**. Complementa `S7GE_MIN_BOOT_VALIDATION.md` (criterios A-E).

## 1. Cargador (`HEROLTE XNU LOADER`)
| Mensaje | Significado |
|---|---|
| `HEROLTE XNU LOADER` | el cargador arrancó (S-Boot cargó nuestro BOOT) |
| `ENTRY`, `BOOTARGS`, `JUMP TO XNU` | secuencia normal; `BOOTARGS` muestra la línea de arranque **(comprobar que incluye `herowifi=0 heropower=0 herogpu=0`)** |
| `LOADER FAIL: ENTRY OUTSIDE KERNEL` | el cargador no está donde esperaba (imagen o direcciones mal) |
| `LOADER FAIL: BAD SWEETXNU PAYLOAD` | el payload anexo no tiene la firma esperada (imagen mal empaquetada) |
| `LOADER FAIL: PAYLOAD OVERLAPS XNU RAM` | el payload se solapa con la RAM de XNU (tamaño/direcciones) |
| `TWRP EN 30 S` | el cargador falló y muestra el motivo 30 s antes de pedir TWRP |

## 2. Kernel: lo que debe aparecer
- Bloques de color de arranque (entrada, MMU, FP, tunables, `arm_init`) y `XNU ENTRY` / `XNU MMU ON` (`herolte-bringup.md`).
- La **versión del kernel**: `Darwin Kernel Version 22.6.0: Mon Aug 14 05:06:07 UTC 2023; …xnu-8796.141.3` (cadena presente en el binario).
- Con `debug=0xc keepsyms=1` el pánico muestra **símbolos** (`keepsyms=1`): una pantalla de pánico será legible.
- Detección de **8 CPUs** (`cpus=8`) y lectura del UFS/GPT (`HEROLTE UFS …`; el texto exacto no está verificado).
- **Final esperado de N2:** `cannot mount root, errno = %d` (la raíz `ufsroot=USERDATA` es ext4: XNU no la puede montar). **Eso es el éxito del peldaño**, no un fallo.

## 3. Lo que **NO** debe aparecer con la variante mínima (control de que los argumentos se aplicaron)
| Prefijo | Quién lo imprime | Por qué no debe estar |
|---|---|---|
| `HEROLTE WIFI:` | hilo de Wi-Fi | `herowifi=0` |
| `HEROLTE GPU:` | `hg_thread` y la sonda | `herogpu=0` (no se arranca el hilo) |
| `HEROLTE CPU:` / `HEROLTE POWER:` / `HEROLTE TMU:` | medición de CPU / hilo de energía | `herogpu=0` / `heropower=0` |
| `HEROLTE DROP:` | zona DROP | `herodrop=0` |
Si **aparece alguno**, la línea de arranque efectiva no es la prevista: **anotarlo** (es un hallazgo sobre la cadena cargador → kernel, no sobre el hardware) y no seguir con la fase 3 sin entenderlo.

## 4. Lo que puede aparecer aunque se hayan apagado los hilos
- `HEROLTE BUS:` / `HEROLTE DISP:` (el hilo de bus/display arranca siempre y puede imprimir mediciones de DECON; **cuándo y qué no está verificado**), y `HEROLTE FB:` (presentación): no son fallo.
- Mensajes `A5XELTE CPU: expected boot MPIDR …`: el binario los contiene (código de otra placa en el mismo árbol); **si aparecen, anotarlos con la línea completa**: sería una señal de un supuesto de MPIDR del A5XELTE que no se cumple, no un daño.

## 5. Cómo anotar lo que se vea
Vídeo continuo de la pantalla (los textos pasan en segundos); transcribir **literalmente** las últimas 5-10 líneas antes de cualquier parada, pánico o reinicio; anotar el tiempo desde que se soltaron los botones y si hay reinicios; **no inferir** la causa de lo que no se ve (con `herolog=0` no hay log persistente). Resultado en `evidence.toml` como evidencia del dispositivo (`device = "this-unit"`), con el hash de la imagen probada.

## 6. Lo que esta lista no cubre
Ningún mensaje de iOS (launchd, SpringBoard): no se alcanzarán sin raíz; no hay verificación de GPU, Wi-Fi ni energía; el texto exacto de los mensajes de UFS y de CPUs no se ha comprobado.

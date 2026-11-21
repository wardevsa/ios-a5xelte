# S7GE_PATCH_DEPENDENCIES — dependencias entre los parches de GPU y qué se puede consolidar (Fase 5, 2026-11-14)

**Solo análisis; no se ha cambiado ni retirado ningún parche.** Método: barrido automático de los 260 parches de `xnu/patches/` (los 108 que tocan `herolte_gpu.c`, `HeroGPU.cpp`, `SweetSurface*`, `SweetFramebuffer.cpp`, `herolte_gl.c` o llevan gpu/mali/surface en el nombre; el inventario S7GE_INVENTORY.md usa un filtro algo más estrecho, 86). Dependencia entre parches = **tocan la misma función** (contexto de hunk `@@ … @@ función`) o el mismo fichero en secuencia. **Aproximación:** un hunk sin nombre de función no se ve, y "mismo fichero" no es "mismo código"; no he aplicado ni compilado nada para esto. Nivel **L1**.

## 1. Estructura de la dependencia
- **La serie es un orden total sobre cada fichero compartido.** Parches por fichero: `herolte_gpu.c` **63** (0225→0334), `SweetFramebuffer.cpp` 34 (0046→0330), `herolte_gl.c` 12, `SweetSurface.cpp` 9, `HeroGPU.cpp` 6 (0239→0260), `herolte_drop.c` 5, `herolte_ufs.c` 6, `herolte_wifi.c` 7. Los parches de un mismo fichero **no se pueden reordenar libremente**: cada uno asume el texto que dejó el anterior.
- Los más **referidos** (otros parches tocan las mismas funciones después): `0061-sweet-iphone-x-display-size` (23), `0056-sweet-fb-throttled-present` (21), `0226-herolte-mali-first-job` (20), `0124-a5xelte-fb-pacing-metrics` (19), `0109-a5xelte-decon-iosurface-bridge` (18), **`0239-herolte-herogpu-user-client` (18)**, `0235-herolte-gpu-present` (17), `0231-herolte-mali-gpu-copy` (16).
- Los más **dependientes** (tocan funciones de muchos anteriores): `0330-screen-off-and-heat-rates` (24), `0322-two-panel-buffers` (24), `0333-gpu-wait-asleep` (20), `0276-scaled-default-surface-own-memory` (20), `0298-frames-in-the-blank` (19), `0291-show-frames-at-once` (17).
- **Hay un núcleo que no se puede quitar:** `0225` (crea `herolte_gpu.c`), `0239` (crea `HeroGPU.cpp` y la API `herolte_gpu_*`), `0243` (quirks T880), `0247` (barrera de escritura), `0249` (recuperación y reutilización de VA), `0307` (pool L3 propio), `0333/0334` (espera dormida): lo que el cliente actual usa o corrige un fallo real.

## 2. Parches cuyo código fue casi todo sustituido después (candidatos a consolidar)
Fracción de líneas **añadidas** por el parche y **retiradas** literalmente por uno posterior (≥ 30 %, ≥ 5 líneas):
| Parche | Líneas añadidas | Retiradas después | Sustituido sobre todo por |
|---|---|---|---|
| 0226 `mali-first-job` | 135 | 57 % | 0227 |
| 0227 `mali-fragment-clear` | 149 | 35 % | 0228, 0230 |
| 0243 `t880-quirks` | 19 | 37 % | 0249 |
| 0256 `clock-boot-arg` | 15 | 40 % | 0267, 0273 |
| 0259 `surface-over-client-memory` | 22 | 36 % | 0332 |
| **0266 `clock-down-on-read-faults`** | 10 | **100 %** | 0273 |
| **0268 `log-memory-and-bus-rates`** | 10 | **100 %** | 0269 |
| 0271 `mongoose-1976mhz` | 49 | 61 % | 0330, 0272 |
| 0284 `vsync-deadlines` | 15 | 33 % | 0298, 0288 |
| **0292 `decon-probe`** | 17 | **100 %** | 0293 |
| 0294 `disp-pll` | 16 | 75 % | 0295, 0296 |
| **0295 `dsim-multi-pkt`** | 10 | **100 %** | 0296 |
| 0296 `vclk-on-disp-pll` | 10 | 70 % | 0297 |
| 0304 `wifi-pcie-probe` | 70 | 67 % | 0306 |
La mayoría son **sondeos y experimentos** (display, Wi-Fi, relojes) que se fueron refinando parche a parche; su código final vive en otros parches.

## 3. Qué se puede hacer con eso (propuesta; nada aplicado)
**No eliminar parches sueltos:** como la cadena es secuencial, quitar uno rompe la aplicación de los siguientes. La vía segura es **rebasar la serie**:
1. Aplicar la serie actual a una copia del árbol base y guardar el árbol resultante (`git write-tree` del estado final).
2. Generar **un parche de consolidación por subsistema** (GPU núcleo, superficies, GL, display, audio, Wi-Fi, relojes) cuya suma sea **idéntica byte a byte** al árbol resultante (prueba: el árbol de la serie nueva tiene el mismo hash que el de la antigua).
3. La serie antigua se **conserva** (historia y trazabilidad con upstream, D-0014); la consolidada es una **segunda serie** que se compila en el CI en paralelo y debe producir un **kernel con el mismo contenido** (mismos símbolos y mismo `kernel.development.herolte` salvo marcas de compilación).
4. Solo entonces se plantea que S7GPU sustituya `herolte_gpu.c`.
Riesgo principal: que el upstream (`origin/herolte`) siga añadiendo parches sobre el fichero antiguo; la consolidación debería ser una **rama paralela**, no sustituir la serie de `herolte`. Es cambio de nivel B y el rango 0400+ (D-0007, propuesta) está pensado para esto.

## 4. Lo que no puedo afirmar
No he comprobado que cada parche aplique por separado (solo en bloque, E-0035 para 0332-0337); el recuento de "líneas retiradas" es textual (una línea movida o reformateada cuenta como retirada y nueva); no he leído los 62 parches que no son del núcleo de GPU salvo por el nombre y los comentarios.

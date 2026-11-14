# S7GE_MESA_VERSION_ANALYSIS — Mesa 25.0.7 frente a 26.2.4 y licencias (Fase 12, 2026-11-14)

**Medido en el PC, con fuentes públicas descargadas (clon superficial de los tags `mesa-25.0.7`, `mesa-26.2.4` y `libdrm-2.4.124`, en un directorio aparte del scratchpad; no se ha enviado nada del proyecto).** Nivel de evidencia **L1** (aplicabilidad de un script y lectura de ficheros). **No se ha compilado Mesa**: el destino es Darwin/iOS (SDK de Apple y compilación cruzada o en un macOS) y este PC es Linux: la compilación sigue siendo cosa del CI (`mesa-ios.yml`). Esto responde a la fase pedida ("¿compila Mesa 25.0.7 con los parches actuales?") **solo en la parte que se puede medir aquí**.

## 1. Resultado principal
| Pregunta | Resultado medido |
|---|---|
| ¿Aplica `gpu/mesa/patch-mesa.py` a **Mesa 25.0.7**? | **Sí: las 12 ediciones aplican** (cada una exige que el texto aparezca exactamente una vez) y se añaden `osmesa_hero.inc` y `hero_hw.c`; efecto: 7 ficheros de Mesa modificados, +295 −3 líneas |
| ¿Aplica a **Mesa 26.2.4**? | **No tal cual.** El fichero `src/gallium/targets/osmesa/osmesa_target.c` **no existe** (`src/gallium/frontends/` de 26.2.4 no tiene `osmesa`). *Corrección (2026-11-14, `S7GE_OSMESA_MESA26_COMPATIBILITY.md` §4):* con el frontend reinyectado, **10 de las 12 ediciones aplican y 2 fallan** (ambas en `pan_kmod.h`); la cifra "al menos 3" salió de una segunda pasada sobre un árbol ya modificado |
| ¿Cuándo desapareció OSMesa? | Las notas de versión de Mesa lo dicen: **25.1.0: "Remove osmesa"** (y 25.2.0 limpia la opción de meson). **25.0.7 es, por tanto, la última versión con OSMesa** (la serie 25.0 acaba en 25.0.7) |
| ¿Existe el tag `libdrm-2.4.124`? | Sí (se usa solo para las cabeceras `xf86drm.h`, `drm.h`; la biblioteca la sustituye `herodrm.c`) |

## 2. Consecuencia estratégica (no es un detalle de versión)
**La ruta actual de OpenGL ES (OSMesa + Panfrost) está atada a una serie de Mesa que ya no se mantiene** y **no se puede actualizar parcheando**: la pieza que usa el proyecto (el *frontend* OSMesa y sus puntos `OSMesaSweet*`) **no existe** en Mesa ≥ 25.1. Quedan tres caminos, ninguno decidido: (1) **quedarse en 25.0.7** y asumir que no habrá correcciones (seguridad y Panfrost T880 incluidos); (2) **mantener nosotros el frontend OSMesa** como código propio (copiarlo de 25.0.x a un parche/árbol del proyecto, con su licencia MIT); (3) pasar a **otra superficie de Mesa** (p. ej. un frontend propio sobre `pipe_screen`/*gallium* o el `dri` sin X) — lo que encaja con el diseño S7GL/S7MCL del macroinforme (§11) y es trabajo de diseño. **Recomiendo no tocar nada ahora y decidirlo en la fase de S7GL** (nivel B, jefatura): el atajo (1) es lo que funciona hoy.
Esto afecta además a `gpu/mesa/patch-mesa.py`: su "falla en alto si Mesa cambia" funcionó exactamente como se diseñó (lo detectó).

## 3. Licencias de Mesa 25.0.7 y libdrm 2.4.124 (cierra el punto abierto de S7GE_LICENCIAS.md)
Revisado en las carpetas que se enlazan (`src/mesa`, `src/gallium/auxiliary`, `src/panfrost`, `src/compiler`, `src/util`, `src/gallium/drivers/panfrost`, `src/gallium/drivers/softpipe`, `src/gallium/frontends/osmesa`, `src/gallium/targets/osmesa`; ~2 000 ficheros fuente):
- `docs/license.rst`: "El núcleo de Mesa está bajo licencia **MIT**; la mayor parte del código es MIT, pero algunos ficheros tienen licencia propia" y manda **consultar el SPDX de cada fichero**.
- Los identificadores **SPDX presentes en esas carpetas son todos `MIT`** (p. ej. 107 en `src/panfrost`, 78 en `src/compiler`, 54 en `src/util`); **la mayoría de los ficheros no lleva SPDX** (cientos por carpeta) y usa la cabecera "Permission is hereby granted…" (MIT en forma de texto, 1 676 ficheros).
- **No hay GPL/LGPL/Apache** en esas carpetas (búsqueda de texto y de SPDX). Excepciones menores: **1 fichero con licencia Boost** (`src/gallium/auxiliary/gallivm/f.cpp`; `gallivm` es la parte de LLVM, que **no se compila**: `-Dllvm=disabled`), **~22 ficheros con avisos tipo BSD** y **6 de dominio público** (`src/util/sha1`, `rand_xor.c`, `fast_idiv_by_const.c`, etc.).
- **libdrm 2.4.124** (cabeceras que usa `herodrm.c`): `xf86drm.h` y `drm/drm.h` llevan el aviso MIT; `include/` lleva SPDX `MIT` (y los `drm-uapi` de Mesa algunos con `GPL-2.0 WITH Linux-syscall-note`, que es la nota habitual de las cabeceras de la API del kernel de Linux).
**Veredicto (no jurídico):** lo que enlazamos es **MIT con alguna cabecera BSD/dominio público**, compatible con distribuir bajo MIT y con el resto del proyecto; hay que **adjuntar el aviso de Mesa** al redistribuir binarios. **No verificado:** dependencias transitivas (zlib, expat), las cabeceras `drm-uapi` en uso concreto, y que los ficheros "sin SPDX" no tengan una cabecera distinta (solo se buscó por palabras clave).

## 4. Qué NO se hizo
No se compiló nada; no se probó que el Mesa parcheado funcione; la comprobación de 26.2.4 se limita a la aplicabilidad del script (el resto de ediciones, posteriores al fallo del fichero ausente, no se evaluaron); no se midió ningún tag intermedio (25.1.x, 25.2.x).

## 5. Decisión de la jefatura técnica (2026-11-14, nivel B) y matices medidos
**Opción B: mantener OSMesa nosotros** (D-0031); la **implementación espera la confirmación del Director**; la política está en `S7GE_OSMESA_FORK_POLICY.md`. Añado dos datos que afinan la decisión (sin cambiarla):
- Si "mantener OSMesa" significa **quedarse con Mesa 25.0.7 entera**, el coste de Panfrost T880 (sin correcciones) sigue ahí; si significa **solo el frontend sobre un Mesa más nuevo**, hay una **señal a favor**: las 18 funciones de Mesa que usa `osmesa.c` existen en 26.2.4 con la misma declaración (no compilado). La política distingue las dos formas (B1/B2).
- La decisión de migrar de superficie **queda para S7GL**, como decide la jefatura.


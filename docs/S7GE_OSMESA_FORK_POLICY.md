# S7GE_OSMESA_FORK_POLICY — política de mantenimiento del OSMesa propio (2026-11-14)

**Decisión de la jefatura técnica (nivel B, 2026-11-14): Opción B, "mantener OSMesa nosotros".** Se registra como **D-0031**. **La implementación NO está autorizada** (el propio mensaje de jefatura lo dice: esperar la confirmación del Director): este documento fija la **política**; **no existe ni se crea** `gpu/mesa/osmesa-fork/`, y no se toca `gpu/mesa/` ni ningún parche. Contexto y medidas: `S7GE_MESA_VERSION_ANALYSIS.md`.

## 1. Qué es "el OSMesa propio" (dos formas posibles; hay que elegir una al implementar)
| Forma | Qué se mantiene | Qué viene de Mesa | Coste real |
|---|---|---|---|
| **B1 · congelar Mesa 25.0.7 entera** (vendorizada o clonada con el hash `742a20f4…` del tag) | todo lo que ya parcheamos | nada nuevo: **Panfrost/NIR/Midgard quedan en 25.0.7** | casi cero hoy; **sin correcciones de Panfrost T880** futuras, y la seguridad de Mesa pasa a ser nuestra |
| **B2 · solo el frontend OSMesa** (`src/gallium/frontends/osmesa/osmesa.c`, **1 286 líneas** en 25.0.7, + el destino `targets/osmesa`) como código propio, **sobre un Mesa más nuevo** | ese frontend y su glue (`osmesa_hero.inc`, `hero_hw.c`) | Panfrost, NIR, state tracker de la versión nueva | **medido a favor** (ver §2) pero **no compilado**: cada Mesa nueva puede romper el contacto con los internos |
La jefatura describe un directorio `gpu/mesa/osmesa-fork/{src/gallium/frontends/osmesa, patches, README.md}`, que corresponde a **B2** (con parches y README propios). **Esto no está decidido entre B1 y B2**: lo pide el texto de la propia decisión ("evaluar EGL, GBM o superficie propia en S7GL").

## 2. Lo que se midió sobre la viabilidad de B2 (PC, solo lectura)
- `osmesa.c` de 25.0.7 llama a **18 funciones** de Mesa con prefijos `_mesa_`, `st_`, `pipe_`, `util_`, `u_`, `cso_`: **las 18 existen en 26.2.4 y su primera declaración encontrada es idéntica**; los **12 tipos** `struct st_*`/`pipe_*` que usa también existen.
- **Límites de esa medida:** compara el texto de la primera declaración, **no el contenido de las estructuras** ni el comportamiento; **no se compiló** nada; no se midió ninguna versión intermedia. Es una **señal a favor**, no una prueba.
- Las 3 ediciones de `patch-mesa.py` que fallan en 26.2.4 (en `meson.build` y `pan_kmod.h`, de la parte Panfrost) son **un problema aparte**: B2 no las evita.

## 3. Política de mantenimiento (la de la jefatura, con matices)
1. **Solo correcciones críticas de seguridad** en el código del fork; sin intentar paridad con upstream.
2. Cada corrección se documenta con **referencia al CVE o al bug**, el commit de Mesa de origen (si existe) y su prueba. **Matiz:** si el resto de Mesa queda en 25.0.7 (B1), **no hay quien publique CVEs** para esa serie: la obligación de vigilar avisos es **nuestra** y debe asignarse a alguien (hoy no lo está).
3. **Revisión trimestral:** ¿ha vuelto OSMesa o hay alternativa en Mesa? ¿hay CVEs relevantes para `src/mesa`, `src/gallium/auxiliary`, `src/util`, Panfrost? Registrar la revisión en `governance/` (tarea periódica).
4. **Trazabilidad:** el fork guarda el **hash del commit de Mesa** de partida, la lista de diferencias respecto a él (`git diff` reproducible) y la licencia (MIT, con las cabeceras originales; S7GE_LICENCIAS.md).
5. La **migración a otra superficie** (EGL, GBM o una propia) se decide en la fase S7GL, no antes (decisión de la jefatura).

## 4. Condiciones previas para implementar (no cumplidas hoy)
(a) Confirmación del **Director** (lo exige la jefatura); (b) elegir **B1 o B2**; (c) tener un **entorno de compilación de Mesa para iOS** reproducible (hoy solo el CI de macOS; `mesa-ios.yml`) para poder probar cada cambio; (d) decidir quién vigila los avisos de seguridad; (e) licencia declarada para el código propio de `gpu/mesa/` (hoy sin licencia).

## 5. Riesgos
Mantener código ajeno sin pruebas automáticas del kernel/Mesa (S7GE_CONSOLIDATION_RISKS R10); la obsolescencia silenciosa de Panfrost para T880; que un fallo de Mesa 25.0.7 en esta unidad (p. ej. los `0x42`) **no tenga solución upstream**.

# S7GE_IR_DESIGN — diseño parcial de S7GIR (Fase 3, 2026-11-14)

**Solo diseño; no hay compilador ni código.** Desarrolla `S7GE_ARCHITECTURE.md` §9 (S7GTE y S7GIR): usa **las diez categorías de nodo** que fija el macroinforme y su ejemplo conceptual (§9.3), y su regla de oro (§9.4): *si una operación no se puede representar bien, falla de forma explícita; no se altera en silencio la semántica de la app*. Lo que depende de Midgard no medido se marca *(depende de hardware)*. Lo que sale de código de este proyecto se cita.

## 1. Forma general
- **Módulo S7GIR** = lista **ordenada** de nodos por *command buffer*, con **identificadores locales** (u32) y referencias por id, nunca por puntero. Inmutable una vez validado.
- Cada nodo: `{ op, id, flags, deps[] (ids anteriores), attrs (según op) }`. Los recursos se referencian por **handle** del ABI (S7GE_ABI_V2_PROPOSAL.md §2): la IR no contiene direcciones.
- **Dos niveles:** (a) *IR de comando* (esta fase): recursos, pipelines, pases, dibujos, copias, barreras, fences, presentación; (b) *IR de shader* (S7SHC: AIR→SPIR-V→NIR→Midgard, macroinforme §10), **fuera de esta fase**: aquí un shader es un recurso opaco compilado con su interfaz (entradas/salidas, recursos que lee).

## 2. Tipos de nodo (las 10 categorías del macroinforme → operaciones)
| Categoría | Operaciones iniciales | Atributos clave |
|---|---|---|
| **Device** | `DEVICE_QUERY` | capacidades del ABI (`S7_CAPS`): nº de AS, límites, formatos |
| **Resource** | `BUFFER_CREATE`, `TEXTURE_CREATE`, `RESOURCE_IMPORT_SURFACE`, `RESOURCE_DESTROY` | tamaño, formato, usos (`RENDER_TARGET`, `SAMPLED`, `VERTEX`, `UNIFORM`…), tiling, alineación, propietario |
| **Shader** | `SHADER_BIND` (resuelve el binario compilado y su caché) | stage, interfaz, hash de fuente, versión del compilador |
| **Pipeline** | `PIPELINE_RESOLVE` | shaders, formato de vértices, topología, **estado fijo** (blend, depth, stencil, cull, MSAA) |
| **RenderPass** | `RENDER_BEGIN`, `RENDER_TARGET_BIND`, `RENDER_END` | adjuntos, `loadOp`/`storeOp`, tamaño en tiles |
| **Draw** | `DRAW`, `DRAW_INDEXED`, `DRAW_INDIRECT` (sin soporte inicial) | geometría, instancias, rangos de buffers |
| **Blit** | `COPY_BUFFER`, `COPY_TEXTURE`, `CONVERT` | rangos, formato origen/destino |
| **Barrier** | `BARRIER` | recursos afectados, uso previo→uso siguiente |
| **Fence** | `FENCE_SIGNAL`, `FENCE_WAIT` | fence, valor monótono |
| **Present** | `PRESENT` | superficie/drawable, tiempo objetivo (vsync) |
Las operaciones del ejemplo del macroinforme (§9.3) se mapean 1:1: `CreateTexture→TEXTURE_CREATE`, `BeginRenderPass→RENDER_BEGIN`+`RENDER_TARGET_BIND`, `Draw→DRAW`, `Commit→SUBMIT+FENCE`.

## 3. Estados de recurso y dependencias
Cada recurso tiene un **estado de uso** (`UNINIT`, `RT_WRITE`, `SAMPLED_READ`, `COPY_SRC`, `COPY_DST`, `PRESENT`, `FREED`); cada nodo declara el estado que requiere y el que deja. El validador exige que **entre dos usos incompatibles haya un `BARRIER`** (o una dependencia explícita `deps[]`); un `RENDER_END` con `storeOp=STORE` deja el recurso en `SAMPLED_READ` solo si se emitió barrera. *(La traducción a las dependencias del job manager de Midgard —índice de job y dependencias en la cabecera, p. ej. el índice de `WRITE_VALUE` en el offset 18 que se ve en `herolte_gpu.c`— es un detalle del backend y depende de hardware.)*

## 4. Validación semántica (§9.4 del macroinforme) — reglas por nodo
Todo nodo falla con un código explícito si incumple: **tipo** (el handle es del tipo esperado), **tamaño** (sin overflow; `offset+len ≤ size`), **alineación** (p. ej. filas de superficie múltiplo de 64 B, como en 0252/0254), **formato** (existe y es permitido para el uso), **estado** (transición válida, §3), **dependencias** (existen y son anteriores; sin ciclos), **permisos** (el contexto es dueño del recurso, entitlement), **límites** (nº de adjuntos, tamaño de textura, nº de nodos del buffer) y **resultado esperado** (qué cambia). Ejemplos de rechazo explícito: `DRAW` sin pipeline resuelto; textura con formato sin equivalente en Midgard; `RENDER_BEGIN` con adjuntos de tamaños distintos; `PRESENT` de una superficie ajena.
**Nada se "arregla" en silencio:** una conversión de formato con pérdida solo si el nodo la pide (`CONVERT`) y queda en la traza (S7TRACE).

## 5. Qué hace el backend con la IR *(depende de hardware; solo orientación)*
`RENDER_BEGIN…RENDER_END` con sus `DRAW` → jobs *vertex/tiler* + un job *fragment* con **MFBD multi-target** (el formato que ya funciona en esta unidad del upstream: Local Storage/Parameters/Tiler Context/Weights/Render Target, 0227); `BARRIER` → dependencias entre jobs; `FENCE_*` → S7FENCE (hoy sondeo, fase posterior); `PRESENT` → la ruta actual de presentación (`herolte_gpu_present_*`) hasta que exista S7PRES. Los *blits* simples pueden ir por job de copia de GPU como `hg_gpu_copy_test` (0231) o, si no cabe, por CPU **con fallback explícito** (principio 2.8, no silencioso).

## 6. Representación serializable (para tests y trazas)
Texto canónico estable, una línea por nodo: `n12 DRAW pipe=n7 vb=n3[0:4096] first=0 count=3 inst=1 deps=[n11]`. Sirve para **pruebas de host** (validador sobre IR escrita a mano o generada de una traza), para *golden files* y para S7TRACE. Un formato binario de transporte queda para cuando haya `S7MCL` real.

## 7. Plan de pruebas del validador (sin hardware)
1. Banco de **IR válidas** (las diez categorías, ejemplo §9.3) → aceptadas. 2. **IR inválidas** una por regla de §4 → cada una produce el código esperado y ningún otro. 3. Mutación de una IR válida (borrar una barrera, cambiar un tamaño, un handle viejo) → rechazo. 4. Propiedad: ningún nodo aceptado referencia memoria fuera de sus recursos. Todo esto es nivel A (host) cuando se autorice implementarlo.

## 8. Decisiones abiertas
- ¿IR por command buffer o por frame completo? (el macroinforme da la unidad al *command buffer*; la composición de iOS submite muchas, S7COMP.) - ¿Los `DRAW_INDIRECT` entran en la v1 o se rechazan explícitamente? - ¿Quién fija la lista de formatos iniciales (macroinforme §17.3)? - Lugar de código: `s7ge/ir/` según la estructura propuesta del macroinforme §24 (no creado).

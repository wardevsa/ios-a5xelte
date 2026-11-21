# S7GE_ABI — el ABI real de `HeroGPU` y su brecha frente a S7GE (T-0008, 2026-11-13)

**Informe de solo lectura; no cambia código.** Describe lo que el kernel hace **hoy** (nivel L1: código leído y compilado en el CI; L3h/L4h en el teléfono del upstream, **no en esta unidad**) y lo compara con los principios de `docs/S7GE_ARCHITECTURE.md` (§2.5, §13, §14, §15, §23). Toda "brecha" es una **propuesta** (`architecture-change`, nivel B): ninguna está aprobada.

**Fuente leída (entera):** `iokit/Kernel/arm/HeroGPU.cpp` (539 líneas) y las funciones `herolte_gpu_up/va_alloc/map/unmap/submit` y `hg_run` de `bsd/dev/herolte_gpu.c` (3465 líneas), tal como están en el árbol XNU parcheado del kit (`~/HackiOS/builds/device-day/artifacts/buildtree-0332-fork-8d1cf43/buildtree.tgz`, hasta nuestro `0332`; **no incluye** el `0333`/`0334` de upstream, que solo cambian `herolte_gpu.c` para dormir en la espera). Parches de origen: `0239`, `0248`, `0249`, `0258`. **No leí** el resto de `herolte_gpu.c` (3000 líneas de arranque, energía, recuperación y descriptores de prueba) más allá de lo citado, ni el sandbox de iOS.

## 1. Cómo se abre
`IOServiceMatching("HeroGPU")` → `IOServiceOpen(type 0)`. `HeroGPU::start` publica `GPU = "Mali-T880 MP12"` y (con `heroaccel` ≠ 0) un servicio vacío `IOAcceleratorES` (`0260`, sin cliente de usuario).
`HeroGPUUserClient::initWithTask` reserva un lock y una tabla de **4096** entradas de BO (`HEROGPU_MAX_BOS`) y llama a `herolte_gpu_up()`: **el primer cliente enciende la GPU**. **No comprueba tarea, firma, entitlement ni privilegio** (`IOUserClient::clientHasPrivilege`/`IOTaskHasEntitlement` no aparecen). Lo único que hoy limita quién abre `HeroGPU` sería el *sandbox* de iOS (regla `iokit-open`), que **no he verificado** y que no es una comprobación del driver.

## 2. Los 8 selectores (scalar in → scalar out)
| # | Nombre | Entradas → salidas | Qué valida el kernel | Qué NO valida / riesgo |
|---|---|---|---|---|
| 0 | `GetParam` | `[param]` → `[valor]` | `herogpu_param` traduce números de parámetro de Panfrost a registros de identificación (GPU_ID, `*_PRESENT`, features…); `herolte_gpu_reg` rechaza offsets ≥ 0x1000 o no alineados | Lectura de solo identificación; riesgo bajo. Devuelve 0 para parámetros desconocidos (no distingue "no soportado" de "valor 0") |
| 1 | `CreateBO` | `[size]` → `[handle, gpu_va, size]` | `size` redondeado a 4 KiB, 0 < size ≤ **256 MiB** (`HEROGPU_MAX_BO_BYTES`); la memoria se **pone a cero** y se limpia de caché antes de mapearse; se asigna VA y se mapea; si algo falla se deshace | **Sin presupuesto total**: 4096 BO × 256 MiB por cliente de memoria **cableada**; sin tope global entre clientes (DoS de memoria). El `handle` es `índice + 1` (1..4096) |
| 2 | `FreeBO` | `[handle]` | 1 ≤ handle ≤ 4096 y ranura en uso. `herogpu_bo_free` **primero desmapea de la GPU** (con `hg_mtx`: espera a que acabe el job en curso) y **después** libera la memoria y la superficie | **El handle se reutiliza al instante** (sin generación): un handle viejo apunta al BO nuevo (ABA). La VA liberada también se reutiliza |
| 3 | `MapBO` | `[handle]` → `[dirección de usuario]` | handle válido; mapea una vez en la tarea del cliente con caché *write-combined* (o la de la superficie) | Sin selector de desmapeo (solo `FreeBO`/cierre) |
| 4 | `Submit` | `[jc_va, js]` → `[status, µs]` | `js` = (≠0 ? 1 : 0); `jc_va ≠ 0`; GPU encendida. Serializado con `hg_mtx`, **síncrono**, sondeo acotado (~200 ms; con `0333` duerme en trozos); si falla, `hg_recover` | **`jc_va` es una VA de GPU arbitraria del cliente: no se comprueba que esté dentro de un BO suyo, ni siquiera dentro del rango de usuario** (`HGU_VA_BASE..END`). La **cadena de jobs y los descriptores los construye el cliente** (Mesa) y apuntan a cualquier VA mapeada. Hay **una sola address space (AS0) compartida por todos los clientes** |
| 5 | `Log` | struct texto | recorta a 1024 bytes y lo envía al log del kernel con el nombre del proceso | Sin límite de frecuencia (inundación del log, que además se persiste) |
| 6 | `SurfaceBO` | `[id IOSurface]` → `[handle, va, size, bytesPorFila, ancho, alto, formato, offset, planos]` | `sweet_surface_copy(id)` **retiene** la superficie (se libera en `FreeBO`); comprueba `allocSize` y que el tamaño no excede la memoria ni 256 MiB; páginas físicas alineadas; sincroniza cachés al importar | **Búsqueda global por id**: no comprueba que el llamante sea dueño de la superficie ni que tenga derecho a ella; los ids son pequeños y consecutivos |
| 7 | `SyncBO` | `[handle]` | handle válido | Solo hace algo si el BO es una superficie importada (limpia e invalida cachés); no sirve para BO normales |
| otro | — | — | `kIOReturnUnsupported` | — |
Errores devueltos hoy: `BadArgument`, `NoResources` (tabla llena), `NoMemory`, `NotFound` (superficie), `Unsupported`; el resultado de un job es un `status` crudo (`JS_STATUS`, o `~0` si no corrió), sin distinguir fallo de MMU, de job, de tiempo agotado o de energía.

## 3. Ciclo de vida y concurrencia (lo que sí está bien)
- **Desmapear antes de liberar:** `herogpu_bo_free` hace `herolte_gpu_unmap` (PTE a cero + flush de MMU, bajo `hg_mtx`) y solo después suelta la memoria: no hay uso tras liberación por parte de la GPU en el camino normal.
- **Serialización:** un job a la vez; `FreeBO` o el cierre del cliente **esperan** al job en curso (mismo `hg_mtx`).
- **Retención de superficies:** `sweet_surface_copy` retiene, `FreeBO` libera.
- **Memoria a cero** en `CreateBO`; **sin MMIO ni direcciones físicas** expuestos al cliente (solo VA de GPU y una dirección de usuario); `Submit` no se hace bajo el lock del cliente (no bloquea `Log`/`SyncBO`).
- **Cierre:** `clientClose → terminate → free()` libera todos los BO.

## 4. Brecha frente a S7GE (`§` del documento de arquitectura)
| Requisito S7GE | Estado hoy | Gravedad | Mejora propuesta (nivel B, **no aplicada**) |
|---|---|---|---|
| §23.1 Handles opacos **con generación** | `índice+1`, reutilizable al instante | media (ABA dentro de un mismo cliente) | handle = `(generación << 16) \| índice`; la generación se incrementa al liberar |
| §2.5 / §23 "el cliente no aporta direcciones de GPU ni descriptores" | `Submit` recibe `jc_va`; la cadena la escribe el cliente | **alta** | corto plazo: aceptar `jc_va` solo si cae dentro de un BO del cliente; **estructural:** una **address space por cliente** (la Midgard expone varias AS —registro `AS_PRESENT`, **no leído aquí**—; hoy el código solo usa AS0) para que un cliente no vea la memoria de otro; largo plazo: construir los jobs en el kernel (S7JMQ) |
| §23.3 Entitlements | ninguna comprobación en el driver | alta | exigir un entitlement a la tarea en `initWithTask` (p. ej. el de `hero-run.entitlements`) y rechazar el resto; auditar el perfil de sandbox |
| §23.2 Presupuesto de memoria | solo tope por BO | media | presupuesto por cliente y global; rechazar con `NoResources` |
| §23.4 Aislamiento entre clientes | **AS0 única y compartida; `SurfaceBO` global** | **alta** | AS por cliente; comprobar propiedad/derecho en `SurfaceBO` |
| §23 Versión y tamaño en cada petición | selectores escalares sin versión | baja | un selector de versión/capacidades (`S7MCL_ABI_*`) y estructuras con `version`/`size` |
| §22.3 Errores que distingan causa | `status` crudo | media | códigos propios (MMU fault, job fault, timeout, energía) |
| §15 Fences y finalización verificable | `Submit` síncrono, sondeo, sin fences ni IRQ | media (aceptable al principio, §15.1) | fences monótonas + IRQ de job/MMU/GPU por GICv2 tras auditar el mapa de interrupciones (S7JMQ) |
| §13.4 Retención ante timeout ambiguo | tras el tiempo agotado se llama a `hg_recover` (recuperación del hardware); los BO siguen en poder del cliente hasta `FreeBO`/cierre | por revisar | documentar y probar qué estado de GPU queda; no liberar páginas hasta confirmar el reinicio |
| §22 Observabilidad | una línea de log por selector y fallos de job | baja | S7TRACE: contadores por cliente |
**Lo que NO he verificado** y que cambiaría la gravedad: qué direcciones físicas del kernel (tablas de páginas, memoria de pruebas, framebuffer) están **mapeadas en AS0 y por tanto alcanzables** desde un job de cliente (fuera del rango de usuario); el perfil de sandbox de iOS para `iokit-open` sobre `HeroGPU`; el comportamiento de `hg_recover` bajo un job malicioso; el código de `herogpu_param` más allá de los casos leídos.

## 5. Siguientes pasos (no hechos)
1. **Auditoría dirigida de AS0:** listar todo lo que `hg_tables`/`hgp_*` mapea en la address space única (T-0010, `S7GE_HARDWARE.md`).
2. Decisión de arquitectura (nivel B, revisor jefe técnico): AS por cliente + validación de `jc_va` + entitlement. Es una modificación del kernel y de la serie de parches: **no se hace sin esa revisión** (D-0011 describe cómo se registra).
3. Pruebas: hoy no hay pruebas de host de `HeroGPU.cpp`; un banco con un doble de `herolte_gpu_*` permitiría probar las validaciones de handles y presupuestos sin hardware (nivel A, tarea futura).

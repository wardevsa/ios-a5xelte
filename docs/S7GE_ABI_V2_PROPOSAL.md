# S7GE_ABI_V2_PROPOSAL — propuesta de ABI kernel↔userland para S7GE (Fase 2, 2026-11-14)

**Es una PROPUESTA de diseño; no se implementa nada.** Cambiar la interfaz de `HeroGPU` es nivel **B** (arquitectura/interfaz crítica): necesita la revisión de la jefatura técnica antes de cualquier código. Parte de `S7GE_ABI.md` (ABI actual, 8 selectores), `S7GE_HARDWARE.md` (AS0 y tablas escribibles), `S7GE_EXECUTION_MODEL.md` y de los requisitos del macroinforme §23 (handles con generación, validación, entitlements, aislamiento). Lo que dependa de hardware no medido va marcado *(depende de hardware)*. Cierra la propuesta D-0015 con un diseño concreto; no la sustituye.

## 1. Objetivos y no-objetivos
**Objetivos:** (1) ningún cliente puede leer ni escribir memoria de otro ni del kernel, (2) un fallo de un cliente no deja la GPU inutilizable para el resto, (3) errores con causa, (4) versionado explícito, (5) camino de migración desde el ABI actual sin romper Mesa/hakios-gl de golpe.
**No-objetivos de esta fase:** interrupciones y fences completas (S7FENCE, fase posterior), construir los jobs en el kernel (S7JMQ), DVFS dinámico.

## 2. Modelo de objetos
| Objeto | Qué es | Propietario |
|---|---|---|
| **Cliente** | un `IOUserClient` abierto por una tarea; lleva el entitlement comprobado en `initWithTask` | la tarea |
| **Contexto** | espacio de direcciones de GPU + cola lógica de un cliente | el cliente (1..N por cliente, tope fijo) |
| **BO** | memoria cableada de GPU, ligada a un contexto; opcionalmente importada de un IOSurface | el contexto |
| **Job** | cadena de descriptores ya **validada** y copiada/anclada | el contexto |
Todo identificador visible al userland es un **handle opaco de 64 bits**: `[ generación 24 | tipo 8 | índice 32 ]`; la generación sube al liberar el hueco; un handle viejo da `S7_E_STALE`. Nunca se devuelven direcciones físicas ni de kernel.

## 3. Aislamiento de memoria *(el núcleo del cambio)*
1. **Una AS por contexto** *(depende de hardware: `AS_PRESENT` no se ha leído en esta unidad; la Midgard T880 expone varias AS en las plantillas de Panfrost/kbase, no verificado aquí)*. Si solo hubiera una AS usable, el fallback es **un contexto activo a la vez** con cambio de `transtab` entre jobs (más lento, pero seguro) y se documenta como límite.
2. **Las tablas de página dejan de estar mapeadas en la AS del cliente.** Hoy el bloque de 2 MiB con la L2 de usuario y las L3 de presentación es escribible desde un job (S7GE_HARDWARE.md §3). En la propuesta, las tablas del cliente viven en memoria **que ninguna AS de cliente mapea**, y el bloque de presentación pasa a una AS **del kernel** propia.
3. **Validación de `jc_va`:** el kernel solo acepta una cadena cuya VA caiga **dentro de un BO del propio contexto**, alineada, con tamaño máximo, y recorre la cadena (`next_job` de cada cabecera) comprobando que cada nodo sigue dentro de BO propios y que el número de nodos no excede un tope; una VA fuera del rango del contexto es `S7_E_RANGE` antes de tocar el hardware. La validación **completa** (que los descriptores no apunten fuera) solo es posible cuando los jobs se construyen en el kernel (S7JMQ, fase posterior): hasta entonces, la defensa real es la AS por contexto, no la validación de la cadena.
4. **Presupuesto de memoria:** por contexto, por cliente y global; `S7_E_BUDGET` en vez de agotar RAM cableada (hoy 4096 BO × 256 MiB por cliente).

## 4. Entitlements y descubrimiento
`initWithTask` exige un entitlement (propuesta `com.s7ge.gpu.client`) vía `IOTaskHasEntitlement` o `IOUserClient::clientHasPrivilege`; sin él `kIOReturnNotPrivileged`. Los componentes que lo necesitan hoy: backboardd/hakios-gl, `hero-run`, apps del proyecto. Necesita **auditar el perfil de sandbox de iOS** para `iokit-open` sobre `HeroGPU` *(no verificado)*. Un selector de **versión y capacidades** (`S7_CAPS`) devuelve versión de ABI, número de AS, límites y flags; el cliente decide con eso.

## 5. Forma de las peticiones
Estructuras de tamaño fijo con `{u32 version; u32 size; u32 selector; u32 flags; u64 client_op_id; ...; u32 reserved[N]}`; los reservados deben ser 0 o `S7_E_BADARG`. Se mantienen selectores **escalares** solo para operaciones triviales (`CAPS`, `FREE`); el resto usan `structureInput/Output` con límites de tamaño comprobados (overflow, alineación).

## 6. Selectores propuestos y migración desde el ABI actual
| Nuevo | Hace | Sustituye a (hoy) | Notas |
|---|---|---|---|
| `CAPS` | versión, AS, límites, formatos | `GetParam (0)` | `GetParam` se mantiene un tiempo como envoltorio |
| `CTX_CREATE` / `CTX_DESTROY` | crea/destruye contexto (AS propia) | — (hoy todo en AS0) | nuevo |
| `BO_CREATE` | BO en un contexto, con presupuesto | `CreateBO (1)` | devuelve handle con generación |
| `BO_FREE` | desmapea y libera | `FreeBO (2)` | mismo orden seguro (desmapear antes de liberar) |
| `BO_MAP` | mapa a la tarea | `MapBO (3)` | + `BO_UNMAP` (hoy no existe) |
| `BO_IMPORT_SURFACE` | importa IOSurface **con comprobación de propiedad** | `SurfaceBO (6)` | hoy es global por id: exige derecho sobre la superficie |
| `BO_SYNC` | caché para cualquier BO | `SyncBO (7)` (solo superficies) | amplía |
| `SUBMIT` | job validado, devuelve `op_id` | `Submit (4)` | devuelve estado estructurado |
| `WAIT` | espera una operación (con tiempo límite) | espera dentro de `Submit` | prepara fences |
| `LOG` | traza con límite de frecuencia | `Log (5)` | anti-inundación |
**Coexistencia:** `HeroGPU` (ABI v1) y el nuevo `S7GPU` (ABI v2) son **dos servicios distintos** durante la migración; el v1 queda **solo para software del proyecto** hasta retirarlo. Los consumidores se migran uno a uno (`libherodrm` de `gpu/mesa/herodrm.c` es el principal).

## 7. Errores estructurados
`SUBMIT/WAIT` devuelven `{u32 status; u32 cause; u64 fault_addr; u32 js_status; u32 gpu_fault; u32 resets_since}` con `status` ∈ {OK, `JOB_FAULT`, `MMU_FAULT`, `TIMEOUT`, `RESET`, `POWER`, `BAD_CHAIN`} y `cause` con el detalle (`0x42`, `0x58`…). Un job que dispara un reinicio marca **solo su contexto** como afectado y reinicia el resto limpiamente; tras `N` fallos seguidos de un contexto, se **expulsa** (S7_E_EVICTED).

## 8. Retención ante un timeout ambiguo (macroinforme §13.4)
Tras un timeout el kernel no libera memoria del job hasta confirmar el reinicio de la GPU; el cliente recibe `RESET` y debe recrear su estado.

## 9. Ruta de implementación (cuando la jefatura lo apruebe)
1. Extraer GPU de `herolte_gpu.c` a un módulo (S7_INVENTORY §5) **sin cambiar comportamiento**. 2. Banco de pruebas de host con un doble de `herolte_gpu_*` para handles, presupuestos y validación (nivel A). 3. `CTX_*` y una AS por contexto (necesita el teléfono: L3). 4. Tablas fuera de la AS del cliente. 5. Entitlement. 6. `SUBMIT` con validación de cadena. 7. Migrar `herodrm.c`. 8. Retirar ABI v1.

## 10. Preguntas abiertas para la jefatura
- ¿Cuántas AS reales tiene esta unidad? (leer `AS_PRESENT` en el primer arranque N2/N3; hasta entonces el diseño debe tolerar 1.)
- ¿Entitlement real o regla de sandbox? ¿Qué proceso de Apple abre `HeroGPU` y con qué firma?
- ¿Se acepta que la validación fuerte espere a S7JMQ, aceptando mientras tanto que **la barrera es la AS por contexto**?

# Transferencia entre sesiones y modelos

## Protocolo
**Quien sale** (fin de sesión, corte inminente, cambio de modelo): (1) deja un checkpoint de la tarea en curso; (2) actualiza `STATE.md` y su marca `state-commit` si cambió el panorama; (3) añade **abajo** un relevo nuevo `H-NNNN` (los anteriores no se editan); (4) `render` + `check` + commit local.
**Quien entra:** sigue "Si acabas de incorporarte" de `README.md`, lee el relevo vigente y **verifica** cada afirmación importante contra el repositorio antes de repetirla (`status`, `evidence`, `regress`). Si el estado real contradice el relevo, gana el estado real y se anota la discrepancia en un checkpoint.
Un relevo contiene siempre: repositorio y rama exactos, estado Git, documentos creados o modificados, qué se verificó y cómo, permisos vigentes, riesgos, decisiones pendientes, hilos abiertos con su siguiente paso y la misión recomendada. **No incluye secretos ni datos privados.**
Los informes para el jefe técnico (ChatGPT) usan el mismo formato: se le entregan a través del Director.

---

## Relevo vigente: H-0013 — modelado S7GE Fases 4-6 hecho; hallazgo sobre lo que hace N2 en el hardware (2026-11-14)
- **Hecho (T-0031, solo documentos y una candidata en el PC):** `S7GE_SPLIT_PLAN.md` (mapa medido de `herolte_gpu.c`: GPU 1 960 líneas, el resto ~1 350; audio y Wi-Fi son autocontenidos; los no-GPU solo dependen de `hg_rd/hg_wr/msleep`; la presentación sí está acoplada al display), `S7GE_PATCH_DEPENDENCIES.md` (63 parches tocan `herolte_gpu.c`; candidatos a consolidar; la vía segura es una serie paralela con árbol idéntico, no quitar parches), `S7GE_MESA_INTEGRATION.md`, `S7GE_INCONSISTENCIES.md` (14 puntos), entitlements de la jefatura incorporados al ABI v2 **con su límite**: con `cs_enforcement_disable=1` el entitlement no es una barrera, la barrera es la AS por contexto.
- **Hallazgo importante para el flasheo:** la candidata N2 es de solo lectura para el **almacenamiento**, no para el hardware: por defecto arranca el hilo de **Wi-Fi** (escribe GPIO, reloj, PMU y PCIe), el de bus/display y los de energía y medición. No toca tensión ni frecuencia de CPU (sin `herocpu_mhz`). Variante de menor huella construida y verificada: `xnu-boot-v2-s7-min-20261114.img` (SHA-256 `07ddfa06…5db3`, E-0040, +`herowifi=0 heropower=0 herogpu=0`). **El Director/jefatura elige cuál** (la solicitud en `docs/herolte-solicitud-n2.md` lo explica).
- **Backup del Director (NVMe) sigue en otra terminal:** no tocar adb ni esa carpeta. Recortar la cola de dd al terminar (KI-0008).
- **Pendiente:** autorización roja de flasheo (Director); decisiones de jefatura sobre separar `herolte_gpu.c` y la serie consolidada; ninguna tarea verde abierta.

---

## Relevo anterior: H-0012 — modelado S7GE Fases 0-3 hecho (solo documentos); el backup del S7 corre en otra terminal (2026-11-14)
- **Hecho (T-0030, VERDE, sin tocar parches ni código):** `docs/S7GE_INVENTORY.md` (86 parches tocan los ficheros de GPU, ~40 son el núcleo; **`herolte_gpu.c` (3 465 líneas) también contiene audio, Wi-Fi, relojes de CPU y display**: hay que sacarlos antes de rediseñar S7GPU), `S7GE_EXECUTION_MODEL.md` (secuencia de job por sondeo, AS0 única, recuperación por escalera, causa de los `0x42` sin demostrar), `S7GE_ABI_V2_PROPOSAL.md` (contexto con AS propia, handles con generación, entitlement, errores estructurados, migración), `S7GE_IR_DESIGN.md` (10 categorías de nodo del macroinforme, validador, pruebas de host).
- **Backup del Director en curso (NVMe):** no tocar adb ni esos ficheros. Hallazgo KI-0008: `adb exec-out dd` añade ~98 bytes de texto de dd a cada imagen; recortar después con `tools/herolte-trim-dd-tail.py` (informa por defecto) y comparar con el sha256 calculado EN el teléfono. La evidencia del backup será la siguiente entrada libre de evidence.toml.
- **Pendiente del Director:** autorización roja de `device-write-boot` (texto y procedimiento en `docs/herolte-solicitud-n2.md`), tras completar y comprobar el backup. Sin L3/L4 de esta unidad.
- **Sin tareas verdes abiertas** salvo continuar el modelado (Fases 4-6, esperan a la jefatura).

---

## Relevo anterior: H-0011 — candidata N2 reconstruida con el kernel del CI; esperando la autorización roja (2026-11-14)
- **Hecho:** push de `herolte-drop-v2` al remoto `mio` (D-0030), CI `xnu` run `43579309448` = success, `ci_check` por nombre completo: los 6 parches 0332..0337 APLICADOS, ninguno propio saltado (E-0037). Kernel `62ea7501…2d5b`. Candidata nueva **`xnu-boot-v2-s7-20261114.img`** (SHA-256 `2c155829…8f40`): verificador 47 PASS/0 FAIL, independiente 51 PASS/0 FAIL (E-0038). Copias del teléfono verificadas (E-0036). T-0016 y T-0029 hechas.
- **Falta (Director):** autorizar `device-write-boot`; la solicitud completa, el procedimiento y la vuelta atrás están en `docs/herolte-solicitud-n2.md` (T-0012 sigue bloqueada hasta entonces). **Nada se ha escrito en el teléfono.** Sin L3/L4 de esta unidad.
- **En curso:** T-0028 (mutantes de rev3, segundo plano). **Esperas:** T-0004 (R2), T-0023 (aislamiento de HeroGPU: la GPU no debe usarse con software no confiable).
- **Aviso al próximo ingeniero:** no escribir al teléfono ni leer sus particiones sin la autorización del Director con imagen, hash y copias nombrados.

---

## Relevo anterior: H-0010 — T-0016 hecha; D-0029/D-0030 del Director; push y CI (2026-11-14)
- **Decisiones del Director (firmadas):** D-0029 (el NVMe NTFS vale como zona de trabajo para imágenes grandes; ext4 sigue preferido para repositorios y bucles), D-0030 (push de `herolte-drop-v2` SOLO al remoto `mio` = `darkcloud9998/ios-a5xelte`, lanzar el workflow `xnu` y descargar artefactos; sin push a `origin`, sin PR, sin force), D-0014 (renumeración) aprobada.
- **T-0016 hecha:** `0332-herolte-drop-marker-protocol` → `0336-…`, `0334-herolte-drop-v2` → `0337-…`; fusión local con `origin/herolte` (un conflicto de texto en `HEROLTE_PROGRESS.md`, ambas partes conservadas); la serie 0332..0337 aplica limpia en el orden final (E-0035; aplicabilidad, no compilación). `validate-repo.py`: 4 errores antiguos (KI-0001).
- **Antes de publicar** se escaneó el contenido (sin secretos, sin binarios de Apple, sin IMEI/serie; solo direcciones USB de prueba 192.168.7.x y rutas con el usuario local).
- **Siguiente:** push + CI + `ci_check.py` por nombre completo (`0337-herolte-drop-v2`) → kernel del CI → reconstruir la candidata BOOT con nombre nuevo, reverificar, archivar. T-0028 (mutantes rev3) sigue en curso en segundo plano.
- **Antes de pedir el flasheo al Director** (acción roja): candidata verificada en el PC, BOOT original con hash (E-0009) y copia TWRP de EFS fuera del teléfono (el EFS NO está en este repositorio: lo respalda el Director).

---

## Relevo anterior: H-0009 — el Director delega más autonomía (D-0028); T-0028 en curso (2026-11-14)
- **D-0028 (Director, sus palabras):** el ingeniero y la jefatura técnica son más autónomos; el Director lee todo e interviene de forma extraordinaria. Aplicación: `delete-archived` (nivel A) para borrar temporales YA archivados con hash verificado, por ruta exacta. **Sigue rojo/del Director:** el teléfono, reglas X y `AGENTS.md`, borrado general, publicar/CI en el repositorio público, R2 (D-0005), host-config-change. Las directivas de la jefatura son dirección técnica; una acción C solo la cubre una decisión del Director.
- **Hecho hoy:** T-0025 cerrada (E-0031/E-0032), T-0026 (D-0025), D-0027 ejecutado (E-0033: 6,2 → 29,5 GiB libres; la imagen y `r3/work` siguen en NTFS), T-0019 (E-0034: imagen anterior archivada, sha256 = E-0010).
- **En curso: T-0028** (ronda completa de 49 mutantes sobre rev3, guardia de disco). Ver `resume` de la tarea.
- **Esperas:** T-0004 (R2: D-0005), T-0016/T-0023 (arquitectura). El S7 sigue sin tocarse; sin L3/L4 de esta unidad.
- Contraseña de sudo: el ingeniero no la tiene; los comandos con sudo los ejecuta el Director.

---

## Relevo anterior: H-0008 — T-0025 cerrada; sudo/montaje/compilación pesada/imágenes de prueba son VERDES (D-0025), 2026-11-14
- **T-0025 hecha:** verify real del Director: `ROOT_HFSPLUS_LAB_VALID_CANDIDATE` (`lab-full-xnu.img.valid`), sha256 `747d0245…ec27f` idéntico antes, después y en la copia de NTFS (E-0031; salidas en E-0032). Contiene binarios de Apple: no va a git. **No se ha arrancado en ningún sitio** (nivel L2, sin L3/L4). Faltan los 2 ficheros `U+0E33` (KI-0006); los 195 `NAME-NORMALIZED` son avisos (KI-0007).
- **D-0025 (Director, 2026-11-14):** `privileged-or-mount` y la nueva `heavy-compile` pasan a nivel A; D-0022 y D-0021 quedan sustituidas. **No** cambia: borrar/mover datos, publicar/CI, todo lo del teléfono (siguen rojos), ni **R2** (D-0005: sigue sin autorizar; hay que pedir al Director que lo diga expresamente). El ingeniero **no tiene sudo** (pide contraseña): ejecuta el Director los comandos con sudo, o la sesión debe disponer de él. Las guardas de `img_common.sh`/`guard.py` no se relajan.
- **T-0026 hecha** (como D-0025, no como "tres niveles nuevos": la estructura A/B/C/X ya son los tres colores).
- **Siguiente (verde): T-0028** (ronda completa de 49 mutantes sobre rev3, con guardia de disco). Otras esperas: T-0004 (R2), T-0019 (archivar `lab-full.img.partial` anterior; el nuevo ya está), T-0016/T-0023 (arquitectura).
- Scratchpad volátil: la imagen nueva ya está en NTFS; `r3/work` (renombrado) y los logs también deberían archivarse si se vuelven a necesitar.

---

## Relevo anterior: H-0007 — T-0025 con verify real analizado; T-0027 cerrada; T-0026 en espera (2026-11-14)
- **T-0025:** populate y primer verify REALES hechos por el Director (E-0029). Catálogo en bruto: 327/327 nombres en forma XNU exacta; los 195 `NAME-NORMALIZED` son avisos (Linux recompone al leer, KI-0007); el fallo real eran 2 EXTRA: `.journal` y `.journal_info_block` (omisión mía del punto 5, corregida en `tools/ios-root-lab/verify_image.sh`). **Falta que el Director repita `sudo bash <carpeta-imagenes>/xnu_sudo_run.sh verify`** (montaje de solo lectura); si pasa, la imagen se renombra a `.valid`. Ver `docs/herolte-unicode-imagen.md` §5. Después: archivar la imagen (12 GB, volátil en /tmp) y cerrar T-0025.
- **T-0027 hecha (E-0030):** el hueco R07 era del stub de losetup (el retraso de udev nunca arrancaba), no de `r2_lib.sh`; rev3 lo corrige (rev2 intacto).
- **T-0026 en espera:** la petición del 2026-11-14 (sudo/montaje/imágenes = VERDE, 3 niveles) contradice D-0022 (NARANJA) y quita controles al Director: necesita su confirmación con sus palabras.
- **Siguiente (verde): T-0028** (ronda completa de 49 mutantes sobre rev3, con guardia de disco).
- Otras esperas: T-0004 (R2, sin autorización), T-0019 (archivar lab-full), T-0023/T-0016 (decisiones de arquitectura).

---

## Relevo anterior: H-0006 — T-0025 lista salvo los 2 sudo (2026-11-13)
- **Hecho:** T-0007 (E-0026), T-0005 (E-0027: 46/49 detectados; R07 abierto → T-0027), D-0020 (excluir los 2 `U+0E33`, KI-0006), D-0021 (autorización roja `privileged-or-mount`, un solo uso), D-0022 (nivel NARANJA: **solo registrado; implementarlo es T-0026**), D-0023, D-0024, `tools/ios-root-lab/` (copia con adaptador, 17 pruebas), staging restaurado y renombrado, imagen nueva vacía `lab-full-xnu.img.partial`. Ver `docs/herolte-unicode-imagen.md`.
- **Pendiente de una persona:** ejecutar `COMANDOS_SUDO_XNU.md` (populate y verify). El ingeniero no tiene sudo. Después: leer `ver.full-xnu.*` en `r3/out`, archivar, registrar evidencia y cerrar T-0025.
- **Siguiente (verde):** T-0026 (política NARANJA), T-0027 (R07), `python3 tools/governance.py next`.
- **Cuidado:** el scratchpad de /tmp es volátil: `r3/work`, la imagen nueva y sus logs deben archivarse en NTFS tras la verificación.

---

## Relevo anterior: H-0005 — el Director aprueba el gobierno; Unicode: herramienta lista, imagen pendiente (2026-11-13)
- **Decisiones del Director (sus palabras en `approval_ref`):** D-0001 (gobierno) y D-0017 (Unicode) **APPROVED**; D-0018 levanta la congelación del generador (D-0006 sustituida) solo para esto; **D-0019**: la jefatura técnica (Qwen) decide lo técnico en su nombre. **No** autoriza por sí sola acciones rojas ni toca reglas X: el S7 sigue prohibido hasta una autorización roja explícita.
- **Hecho:** T-0013 (cargador clang, D-0016), T-0003, T-0010 (`S7GE_HARDWARE.md`: tablas de página de AS0 escribibles desde un job, por lectura de código), T-0011 (`S7GE_LICENCIAS.md`), T-0022, T-0024 (`xnu_names_stage.py`; 30 de 32 nombres se arreglan solo renombrando, 2 con U+0E33 necesitan `nodecompose`).
- **En curso:** T-0005 (mutación rev2 ronda 2, en segundo plano en el scratchpad; guardia de disco 3 GiB; salida `t0005_ronda2b_out.txt`). Si el proceso ya no existe, ver `mutation_summary3-*` más reciente y registrar el resultado.
- **Bloqueado a la espera de una autorización roja:** T-0025 (imagen nueva; monta HFS+), T-0004 (R2).
- **Siguiente (verde):** `python3 tools/governance.py next`.

---

## Relevo anterior: H-0004 — T-0008 cerrada (ABI real de `HeroGPU`), 2026-11-13
**Rama `herolte-drop-v2`**, worktree `~/HackiOS/repos/wardevsa-ios-a5xelte-v2`, sin push; árbol principal del responsable intacto.
- **Hecho:** T-0008 → `done`. `docs/S7GE_ABI.md`: los 8 selectores de `HeroGPU`, qué valida el kernel y qué no, y la brecha frente a S7GE. **Hallazgos graves (nivel de código leído, no probados en hardware):** una sola address space **AS0 compartida por todos los clientes**; `Submit` acepta la VA de la cadena de jobs **sin validarla**; `SurfaceBO` busca por id **globalmente**; **ningún entitlement** ni presupuesto de memoria; handles `índice+1` reutilizables. Lo bueno: se desmapea de la GPU antes de liberar; los jobs están serializados; la memoria se pone a cero; no se exponen MMIO ni direcciones físicas.
- **Propuesta (no aplicada):** **D-0015** y la tarea bloqueada **T-0023** (aislamiento de clientes). Antes, T-0010: auditar qué mapea AS0.
- **Evidencia de la herramienta de gobierno:** batería final de mutantes **E-0025** (control sin mutar pasa; 22/22 detectados) sobre las 97 pruebas definitivas.
- **Siguiente (verde):** `python3 tools/governance.py next` → **T-0022** (`ci_check`: nombre completo del parche), después T-0010 y T-0011 (documentos), y T-0005 (ronda 2 de mutación de rev2).
- **Pasar al S7:** ver el informe a la dirección; sigue sin tocarse el teléfono.

---

## Relevo anterior: H-0003 — T-0009 cerrada (integración con `origin/herolte`), 2026-11-13
**De:** ingeniero principal. **Estado:** trabajo en rama **`herolte-drop-v2`** (worktree `~/HackiOS/repos/wardevsa-ios-a5xelte-v2`), sin push; el árbol principal del responsable no se ha tocado (sus 28 ficheros sin confirmar conservan su SHA-256).
- **Hecho:** T-0009 → `done`. Informe `docs/herolte-integracion-origin-herolte.md`; resultados archivados (E-0024). **Conclusión:** los contenidos **no** chocan (un único conflicto de texto en `HEROLTE_PROGRESS.md`, resoluble conservando ambas secciones); los 5 parches de las dos series **aplican en ambos órdenes**; solo colisionan los números `0332` y `0334` (upstream no usa `0335`, de modo que D-0008 —que lo daba por colisión— queda `SUPERSEDED` por **D-0014**).
- **Hallazgo de riesgo silencioso:** `ci_check.py`/`preflight.py` identifican el parche por el prefijo `0334-`, que casa con nuestro DROP v2 **y** con `0334-present-wait-asleep` de upstream: puede dar un falso "aplicado". Nueva tarea **T-0022** (verde): exigir el nombre completo, con pruebas.
- **El repositorio es un clon parcial** (`blob:none`): una fusión local falla por blobs ausentes; el análisis se hizo en un clon temporal con la URL pública de `origin` como remoto *promisor* (solo lectura).
- **Siguiente (verde):** `python3 tools/governance.py next` → **T-0008** (ABI real de `HeroGPU`) y **T-0022** (`ci_check`), ambas sin autorización. Después T-0005 (ronda 2 de mutación de rev2).
- **Decisiones para la jefatura técnica:** D-0014 (renumerar solo 0332→0336 y 0334→0337 y exigir nombre completo en `ci_check`; reemplaza a D-0008), además de D-0001, D-0007, D-0009, D-0011, D-0012, D-0013.
- **Pasar al S7:** ver §"¿Hay que pasar al S7?" del informe a la dirección: las candidatas N1/N2 están verificadas en el PC; falta la decisión del cargador (T-0013) y una **autorización roja** del Director (T-0012). No se ha tocado el teléfono.

---

## Relevo anterior: H-0002 — Auditoría de `tools/governance.py` y mecanismos de continuidad, 2026-11-13
**De:** ingeniero principal (Claude). **Para:** jefe de dirección técnica (revisión independiente) y Director. **Estado:** T-0001 sigue `in_review`; la auditoría está hecha y corregida; **nada consolidado ni publicado**.

### 1. Repositorio, rama y Git
- Worktree del ingeniero `~/HackiOS/repos/wardevsa-ios-a5xelte-v2`, rama **`herolte-drop-v2`**. Commits locales de gobierno: `a7e9138` (implantación) y el commit siguiente (esta auditoría: `git log --oneline -3`). **Sin push.**
- **Árbol principal del responsable** (`…/wardevsa-ios-a5xelte`, `herolte-drop-fixes`, HEAD `8d1cf43`): sus **10 entradas sin confirmar (28 ficheros) tienen exactamente el mismo SHA-256 antes y después** de esta auditoría, y el estado Git es idéntico. No se limpiaron, restauraron, movieron ni sobrescribieron.
- Nota de honestidad: antes de esta misión ya había ejecutado `git status` en ese árbol (lectura); `git status` puede refrescar `.git/index` (hallazgo F-01). No cambia ningún fichero, pero es exactamente el efecto que la herramienta corregida evita.

### 2. Archivos creados o modificados en esta auditoría
- **Reescrito:** `tools/governance.py` (de 369 a ~600 líneas) · `tools/test_governance.py` (de 37 a **96 pruebas**).
- **Nuevos:** `tools/onboarding_drill.py`, `tools/test_onboarding.py` (6 pruebas), `tools/governance_mutation.py` (22 mutantes), `governance/AUDIT_GOVERNANCE_TOOL.md`, `governance/KNOWN_ISSUES.md`, `governance/ONBOARDING_DRILL.md`, `governance/data/policy.pin.toml`.
- **Modificados:** `governance/data/{policy,tasks,decisions,evidence,regression}.toml` (colores, `authorizes`, niveles de evidencia, deuda cuantificada, T-0020/T-0021, D-0011..D-0013, E-0021/E-0022), `README`, `CONSTITUTION` (I-23), `AUTHORITY`, `AUTONOMY_POLICY` (colores verde/amarillo/rojo y qué aplica la herramienta), `STATE`, `HANDOFF` y las vistas generadas.
- **No tocados:** `AGENTS.md` (salvo el puntero ya existente), kernel, parches, generador del root, `validate-repo.py`, imágenes y evidencias.

### 3. Auditoría de la herramienta (resumen; detalle en `AUDIT_GOVERNANCE_TOOL.md`)
17 hallazgos, todos corregidos y cubiertos por pruebas citadas por nombre. Los más graves: `status` podía escribir `.git/index`; `regress` ejecutaba cualquier comando; una acción desconocida contaba como verde (falla abierta); **cualquier decisión del director servía de autorización roja** (D-0002 habría "autorizado" borrar datos); una tarea amarilla podía pasar a `done` sin revisión; `next` ignoraba propietario, bloqueos y decisiones sin aprobar; las evidencias no distinguían estados ni niveles; una estructura de datos equivocada validaba una cola vacía en silencio (defecto encontrado por las propias pruebas).
**Qué aplica ahora:** rojo denegado salvo autorización registrada que **nombre la acción** y esté vigente; amarillo no se integra sin `review_ref`; falla cerrada; `check` y los demás comandos de lectura dejan el clon y `.git` **byte-idénticos**; `render` solo escribe 4 vistas, de forma atómica y sin pisar ficheros ajenos; `evidence` solo da por válido lo que coincide en hash y tamaño; niveles y dominios se **declaran** y nunca se elevan.

### 4. Pruebas ejecutadas y resultados (2026-11-13)
| Qué | Resultado |
|---|---|
| `python3 -W ignore tools/test_governance.py` | **96 OK** (permisos, operaciones prohibidas, integridad de evidencias, generación de vistas, recuperación ante errores, selección de tareas, solo lectura, independencia de rutas, coherencia documental) |
| `python3 -W ignore tools/test_onboarding.py` | **6 OK** (README literal en clon con `HOME` vacío; afirmaciones de STATE/HANDOFF frente al estado real; simulacro de reanudación; simulacro en frío) |
| `python3 tools/governance_mutation.py` | **control sin mutar: pasa; 22 mutantes, 22 detectados, 0 sobreviven** (E-0023; E-0021 es la pasada previa, sin control) |
| `python3 tools/governance.py check` | 0 errores; 2 avisos esperados (política sin ratificar; STATE un commit por detrás) |
| `python3 tools/governance.py evidence --all --strict` | **22 OK, 0 sin verificar**: hashes reales de los 22 ficheros, incluida la imagen de laboratorio de 20 GiB y los TAR |
| `validate-repo.py` | **XFAIL cuantificado: 5 errores, sin corregir** (KI-0001); la suite falla si aumentan |
| Regresión previa | verify-boot 22 · plutil 7 · tune-root 30 · stage-portable 20 · hfsplus-names 16 · DROP v2 36/36 · preflight 14/1/0 |
**Separación de niveles:** todo es host **L2** o compilación **L1**. No hay ninguna evidencia de hardware de esta unidad (L3/L4 `this-unit`); ninguna herramienta puede declararla.

### 5. Limitaciones y riesgos pendientes
1. **Disciplina asistida, no cortafuegos** (KI-0004): la herramienta informa; no impide que un agente ejecute un comando. Alinear los permisos de Claude Code es una acción roja (T-0021, D-0013).
2. La pantalla de `regress` es una red de seguridad, no un sandbox.
3. El pin de la política hace visible un cambio, no lo impide al mismo actor; la ratificación es humana (D-0001).
4. `STATE.md` envejece con cada commit (`check --strict` lo exige al día).
5. La parte 2 de la prueba de incorporación (modelo en frío) **no se ha ejecutado**: la demostración completa del criterio de finalización queda pendiente de T-0020.
6. Siguen abiertos KI-0002 (colisión de numeración con `origin/herolte`), KI-0003 (evidencia volátil: `lab-full` solo en `/tmp`) y KI-0005 (baterías rev2 incompletas).

### 6. Instrucciones exactas para retomar el trabajo
```
cd ~/HackiOS/repos/wardevsa-ios-a5xelte-v2          # worktree del ingeniero (NO el árbol principal)
git branch --show-current                              # herolte-drop-v2
python3 tools/governance.py check                      # 0 errores
python3 tools/governance.py status                     # rama, HEAD, cola, bloqueos
python3 tools/governance.py next                       # siguiente: T-0009 (informe de integración con origin/herolte), verde
python3 tools/governance.py evidence                   # hashes de las evidencias presentes
python3 -W ignore tools/test_governance.py && python3 -W ignore tools/test_onboarding.py
```
Después: marcar T-0009 `in_progress` en `governance/data/tasks.toml`, `python3 tools/governance.py render`, escribir el primer checkpoint y trabajar. Antes de cualquier acción dudosa: `python3 tools/governance.py can <acción>` / `gate <acción> --task T-NNNN`.

### 7. Decisiones que necesitan la revisión de la jefatura técnica
- **D-0001** (el gobierno completo y el cambio en `AGENTS.md`), **D-0011** (mecanismo `authorizes`/`review_ref`), **D-0012** (niveles de evidencia declarados, sin elevación automática) y **D-0013** (alinear los permisos de Claude Code).
- Ya pendientes: D-0007, D-0008, D-0009 y las decisiones del Director de T-0003, T-0013, T-0014.
- Pedir al jefe técnico o al Director que ejecute la parte 2 de `ONBOARDING_DRILL.md` con un modelo en frío (T-0020).

### 8. Siguiente misión recomendada
T-0009 (informe de integración con `origin/herolte`, verde), después T-0008 (ABI de HeroGPU) y T-0005 (ronda 2 de mutación de rev2).

---

## Relevo anterior: H-0001 — Misión 0 (implantación del gobierno), 2026-11-13
**De:** ingeniero principal (Claude). **Para:** jefe de dirección técnica (revisión independiente) y Director (ratificación). **Estado de la misión:** implantada y en revisión (`T-0001 in_review`); **no consolidada**.

### 1. Repositorio y rama
- Repositorio: `wardevsa-ios-a5xelte` (remotos `origin` = upstream `wardevsa/ios-a5xelte`, `mio` = fork del responsable).
- **Worktree del ingeniero:** `~/HackiOS/repos/wardevsa-ios-a5xelte-v2`, rama **`herolte-drop-v2`**. Elegido porque estaba limpio, contiene todo el trabajo reciente y no interfiere con los cambios sin confirmar del responsable.
- Árbol principal del responsable: `~/HackiOS/repos/wardevsa-ios-a5xelte`, rama `herolte-drop-fixes`, **10 ficheros sin confirmar, no tocados**.
- **Sin push.** `origin/herolte` avanzó y colisiona en numeración de parches (D-0008, T-0009): decidir la rama definitiva de gobierno es una de las decisiones pendientes.

### 2. Qué se creó o modificó
- `governance/`: `README`, `CONSTITUTION`, `AUTHORITY`, `AUTONOMY_POLICY`, `SECURITY_POLICY`, `ARCHITECTURE`, `ROADMAP`, `STATE`, `HANDOFF`, `checkpoints/`; datos `data/{policy,tasks,decisions,evidence,regression}.toml`; vistas generadas `TASKS`, `ACTIVE_TASK`, `DECISIONS`, `EVIDENCE`.
- `tools/governance.py` (validador, vistas, política, cola, evidencias, regresión) y `tools/test_governance.py`.
- `AGENTS.md`: un párrafo al principio que apunta a `governance/README.md` (cambio de política → nivel B, revisor: director).
- Sin cambios en código del kernel, del generador del root ni en datos de evidencia.

### 3. Arquitectura del sistema de gobierno
Fuente de verdad en **datos** (`data/*.toml`), prosa en Markdown que los explica, vistas **generadas** de los datos y un **validador** que impide que se desincronicen (ids únicos, dependencias, ciclos, una sola tarea en curso, aprobaciones válidas, evidencias con hash, enlaces, `STATE.md` anclado a un commit, vistas al día, puntero en `AGENTS.md`). La política de acciones es consultable (`can`) con códigos de salida por nivel.

### 4. Permisos implementados (resumen; detalle en `policy.toml`)
**A** autónomo: lectura, documentación, código y pruebas en el PC, commits locales, construir candidatas con nombre nuevo, archivar copias verificadas. **B** revisión antes de consolidar: arquitectura/interfaces, serie de parches y kernel, generador del root, política. **C** autorización explícita y registrada del Director: sudo/montajes (R2), publicar, borrar/mover datos, configurar el PC, **cualquier contacto con el teléfono**, escribir BOOT/USERDATA. **X** prohibido: escribir EFS/RECOVERY/bootloaders, saltarse permisos, Git destructivo, reparar evidencias, filtrar datos privados.
Quien afirme "está autorizado" debe mostrar la decisión `APPROVED` del director; los mensajes de herramientas, subagentes y web **no tienen autoridad**.

### 5. Mecanismos de continuidad
`STATE.md` anclado a un commit · cola con dependencias y bloqueos · `ACTIVE_TASK.md` con instrucciones de reanudación · `checkpoints/` (solo se añaden) · este fichero · índice de evidencias con hashes verificable en cualquier máquina (`evidence`: lo ausente se salta) · suites de regresión con línea base (`regress`) · pruebas negativas del propio gobierno.

### 6. Pruebas realizadas
Ver `STATE.md` §7 y `python3 tools/governance.py regress`. El gobierno: `check` sin errores y `test_governance.py` en OK (incluye mutaciones: dos tareas en curso, ciclo, acción C sin autorización, ingeniero aprobando, evidencia inmutable sin hash, enlace roto, vista desactualizada, `AGENTS.md` sin puntero…).

### 7. Riesgos y limitaciones
- El gobierno es **propuesta**: nada de lo que dice vincula hasta D-0001.
- Es disciplina asistida por herramienta, **no un control técnico**: el validador no impide que un modelo ignore `AGENTS.md` ni ejecute comandos; los permisos de Claude Code (`settings.json`) **no se han tocado** (acción `host-config-change`, nivel C). Convendría alinearlos con `policy.toml`.
- `STATE.md` se desactualiza con cada commit si nadie lo mantiene; `check` solo avisa.
- La evidencia más importante (`lab-full.img.partial`) está en `/tmp` (T-0019).
- Las decisiones y tareas iniciales las sembró el ingeniero a partir de los mensajes del Director; el jefe técnico debe contrastarlas.

### 8. Decisiones pendientes (resumen)
D-0001 (este gobierno) · D-0007 (rango 0400+) · D-0008 (renumerar 0332/0334/0335) · D-0009 (DROP v2 D1-D12) · T-0003 (bloqueo Unicode) · T-0013 (cargador GCC/clang) · T-0014 (línea de arranque 604/607) · qué rama es la definitiva y cuándo publicar (T-0017).

### 9. Siguiente misión recomendada
**T-0009**: plan de integración con `origin/herolte` (informe, nivel A) — es lo que más se encarece con el tiempo y desbloquea T-0016/T-0018 — seguida de **T-0008** (ABI real de `HeroGPU`, brecha de seguridad) y **T-0005** (ronda 2 de mutación de rev2, que precede a cualquier R2). Ninguna requiere autorización.

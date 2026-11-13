# Estado actual de IOS S7

<!-- state-commit: a7e9138 -->
**Verificado el 2026-11-13 sobre el commit `a7e9138`** (primer commit del gobierno; la auditoría de la herramienta y sus correcciones van en el commit siguiente). `python3 tools/governance.py check` avisa si HEAD se ha alejado de este commit. Cuando el panorama cambie, actualiza este fichero **y** la marca de arriba.

## 1. En una frase
Todo el trabajo hecho hasta hoy es **en el PC**: hay una candidata BOOT N2 de solo lectura verificada, un pipeline de root portable a Linux con una verificación fallida por 32 nombres Unicode, herramientas probadas y un estudio de la arquitectura gráfica S7GE. **Nada se ha escrito ni probado en el Galaxy S7** (BOOT original de Samsung, Android intacto).

## 2. Hechos medidos (con evidencia)
| Hecho | Evidencia | Nivel |
|---|---|---|
| Candidata N2 de solo lectura: 47 PASS (constructor) y 50 PASS (verificador independiente), 0 FAIL; `ufsrw=0 herolog=0 herodrop=0`; imagen SHA-256 `26a39560…1d29` (18 618 384 B, 44 % de la partición); payload reproducible byte a byte desde kernel + ADT + línea; construcción determinista | E-0001..E-0006 | L2 |
| Kernel DROP v2 (SHA-256 `e678b454…`): preflight 14 correctas, 1 aviso (sin GCC aarch64), 0 fallos | E-0006, E-0007 | L1/L2 |
| Las 5 candidatas anteriores fallan el perfil N2 (3-4 FAIL): no llevaban `ufsrw=0` o llevaban `ufsrw=1 rootrw=1` | E-0019 | L2 |
| `lab-full.img.partial` (SHA-256 `e724f981…c79496`, 20 GiB aparentes) está poblada pero su verificación es `ROOT_HFSPLUS_LAB_FAILED`: **32 de 329 nombres no ASCII** difieren entre la tabla de descomposición del `hfsplus` de Linux y la de XNU (144 caracteres del BMP difieren en total); `fsck_hfs -n` solo señala esos 32 | E-0010, E-0017, `docs/herolte-unicode-hfsplus.md` | L2 |
| Las 7 tablas CoreFoundation de XNU (compiladas desde su fuente) están byte a byte en el kernel desplegado | E-0017 | L2 |
| El árbol ya contiene un driver de GPU T880 y un cliente de usuario (parches 0225-0267, 0307), Mesa Panfrost en OSMesa y un puente EAGL; **no hay proveedor de Metal** | `docs/S7GE_STATUS.md` | L1 |
| DROP v2: 36/36 comprobaciones del núcleo (81 510 casos de doble fallo), `test_host_pack` y sintaxis del núcleo correctos | `regression.toml` | L2 |
| **`tools/governance.py` auditada línea a línea**: 17 hallazgos corregidos, 96 pruebas propias en OK, 6 de incorporación en OK y una batería de 22 mutantes con control sin mutar: 22 detectados y 0 supervivientes; los comandos de validación dejan el árbol y `.git` byte-idénticos | `AUDIT_GOVERNANCE_TOOL.md`, E-0021..E-0023 | L2 |
| Los 10 elementos sin confirmar del árbol principal (28 ficheros) tienen el mismo SHA-256 antes y después de la auditoría; su HEAD (`8d1cf43`) no cambió | comprobado al cerrar la misión | L2 |

## 3. Hipótesis (no demostradas)
- Que la candidata N2 **arranque** en el S7: solo hay comprobaciones de consistencia del PC.
- Que corregir los 32 nombres deje `fsck_hfs` en rc=0 (R2 lo mediría); que XNU no abra esos ficheros por nombre (ruta de código leída, no ejecutada).
- Que la evidencia de GPU y pantalla de `HEROLTE_PROGRESS.md` (otro teléfono) se reproduzca en esta unidad.
- Que las decisiones D1-D12 de DROP v2 sean las correctas (sin ratificar, D-0009).

## 4. Git
| Árbol | Rama | HEAD | Sin confirmar |
|---|---|---|---|
| `~/HackiOS/repos/wardevsa-ios-a5xelte-v2` (**worktree del ingeniero**) | `herolte-drop-v2` | `bdf7c53` al verificar | 0 |
| `~/HackiOS/repos/wardevsa-ios-a5xelte` (árbol principal **del responsable**) | `herolte-drop-fixes` | `8d1cf43` | 10 (2 modificados, 8 sin versionar): **no tocar** |
Remotos: `origin` = `wardevsa/ios-a5xelte` (upstream), `mio` = fork del responsable. `origin/herolte` (2026-11-13, `f19b73d`) lleva 13 commits que esta rama no tiene (incluye `0332`-`0334` de gráficos que **colisionan** con nuestros `0332`, `0334`, `0335`: D-0008, T-0009). Esta rama lleva 34 commits propios no publicados (**sin push**).

## 5. Bloqueos abiertos (qué los desbloquea)
| Bloqueo | Quién | Tarea |
|---|---|---|
| Elegir la corrección del bloqueo Unicode (1-5 / B / C) | Director | T-0003 |
| Autorizar R2 (sudo, montar imágenes) con comandos acotados; antes, ronda 2 de mutación y revisión independiente de rev2 | Director + ingeniero | T-0004, T-0005, T-0006 |
| Cargador de clang o GCC; qué argumento quitar de la línea diaria (604/607) | Director | T-0013, T-0014 |
| Autorizar escribir BOOT en el S7 (N1/N2) | Director | T-0012 |
| Autorizar retirar 24 GiB de sandboxes originales (copia verificada) | Director | T-0007 |
| Confirmar el archivo en NTFS de `lab-full.img.partial` y `os.apfs` | Director | T-0019 |
| Ratificar D-0001 (este gobierno), D-0011, D-0012, D-0013, D-0007 (rango 0400+), D-0008 (renumerar), D-0009 (DROP v2) | Jefe técnico / Director | T-0001, T-0016, T-0021 |
| Alinear los permisos de Claude Code con `policy.toml` (convierte la disciplina asistida en control técnico) | Director | T-0021 |
| Ejecutar la parte 2 de la prueba de incorporación con un modelo en frío | Jefe técnico / Director | T-0020 |

## 6. Riesgos
1. **Evidencia volátil:** `lab-full.img.partial` y el scratchpad viven en `/tmp` (se pierden al reiniciar). Copias de seguridad: E-0011..E-0017; la imagen de laboratorio **no está archivada** (T-0019).
2. **Divergencia con upstream** que crece cada día (colisión de números de parche).
3. **Brecha de seguridad de la GPU:** `Submit [jc_va, js]` acepta del cliente la dirección de la cadena de jobs (no se encontró validación en los parches 0239/0248; T-0008).
4. **Disco:** `/` en 88 % (15 GB libres); ya llegó a 0 una vez.
5. **Solo hay un teléfono y un camino de vuelta:** BOOT original copiado (E-0009); el EFS (IMEI) está respaldado fuera del teléfono (`~/HackiOS/backups/device-herolte/2026-11-12/`).

## 7. Verificación de esta línea base (2026-11-13)
`python3 tools/governance.py regress` (suites y líneas base en `data/regression.toml`): governance-tests **96 OK** · governance-onboarding **6 OK** · governance-mutation **22/22 detectados** (E-0021) · verify-boot 22 OK · plutil-lite 7 OK · tune-root 30 PASS · stage-portable 20 PASS · hfsplus-names 16 OK · drop-v2-core 36/36 (1 min 56 s) · drop-v2-host-pack OK · drop-v2-kernel-syntax OK · preflight-kit 14/1/0 · validate-repo **XFAIL cuantificado: 5 errores `Gap in patch sequence`** (KI-0001, T-0018; se vigila que no aumente).
**Evidencias** (`python3 tools/governance.py evidence --all --strict`): **22 OK, 0 sin verificar** (hash y tamaño reales, incluida la imagen de laboratorio de 20 GiB). **Nivel:** todo lo anterior es **host L2** o compilación **L1**; no hay ninguna evidencia L3/L4 de esta unidad.

## 8. Dónde mirar
`KNOWN_ISSUES.md` (deuda sin ocultar) · `AUDIT_GOVERNANCE_TOOL.md` · `ONBOARDING_DRILL.md` · `TASKS.md` · `ACTIVE_TASK.md` · `DECISIONS.md` · `EVIDENCE.md` · `ROADMAP.md` · `ARCHITECTURE.md` · `docs/herolte-preparacion-pruebas.md` · `docs/herolte-unicode-hfsplus.md` · `docs/S7GE_STATUS.md` · `HANDOFF.md`.

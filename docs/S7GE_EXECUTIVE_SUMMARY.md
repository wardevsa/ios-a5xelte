# S7GE_EXECUTIVE_SUMMARY — estado del modelado y del camino al primer arranque (Fase 13, 2026-11-14)

**Resumen de 2-3 páginas para la dirección.** Todo lo de abajo es **análisis de código y comprobaciones del PC (L1-L2)**; **no hay ninguna prueba en el teléfono de esta unidad (L3/L4)**. Detalle en los documentos citados.

## 1. Dónde estamos
- **Candidata de primer arranque lista y verificada en el PC:** `xnu-boot-v2-s7-min-20261114.img` (SHA-256 `07ddfa069c7f53936964e05f174ddced6a75b6ff690180e648a082c941115db3`; E-0040): kernel compilado por el CI con los parches 0332-0337 renumerados y fusionados con upstream (E-0035, E-0037), línea de arranque de **almacenamiento de solo lectura y sin Wi-Fi, energía ni GPU**; 47 PASS (constructor) y 54 PASS (independiente), 0 FAIL. La candidata normal (`2c155829…8f40`, E-0038) queda para una fase posterior. **Nada se ha escrito en el teléfono.**
- **Imagen de raíz de laboratorio** con nombres Unicode en forma XNU: `lab-full-xnu` verificada por `verify_image.sh` (ROOT_HFSPLUS_LAB_VALID_CANDIDATE; E-0031, E-0032); faltan 2 ficheros tailandeses excluidos (KI-0006).
- **Copias de seguridad** del teléfono verificadas (E-0036); **backup completo del Director en curso** (KI-0008: recortar la cola de `dd`).
- **Gobierno:** D-0001 aprobada; decisiones del Director D-0017…D-0030; jefatura técnica con delegación (D-0019); `check` sin errores; pruebas de herramientas y de DROP en verde.

## 2. Qué dice el modelado S7GE (Fases 0-12)
| Tema | Hallazgo | Documento |
|---|---|---|
| Alcance real | 86-108 parches tocan los ficheros de GPU; ~40 son el núcleo; **63 modifican `herolte_gpu.c`** en cadena | INVENTORY, PATCH_DEPENDENCIES |
| `herolte_gpu.c` (3 466 líneas) | **GPU solo 57 %**; el resto es audio, Wi-Fi, relojes de CPU, energía y display. Viola el principio 2.4; audio y Wi-Fi se extraen barato | SPLIT_PLAN, EXTRACTION_INTERFACES |
| **Seguridad** | **Una sola AS0** compartida; el cliente aporta la cadena de jobs; **el bloque de 2 MiB con la L2 de usuario y las L3 es escribible desde un job** (por lectura de código) → un cliente podría alcanzar memoria física arbitraria | S7GE_ABI, HARDWARE |
| ABI nueva (propuesta) | contexto con AS propia, handles con generación, entitlement (decisión de jefatura, **no es barrera mientras `cs_enforcement_disable=1`**), presupuesto, errores estructurados | ABI_V2_PROPOSAL |
| Estabilidad | fallos de lectura `0x42` con >1 GiB de RAM y frecuencias altas, **sin causa raíz demostrada** | EXECUTION_MODEL |
| GL actual | OSMesa+Panfrost sobre `HeroGPU` funciona (en el upstream); **dos puentes EAGL**; propuesta: hakios-gl | MESA_INTEGRATION, EAGL_BRIDGES |
| **Mesa** | el parcheador aplica a **25.0.7 (12/12)**; **OSMesa desapareció en Mesa 25.1**: la ruta GL está atada a una serie sin mantenimiento | MESA_VERSION_ANALYSIS |
| Licencias | Mesa y libdrm: MIT (con detalles menores); `metal2vulkan` desconocida; el código propio sin licencia declarada | LICENCIAS |
| Lecciones de A5XELTE | método por puertas; **el A5 se negó a exponer descriptores crudos, herolte los expone** | A5XELTE_LESSONS |
| Documentación | 17 inconsistencias entre documentos señaladas | INCONSISTENCIES |

## 3. Decisiones tomadas (resumen)
Cargador clang (D-0016); Unicode: nombres en forma XNU y excluir 2 ficheros (D-0017, D-0020); push/CI al fork (D-0030); renumeración de parches (D-0014); NVMe como zona de trabajo (D-0029); borrado de temporales archivados es verde (D-0028); `sudo`/montaje/compilación pesada/imágenes de prueba son verdes (D-0025); jefatura: **primer flasheo con la variante mínima**, entitlements, orden de extracción (audio, Wi-Fi, CPU, display).

## 4. Decisiones pendientes
| Quién | Decisión |
|---|---|
| **Director** | **Autorización roja de la fase 1** (texto en `herolte-solicitud-n2.md` §7), tras completar y comprobar el backup; segunda copia de `EFS.img` fuera de `/dev/sda2` |
| Director | R2 (D-0005), borrado general y publicación en `origin` (siguen en tus manos) |
| Jefatura | consolidar la serie antes o después del primer arranque (recomendado: **después**); separar `herolte_gpu.c`; **qué hacer con OSMesa** (quedarse en 25.0.7 / mantenerlo / otra superficie); qué puente EAGL conservar; ¿se acepta que la defensa real sea la AS por contexto? |
| Director/jefatura | licencia del código propio (hay `LICENSE` ausente en la raíz) |

## 5. Plan tras el flasheo
1. **Fase 1:** escribir la variante mínima, observar (`S7GE_MIN_BOOT_VALIDATION.md`, `S7GE_BOOT_LOG_EXPECTATIONS.md`), **restaurar BOOT** al terminar cada intento mientras no haya raíz (`S7GE_ROLLBACK_PLAN.md`), comprobar EFS.
2. **Según el resultado (A-E):** A → fase 3 (candidata normal, nueva autorización); B/C/D/E → analizar la última línea y decidir.
3. **Después:** activar subsistemas uno a uno (Wi-Fi, energía, GPU: `AS_PRESENT` y `GPU_ID` de esta unidad), una imagen y una autorización por intento.
4. **En paralelo en el PC:** ABI de GPU v2 (banco de pruebas de host con dobles), separación de `herolte_gpu.c`, validador S7GIR (nivel A tras la aprobación).

## 6. Riesgos principales (honestos)
- **Primer arranque en hardware nuevo:** pantalla negra o reinicios son posibles; mitigado con copias verificadas y la restauración de BOOT. **Riesgo residual:** si TWRP no responde, **no hay camino de restauración documentado** por otro canal (Download/Odin) y no he comprobado si hay firmware oficial en el PC.
- **Punto único de fallo de las copias:** todo en `/dev/sda2`; `EFS` contiene el IMEI.
- **Seguridad del aislamiento de GPU:** hoy un cliente de GPU es de confianza total del kernel; mientras no se corrija (D-0015/T-0023), **no usar la GPU con software no confiable**.
- **Dependencia de Mesa 25.0.x** y de OSMesa (sin mantenimiento).
- **Evidencia:** todo lo anterior es L1-L2; no se debe afirmar que "iOS arranque" ni que "la GPU funcione" en esta unidad.

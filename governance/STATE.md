# Estado actual de IOS S7

<!-- state-commit: 32793e5 -->
**Verificado el 2026-11-15 sobre el commit `32793e5`** (el estado se refresca en cada relevo; `check` avisa de la distancia).

## 1. En una frase
**El kernel XNU de iOS 16.7.16 arranca en el Galaxy S7 hasta `bsd_init` y falla al montar la raíz (resultado A de N2, E-0177, 2026-11-15)**: se ven en pantalla 64 fases de `kernel_bootstrap`, los drivers propios (APM, táctil, UFS) y `cannot mount root`; la GPU, el Wi-Fi y la energía siguen apagados a propósito. iOS **no** está instalado: USERDATA sigue siendo Android ext4; el plan (`docs/S7GE_IOS_ROOT_PLAN.md`, vía B local) usa la imagen HFSX de laboratorio de 20 GiB ya verificada, un *tuning* con `sudo` y la escritura de USERDATA, que **borra Android** y exige autorización roja con hash. Hay copias verificadas de SYSTEM, USERDATA y RECOVERY (E-0123…E-0125). **Corrección:** la "pantalla de reinicio" de min2-min13 no era un reinicio (ver `S7GE_N2_REACHED.md`).

## 2. Hechos medidos (con evidencia)
| Hecho | Evidencia | Nivel |
|---|---|---|
| **Escrituras en BOOT (solo BOOT; EFS idéntico antes y después en cada sesión):** min1 (D-0033), min2 (D-0034), min3 (D-0035), min4 (D-0036), min5 (D-0037), min6 (D-0039), min7h08 (D-0041); cada una leída de vuelta con su hash | E-0043, E-0046, E-0049, E-0051, E-0053, E-0056, E-0060 | L2 |
| min1: panic en `kmem_range_init` (ADT de 2 GiB sin `vm_compression_limit`); min2-min6: pantalla final "azul, cian, magenta + XNU MMU ON" tras un reinicio; min5: vistos 7 bloques de la columna derecha (hasta 6a) y texto de etapas 1-3; min6: nada visible entre el cargador y la pantalla final | E-0044, E-0057 y `docs/S7GE_MIN2..MIN6_*` (observaciones a ojo del Director) | L2 |
| Parches de diagnóstico 0338-0342 (bloques de color, `herostop=N`, contador en `0x8ffff108`); kernel `4e5f25a5…4d6f` (CI 43603366417) | E-0058 | L1/L2 |
| TWRP **no** tiene `/dev/mem` (`# CONFIG_DEVMEM is not set`); `last_kmsg` no contiene rastro de XNU; la línea de arranque de TWRP trae `sec_debug.reset_reason=5` (sin interpretar) | E-0054, E-0060 | L2 |
| Imágenes de la bisección preparadas: min7 (sin herostop), h02, h04, h06, h12, h16, h19 (verificadas, NO escritas) | E-0058, E-0061..E-0066 | L2 |
| **Candidata de primer arranque** `xnu-boot-v2-s7-min-20261114.img` (SHA-256 `07ddfa06…5db3`): kernel compilado por el CI (run `43579309448`) con los parches 0332-0337; línea de solo lectura **y sin Wi-Fi, energía ni GPU** (`herowifi=0 heropower=0 herogpu=0`); 47 PASS (constructor) y 54 PASS (independiente), 0 FAIL | E-0037, E-0040 | L1/L2 |
| Candidata normal `xnu-boot-v2-s7-20261114.img` (SHA-256 `2c155829…8f40`): la misma sin los tres `=0` de hardware; 47/51 PASS. Reserva para una fase 3 con autorización propia | E-0038 | L2 |
| La candidata anterior de solo lectura (`26a39560…1d29`, kernel sin los parches de upstream) se conserva: 47/50 PASS | E-0001..E-0006 | L2 |
| La serie renumerada 0332..0337 (0332 marcador→0336, 0334 DROP v2→0337) aplica limpia en orden final; fusión con `origin/herolte` con 1 conflicto de texto; CI success y los 6 parches constan aplicados | E-0035, E-0037 | L1 |
| **Imagen de raíz `lab-full-xnu`** (HFS+ con nombres XNU; 327/327 nombres no ASCII exactos en el catálogo en bruto; 2 ficheros `U+0E33` excluidos): `ROOT_HFSPLUS_LAB_VALID_CANDIDATE`, SHA-256 `747d0245…ec27f` idéntico antes, después y en la copia de NTFS | E-0031, E-0032 | L2 |
| Copias del teléfono (BOOT = E-0009, EFS, CPEFS, PERSISTENT, PARAM, PERSDATA, RECOVERY, BOTA0/1) verificadas con su `SHA256SUMS`; en el PC, permisos 600, fuera de git, **todas en el mismo disco** | E-0036 | L2 |
| **Snapshot de backup del Director (2026-11-14, NVMe) NO completo:** BOOT bueno (prefijo = E-0009), EFS bueno (8 bytes de superbloque distintos), **RECOVERY truncada (16 %)**, SYSTEM sin verificar, **USERDATA 0 B**; copia en tarjeta SD declarada sin hash. La fase 1 está cubierta por las copias de 11-12 | E-0042, `docs/S7GE_BACKUP_STATUS.md` | L2 |
| El hilo de Wi-Fi arranca **por defecto** y escribe GPIO, reloj, PMU y PCIe; N2 es de solo lectura para el **almacenamiento**, no para el hardware | `docs/S7GE_SPLIT_PLAN.md` §3 | L1 |
| `herolte_gpu.c` (3 466 líneas) es 57 % GPU; el resto audio, Wi-Fi, relojes de CPU, energía, display | `docs/S7GE_INVENTORY.md`, `S7GE_SPLIT_PLAN.md` | L1 |
| **Seguridad GPU:** AS0 única; `Submit` acepta la cadena del cliente sin validar; el bloque de 2 MiB con la L2 de usuario y las L3 es escribible desde un job (lectura de código) | `docs/S7GE_ABI.md`, `S7GE_HARDWARE.md` | L1 |
| **Mesa:** el parcheador aplica a 25.0.7 (12/12); **OSMesa se eliminó en Mesa 25.1**; Mesa y libdrm son MIT en lo enlazado | `docs/S7GE_MESA_VERSION_ANALYSIS.md` | L1 |
| **OSMesa propio (B2, D-0032):** `gpu/mesa/osmesa-frontend/` reinyecta el frontend de Mesa 25.0.7 en Mesa 26.2.4; **compila en Linux (913/913) y una prueba mínima da el píxel correcto**; falta el gancho `mmap` de Panfrost (2 de 12 ediciones), Panfrost y Darwin | E-0041, `docs/S7GE_OSMESA_MESA26_COMPATIBILITY.md` | L1 |
| Rondas de mutación de rev2/rev3: 47 de 49 detectados, M16 y N02 equivalentes conocidos | E-0039 | L2 |
| `tools/governance.py`: auditada, 98 pruebas propias y 6 de incorporación en OK; batería de 22 mutantes con control (E-0025, **sobre una versión anterior**: `next` cambió, ver T-0035) | E-0025 | L2 |
| Herramienta de escritura de BOOT con salvaguardas, 13 pruebas con adb **falso**; clasificador de transcripciones, 9 pruebas | `tools/herolte-flash-boot.sh`, `herolte-boot-transcript-check.py` | L2 |

## 3. Hipótesis (no demostradas)
- Que la candidata **arranque** en esta unidad (solo comprobaciones de consistencia del PC).
- Que los valores de tensión/frecuencia y los hilos probados en el teléfono del upstream sirvan para este silicio.
- Que el procedimiento de restauración funcione en el TWRP real (documentado, no ensayado).
- Que el `hfsplus` real no altere más nombres de los medidos (el catálogo en bruto dice que no).
- Que la GPU de esta unidad tenga el mismo `GPU_ID` y número de address spaces que la del upstream (no leído nunca).

## 4. Git
| Árbol | Rama | HEAD | Sin confirmar |
|---|---|---|---|
| `~/HackiOS/repos/wardevsa-ios-a5xelte-v2` (**worktree del ingeniero**) | `herolte-drop-v2` | `120f183` al verificar | los cambios del relevo en curso |
| `~/HackiOS/repos/wardevsa-ios-a5xelte` (árbol principal **del responsable**) | `herolte-drop-fixes` | `8d1cf43` | 10 (2 modificados, 8 sin versionar): **no tocar** |
Remotos: `origin` = `wardevsa/ios-a5xelte` (upstream, **sin push**), `mio` = `darkcloud9998/ios-a5xelte` (fork del responsable; D-0030 autoriza publicar solo `herolte-drop-v2` ahí). La rama **ya está publicada en `mio`** hasta el commit `d4c9d88`; los commits posteriores son locales.

## 5. Bloqueos abiertos (qué los desbloquea)
| Bloqueo | Quién | Tarea |
|---|---|---|
| **Localizar la fase del reinicio** (bisección con `herostop`, tanda D-0041, 7 escrituras restantes; el Director reinicia y observa) | Director + Ingeniero | T-0012 |
| R2 sigue sin autorizar (D-0005): el Director debe decir expresamente que puede ejecutarse | Director | T-0004, T-0006 |
| Ratificar D-0007 (rango 0400+), D-0009 (DROP v2), D-0011, D-0012, D-0013 (permisos de Claude Code), D-0015 (aislamiento de clientes de HeroGPU) | Jefatura técnica / Director | T-0014, T-0018, T-0021, T-0023 |
| Portar el gancho `mmap` de Panfrost y compilar con Panfrost/iOS (B2 ya elegida y autorizada): falta `libdrm-dev` o el CI (D-0032) | Ingeniero + Director (instalar herramientas / publicar) | T-0037 |
| Consolidar la serie de parches y separar `herolte_gpu.c` (recomendado: después del primer arranque) | Jefatura | T-0015, T-0017 |
| Ejecutar la parte 2 de la prueba de incorporación con un modelo en frío | Jefatura / Director | T-0020 |

## 6. Riesgos
1. **Primer arranque en hardware nuevo:** pantalla negra o reinicios posibles; vuelta atrás con `BOOT.img` verificado; **si TWRP no responde no hay camino documentado por Download/Odin** (riesgo residual).
2. **Punto único de fallo de las copias** (un solo disco; `EFS` contiene el IMEI).
3. **Brecha de seguridad de la GPU:** hasta aplicar D-0015/T-0023, no usar la GPU con software no confiable. **Con `cs_enforcement_disable=1` los entitlements no son una barrera.**
4. **Dependencia de Mesa 25.0.x** (sin OSMesa en versiones nuevas).
5. **Volatilidad:** el scratchpad vive en `/tmp`; lo importante está archivado en NTFS (E-0011…E-0040 con copia); ahora sin `r3/work` ni la imagen original (restaurables).
6. **Disco:** `/` con ~21 GB libres.

## 7. Verificación de esta línea base (2026-11-14)
Pruebas ejecutadas hoy: `tools/test_governance.py` 98 OK · `test_onboarding.py` 6 OK · `ios-root-lab/test_adapter.py` 18 OK · `test_flash_boot.py` 13 OK · `test_boot_transcript.py` 9 OK · `test_trim_dd_tail.py` 6 OK · `xnu/drop-v2/test/test_ci_check.py` 9 OK · `hfsplus-names` 16 OK + 9 OK. `python3 tools/governance.py regress` **no** se ha vuelto a ejecutar entero desde 2026-11-13 y `regression.toml` **no incluye** las suites nuevas (T-0035). **Nivel:** todo es **host L2** o compilación **L1**; no hay ninguna evidencia L3/L4 de esta unidad.

## 8. Dónde mirar
`HANDOFF.md` (empezar aquí) · `KNOWN_ISSUES.md` · `TASKS.md` · `DECISIONS.md` · `EVIDENCE.md` · `docs/herolte-solicitud-n2.md` (la solicitud al Director) · `docs/S7GE_EXECUTIVE_SUMMARY.md` · `docs/S7GE_PREFLIGHT_CHECKLIST.md` · `docs/S7GE_ROLLBACK_PLAN.md` · `docs/S7GE_MIN_BOOT_VALIDATION.md`.

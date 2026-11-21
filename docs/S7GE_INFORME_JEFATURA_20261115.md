# Informe a la Jefatura Técnica — del 14 al 15 de noviembre de 2026 (Ingeniero Principal)

Estado al cierre de la sesión: **el kernel XNU de iOS 16.7.16 arranca en el Galaxy S7 (herolte) hasta `bsd_init` y falla al montar la raíz, que es el resultado esperado de N2** (`S7GE_MIN_BOOT_VALIDATION.md`, criterio A). Detalle: `docs/S7GE_N2_REACHED.md`, E-0177.

## 1. Qué ha pasado desde el último informe (resumen por hitos)
| Fecha/hora | Hito | Evidencia |
|---|---|---|
| 14-nov | min1 (variante mínima): pánico en `kmem_range_init` (sin `vm_compression_limit`) | E-0044 |
| 14-nov | min2-min4: pantalla "azul/cian/magenta + XNU MMU ON"; sin información | E-0046… |
| 14-nov | min5: primer texto y bloques de **C**: llega a `arm_init` | E-0053 |
| 14-nov | Método nuevo: parada `herostop=N` + bloques/nombres de fase en pantalla; bisección min7-min13 | E-0059…E-0148 |
| 14-nov | Pila de arranque superada: `arm_vm_init`, TTBR0 off, `pmap_bootstrap`, `serial_init`, `kmem_init`/`kmem_range_init`, `kernel_bootstrap` (64 fases) | E-0133…E-0169 |
| 15-nov | min16: anillo de mensajes de `kprintf`/`printf`: APM, TOUCH, UFS, HFS `cannot mount root`, Skywalk PASSED, `bsd_autoconf` | E-0177 |
| 14-nov | Copias de seguridad de SYSTEM (7,75 GB), USERDATA (23,4 GB) y RECOVERY, verificadas contra el hash de la partición entera en el teléfono | E-0123…E-0125 |

## 2. Correcciones de método y de hechos (para que el análisis de la jefatura no repita errores)
- **Los "reinicios" de min2-min13 no eran reinicios.** La pantalla "XNU MMU ON + 3 bloques" son marcas que dibuja `start.s` al principio; el kernel seguía vivo pero **nada visible dibujaba**. Lo leímos mal durante horas (incluida yo). No hay ninguna evidencia de reinicio real. Corregido en `S7GE_N2_REACHED.md`.
- Los argumentos de arranque **no** afectan al ensamblador de `start.s` (se leen en C). `herowifi/heropower/herogpu=0` ya estaban en min1; el cambio de min1 a min2 fue solo `vm_compression_limit=98304 vm_compressor=2` (E-0045). La tabla de diferencias de la directiva de la jefatura (min1 "con valores por defecto") era incorrecta.
- El kernel traduce con **4 KiB** (TCR `TG0=0`, `TG1=2`, `T0SZ=T1SZ=25`): el bloque L2 mide 2 MiB, no 32 MiB (el donante usa 16 KiB). Mi parche 0343 lo ignoró y por eso falló su alias de framebuffer (corregido 0347).
- El texto "RS XNU STAGE" era `A5 XNU STAGE`; las etiquetas `arm_limit`/`cpu_limit` no existen (`arm_init entered`, `cpu_init done`).
- Fallos míos, ya corregidos: una revisión de kernel registrada antes de que el CI terminase (revertida); una verificación independiente que falló por la sintaxis de `--expect-arg -v` y no abortó (revertida); `adb exec-out` a 0,9 MB/s (cambié a `nc` por `adb forward`, ~18 MB/s).

## 3. Gobierno: qué se autorizó y cómo (para revisión)
| Decisión | Qué | Cómo se acotó |
|---|---|---|
| D-0033…D-0037, D-0039 | escrituras de BOOT una a una (min1…min6) con imagen y hash | autorización roja con hash por imagen |
| D-0038, D-0040 | lectura de RAM desde TWRP | TWRP no tiene `/dev/mem`; solo `last_kmsg` e `iomem` |
| D-0041, D-0042 | tandas de imágenes que difieren solo en `herostop=N` | kernel fijado por hash |
| **D-0043** | **autorización amplia de diagnóstico** (20 escrituras, hasta 2026-11-17) | lista blanca de ficheros verificada por `tools/herolte-diag-patch-check.py` + revisión del contenido registrada por kernel; `0332-0337` intactos |
| D-0044 | copia de seguridad de SYSTEM/USERDATA/RECOVERY | solo lectura, verificada por trozos |
| D-0045, D-0047 | ampliación de la lista: ficheros de enganche con **solo llamadas `sweet_early_*`** (comprobado por herramienta) | regla de contenido por línea |
| D-0046 | argumento `-v` | una imagen, con hash |
**Pregunta para la jefatura:** el patrón D-0043 (límites verificables por herramienta en vez de firma por kernel) ha funcionado y ahorró unas 12 firmas; ¿se ratifica como procedimiento permanente para diagnóstico de arranque, con tope de escrituras y caducidad? Sus límites: nunca otro ADT/cargador/argumento sin decisión, nunca otra partición.

## 4. Siguiente fase: raíz iOS (decisión delegada por el Director: vía B, local)
`docs/S7GE_IOS_ROOT_PLAN.md`. Ya hay: IPSW verificado, imagen HFSX de laboratorio de 20 GiB (verificada, E-0178), copias de seguridad, escritor de USERDATA rápido y verificado (`tools/herolte-write-userdata.py`, 7 pruebas con adb falso). Falta: F1 (sudo: montar, *tuning* real, fsck, hash final) y la **autorización roja de escribir USERDATA** (borra Android), con la imagen y su hash. Primer arranque con raíz: BOOT `min16` tal cual (UFS en solo lectura).
Riesgo principal: `launchd`/firmas (cs_enforcement, cachés) y el `hfsplus` de XNU frente a una imagen hecha en Linux.

## 5. Qué pido a la jefatura
1. Revisar el plan de la raíz (§4) y **objetar** cualquier paso antes de escribir USERDATA.
2. Ratificar o corregir el patrón D-0043 (§3).
3. Mantener el método observacional: transcribir **literal**, con la posición (columna y orden); no inferir fases de fallo sin el código.
4. Aceptar que las interpretaciones de ChatGPT sobre fotos son transcripciones de nombres y colores, no evidencia de significado (su "hito" o "fase sustancial" no lo es).

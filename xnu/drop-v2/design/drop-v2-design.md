# DROP v2: diseño propuesto (borrador para congelar)

Estado: propuesta. Validada solo contra el modelo `drop_v2_model.py` (misma carpeta). No hay código en el repo.
Aviso: el parche 0333 (sin commitear) tiene un underflow en `hdrop_at` (ver informe de verificación): no compilarlo ni flashearlo.

## 1. Garantías que el diseño usa (informe de persistencia)
- Metadatos HFS (create/rename/unlink/mkdir): atómicos por operación; se persisten en orden de journal (B).
- Datos de fichero: NO van por el journal. Solo son duraderos tras una barrera.
- Barrera = `VNOP_IOCTL(vp, F_FULLFSYNC)` (vacía journal + `DKIOCSYNCHRONIZE`) seguida de `herolte_ufs_sync()` directo
  (nueva función exportada desde `herolte_ufs.c`, envoltorio de `ufs_sync_cache()`), que sí devuelve el error real.
  Si la barrera falla: la instalación aborta, sin publicar nada.
- `fsync` plano no vale como barrera. `rename` sin barrera previa sobre el `tmp` es peligroso (el modelo lo reprodujo).
No se promete: durabilidad ante caché volátil del UFS, atomicidad multi-operación del sistema de ficheros, ni detectar
fallos asíncronos descartados. La atomicidad del paquete la da el protocolo (staging + roll-forward), no HFS.

## 2. Zona (bloque 0 de la zona de 128 MiB), v2
`magic "HERODRP2" | u32 proto=2 | u32 count | u64 bytes | u64 generation | u8 payload_sha256[32] | ... | u8 header_sha256[32]` (últimos 32 B).
- Identidad = (payload_sha256, generation). `id` de 64 bits = primeros 8 B del hash (solo para log).
- El kernel rechaza v1 con un mensaje claro (D1).
Escritura del host: (1) poner a cero la cabecera y verificar; (2) escribir payload con fsync y releer/verificar su SHA;
(3) escribir la cabecera sola (un bloque), fsync y verificar; (4) si algo falla, poner a cero la cabecera.
Releer con `iflag=direct` si TWRP lo soporta (por confirmar).

## 3. Estado en el volumen: `/private/var/herolte/.drop/`
- `state` (registro fijo con checksum): fase `STAGED | COMMITTED | FAILED`, generation, sha, intentos.
- `stage/` (árbol en preparación), `stage.list` (manifiesto: `F ruta` o `B apps/NAME.app`; `wifi/fw.bin` el último),
  `trash/NAME.gen` (versión anterior de un bundle, nombre por generación para evitar colisiones).
- `ready` y `consumed`: `"generation|sha"`. Pendiente para userland ⇔ `ready` válido y distinto de `consumed`.
- Toda actualización de un fichero de control: escribir `x.tmp` → barrera → `rename(x.tmp, x)`.

## 4. Algoritmo de arranque (hilo del kernel, tras el remonte rw; `herodrop=0` lo desactiva)
1. `mkdir .drop`; borrar `state.tmp`. Leer `state` (inválido/TORN ⇒ tratar como ausente, nunca roll-forward).
2. `STAGED` ⇒ completar el commit desde `stage.list` (no necesita la zona). Fin.
3. Sin zona válida ⇒ fin. `COMMITTED` con la misma identidad ⇒ asegurar `ready` salvo que ya esté `consumed`. Fin.
4. Instalar: verificar SHA-256 de la zona (lectura cruda) → validar todas las entradas (pase 1, sin escribir) →
   escribir en `stage/` → `put(stage.list)` → `put(state=STAGED)` → barrera.
5. Commit: por unidad, si existe `stage/X`: fichero ⇒ `rename` sobre el destino; bundle ⇒ `dst→trash/NAME.gen`, luego `stage→dst`.
   Idempotente: si `stage/X` ya no existe, la unidad está hecha.
6. Barrera → `put(state=COMMITTED)` → barrera → `put(ready)` → limpieza best-effort (trash, stage.list).
7. Intentos: 3 por (sha, generation); después `FAILED` hasta una generación nueva. Nunca pánico, nunca bloquear el arranque.

## 5. Protocolo con userspace
- hero-run espera `ready`; si `ready != consumed`: mueve `apps/*.app` a `/Applications`, registra en LaunchServices y escribe `consumed` (tmp + barrera + rename). Ya no borra `ready`.
- El kernel nunca recrea `ready` si coincide con `consumed` ⇒ desaparece el ciclo de reinstalación por arranque.
- Los ficheros sueltos (`autorun`, libs, `wifi/*`) se publican por `rename` sobre el destino: el consumidor ve el viejo o el nuevo completo; un proceso que ya lo tiene abierto conserva su inodo.

## 6. Tabla de fallos
| Fallo | Resultado |
|---|---|
| Corte antes de `STAGED` duradero | Destinos intactos; reinstala desde la zona. |
| Corte durante el commit | `STAGED` duradero ⇒ roll-forward al siguiente arranque, aunque la zona haya cambiado. |
| Corte tras `COMMITTED`, antes de `ready` | Se republica `ready` salvo que ya esté `consumed`. |
| Fallo de barrera (ETIMEDOUT/EIO) | Se aborta; no hay `COMMITTED` ni `ready`; reintento al siguiente arranque (máx. 3). |
| `state` corrupto | Se ignora; reinstalación completa (idempotente). |
| Zona borrada tras una instalación a medias | Con `STAGED`: completa la versión nueva. Sin `STAGED`: versión vieja íntegra. |
| Espacio agotado | Falla en staging: destinos intactos. |

## 7. Arquitectura de código y pruebas
- `herolte_drop_core.c/.h`: parser, máquina de estados y recuperación sin dependencias del kernel (tabla de operaciones: leer zona, ficheros, barrera). `herolte_drop.c`: enlace con VFS/UFS.
- Prerrequisitos de kernel: `herolte_ufs_sync()` exportada; un envoltorio exportado de `renameat_internal` (es `static` en `vfs_syscalls.c:8929`; acepta `UIO_SYSSPACE`); SHA-256 vía corecrypto (`osfmk/corecrypto/ccsha256_di.c` existe; enlazado por confirmar).
- Lector de payload: aritmética por delta (`off >= pos && off-pos <= have && len <= have-(off-pos)`), nunca `pos+have-off`.
- Pruebas aisladas, en este orden: modelo (hecho) → harness C del core con FS en memoria e inyección de cortes/fallos → compilación XNU → dispositivo (autorización específica).

## 8. Decisiones abiertas (valor por defecto propuesto)
D1 rechazar paquetes v1 (default) / modo legado. D2 SHA-256 en kernel (si no enlaza: plan B a decidir).
D3 `wifi/`: fusión por fichero con `fw.bin` el último (default); queda una carrera si el Wi-Fi ya leyó el par antiguo.
D4 3 intentos. D5 numeración: sustituir 0332+0333 por una reescritura (decide el responsable del historial git).
D6 exportar `herolte_ufs_sync()` y usarlo tras cada `F_FULLFSYNC`. D7 estado en el volumen raíz HFS.
D8 limpieza de directorios huérfanos de `stage/`/`trash/` (necesita recorrer directorios): fuera de la primera entrega.

## 9. Lo que el modelo no demuestra
Solo valida la lógica del protocolo bajo los supuestos de la cabecera de `drop_v2_model.py`. No demuestra: que `F_FULLFSYNC`
funcione llamado desde un hilo del kernel, que `renameat_internal` funcione con contexto de kernel y `AT_FDCWD`, que el
volumen del S7 tenga journal ni cómo hace replay, el estado de la caché de escritura del UFS, ni la semántica de `rename`
de directorios sobre HFS en este montaje.

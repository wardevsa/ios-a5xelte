# Registro de decisiones — DROP v2

Tomadas por el **jefe de proyecto suplente** (asistente) el 2026-11-12, con mandato del usuario: decidir a alto nivel, **sin flashear
ni formatear el teléfono** (eso exige consejo con el jefe). Cada decisión es reversible; la última columna dice cómo.
Pendientes de ratificación por el responsable del proyecto.

| # | Decisión | Motivo | Cómo se revierte |
|---|---|---|---|
| 1 | DROP v2 sustituye al protocolo 0332/0333 | `fsync` plano de HFS+ no vacía journal ni caché; HFS pierde el error de `DKIOCSYNCHRONIZE`; 0333 tenía un fallo de límites en `hdrop_at` | no fusionar la rama |
| 2 | El parche entra como **0334 sobre 0332** (lo commiteado), no sobre el borrador 0333 | con 0333 delante, 0334 no aplica y el CI lo salta sin avisar | `preflight.py` falla si ambos están |
| 3 | El borrador 0333 queda **sin efecto** y no se commitea | 0334 reemplaza `herolte_drop.c` entero | el fichero del jefe sigue intacto en su árbol |
| 4 | Trabajo en la rama `herolte-drop-v2` (worktree separado) | no alterar la rama ni el árbol sin commitear del jefe | `git worktree remove` + `git branch -D herolte-drop-v2` |
| 5 | Rechazar paquetes v1 con mensaje claro | evitar ejecutar un protocolo sin verificación | cambiar en el núcleo (`hdc_zone_header`) |
| 6 | SHA-256 propio en el núcleo (sin corecrypto) | no depender de un enlazado no verificable | sustituir `sha_*` por corecrypto |
| 7 | 3 intentos por paquete, luego `FAILED` hasta nueva generación | evitar reinstalaciones en bucle | `HDC_MAX_TRIES` |
| 8 | Barrera = `F_FULLFSYNC` + `herolte_ufs_sync()` directo | es la única vía que devuelve el error real del UFS | — |
| 9 | Limpieza de `trash/` y directorios huérfanos aplazada | necesita recorrer directorios; no corrompe nada | — |
| 10 | Subir **solo** esta rama al fork `mio` y lanzar el CI | es la única forma de saber si 0334 y `hero-run.c` compilan | `git push mio --delete herolte-drop-v2` |
| 11 | `mesa-ios.yml` dispara también en esta rama (commit aparte) | el fork no tiene ese workflow en su rama por defecto | quitar ese commit antes de fusionar |
| 12 | No se commitea el informe interno ni las copias del teléfono | contienen rutas y datos privados (IMEI en las copias) | — |

## Fuera de mandato (necesitan al jefe)
Flashear BOOT, formatear/escribir USERDATA (instalación completa de iOS: borra el Android del teléfono de pruebas), escribir la zona DROP,
fusionar la rama, publicar nada fuera del fork, y el validador `tools/validate-repo.py` (ya fallaba antes por huecos/duplicados de numeración;
con 0334 hay un hueco más porque 0333 no está en la serie commiteada).

# Corrección Unicode (D-0017): qué se implementó, qué mide y qué falta (T-0024, 2026-11-13)

**Autoridad:** D-0017 (Director, 2026-11-13) y D-0018 (sin R2 previo; imagen nueva con nombre nuevo; la anterior intacta). **No autorizan** montar imágenes, `sudo` ni R2 (D-0005 sigue). Nada se ha ejecutado en el teléfono. Nivel de evidencia: **L2** (herramientas y modelo validado contra el código real de XNU; **ningún montaje real de Linux**).

## 1. Qué se implementó (en git)
- `tools/hfsplus-names/xnu_names_stage.py`: planea (`plan`, solo lectura) y aplica (`apply`) el renombrado de las **hojas** de un árbol de *staging* (ext4, sin root) a la forma de nombre de XNU (`hfs_names.hfs_component`). Se niega, sin tocar nada, si algún **directorio** cambiaría de nombre, si hay **colisiones** (incluida con un fichero existente) o nombres de más de 255 unidades UTF-16; no sigue enlaces simbólicos; no sale del árbol; no sobrescribe. Con `--ko` informa de qué nombres, **ya renombrados**, el `hfsplus` de Linux montado por defecto volvería a cambiar.
- `tools/hfsplus-names/test_xnu_names_stage.py`: 8 pruebas (plan sin efectos, renombrado a forma XNU, árbol ASCII intacto, colisión, directorio que cambiaría, nombre demasiado largo, enlaces simbólicos, el caso de `U+0E33`). Resultado: **OK**. `test_hfs_names.py`: **16 OK** (incluye diferencial contra el `utfconv` real de XNU).

## 2. Medida sobre los 32 nombres discrepantes (modelo; no montaje)
Entrada: los 32 nombres de `diff32.tsv` (resultados del laboratorio, fuera de git). Para cada uno: `xnu = hfs_component(nombre)` y, si el `hfsplus` de Linux **por defecto** (sin `nodecompose`) lo volviera a descomponer, ¿cambiaría?
| Resultado | Nombres |
|---|---|
| **Ya correctos solo con renombrar a forma XNU** (Linux por defecto los deja tal cual) | **30 de 32** |
| **Siguen distintos aun renombrados** (primera diferencia `U+0E33` → `U+0E4D`: la tabla de Linux descompone SARA AM tailandés, XNU lo conserva) | **2 de 32** |
Clases del informe anterior: 15 canónicamente equivalentes, 15 no equivalentes, 2 equivalentes solo por compatibilidad. **Conclusión honesta:** la corrección de la directiva (nombres en forma XNU, sin tocar el kernel ni montar con `nodecompose`) **resuelve 30 de los 32**; **los 2 con `U+0E33` necesitan `nodecompose` (una opción de montaje) o quedar fuera del root** (alternativa C para esos 2). La premisa "sin kernel y sin R2" se sostiene para 30, no para los 32. Es un **resultado del modelo** (`linux_nfd`, validado sobre la tabla del `hfsplus.ko` del PC), no de un montaje.

## 3. Qué NO se ha hecho (y por qué)
1. **No se generó la imagen nueva.** Escribir un volumen HFS+ en Linux requiere montarlo (`privileged-or-mount`, acción roja): ni D-0017 ni D-0018 la autorizan. Se deja como tarea bloqueada **T-0025** con su solicitud.
2. **No se cableó** en los scripts del laboratorio (`apply_meta_img.py`, `stage_links.py`, `verify_meta.py`, `hfsx_check.py`, `names_static.py`): viven en el scratchpad (no en git; copia en E-0014) con sumas fijadas; punto 3 de la corrección (un único punto de traducción manifiesto→ruta) y punto 4 (`names_static` con `xnu_nfd`) pendientes.
3. **No se aplicó `apply` a ningún árbol real** (el árbol de *staging* del root contiene binarios de Apple que no se tocan sin necesidad).
4. Un nombre POSIX con `:` es `/` en HFS+: no es creable en ext4; el generador debe tratarlo en su propia traducción (no en este renombrado).

## 4. Para continuar
**Decisión pedida (jefatura/Director):** para los 2 nombres con `U+0E33`, ¿`nodecompose` en el montaje (parte del paquete T-0025 con autorización roja `privileged-or-mount`), o dejarlos fuera del root? El resto de T-0025 es mecánico: renombrar el staging con `apply`, montar, copiar, verificar con `hfsx_check` (esperando la forma XNU en el catálogo en bruto) y archivar con nombre nuevo.

## 5. Decisión D-0020 (Director, 2026-11-13) y limitación conocida
**Decisión:** excluir del root los 2 ficheros con `U+0E33`; **no** usar `nodecompose` ni parchear XNU.
**Limitación conocida (KI-0006):** 2 ficheros de `WorkflowKit.framework/th.lproj/DefaultShortcuts/` con `U+0E33` (tailandés) quedan fuera del root porque la tabla de Linux los descompone y XNU los conserva. Según la jefatura iOS hace fallback a inglés y no afecta al funcionamiento; **el ingeniero no lo ha verificado**.
Ficheros (carpeta bajo `th.lproj/DefaultShortcuts/`; nombre en puntos de código, extensión `.shortcut` en el original):
- `0C6A13DC-9084-4A3D-B056-D1C456F011B0/` — `0E04 0E33 0E2A 0E31 0E48 0E07 0E25 0E31 0E14 0E04 0E37 0E2D 0E2D 0E30 0E44 0E23`
- `1401D3FE-B4C5-4DDA-96EE-B149258AD492/` — `0E04 0E33 0E2A 0E31 0E48 0E07 0E25 0E31 0E14`
**Cómo se excluyen sin borrar nada:** `xnu_names_stage.py plan TREE --ko hfsplus.ko[.zst] --exclude-list NUEVO.txt` escribe las rutas relativas que necesitarían `nodecompose`; el copiado usa esa lista como `--exclude-from`. Verificación hecha (modelo validado contra el `utfconv` real de XNU, no un montaje): **30 de 32 nombres coinciden con XNU tras renombrar; los otros 2 son estos**.
**Sigue pendiente (T-0025):** generar la imagen exige montar HFS+ con `sudo` (`privileged-or-mount`, roja). "T-0025 autorizada" en la directiva no nombra esa acción ni los comandos; D-0020 la deja expresamente sin autorizar. Además la directiva pide no tocar los scripts del laboratorio, que son los que montan (`populate_image.sh`).

# S7GE — plan para meter iOS en el S7 (decisión del ingeniero, 2026-11-15)

**Decisión (delegada por el Director): vía B, construir la raíz en este PC con el material que ya tenemos.** Razones: (A) un repositorio privado con el flujo `ios-root` publica software de Apple en un release de GitHub y gasta cuota de macOS ×10; (C) depende de que otra persona la tenga. B no cuesta nada, mantiene los binarios de Apple en local (`AGENTS.md`) y **ya está medio hecha**.

## Lo que ya existe (todo verificado, fuera de git)
| Pieza | Dónde | Estado |
|---|---|---|
| Miembros del IPSW público de Apple (iPhone10,3, iOS 16.7.16, build 20H392): `os.dmg` 4,7 GB, `systemos.dmg` 2,7 GB, `appos.dmg` | `~/HackiOS/builds/device-day/ipsw-root/` | SHA-384 comprobado contra su `BuildManifest.plist` |
| **Imagen HFSX de laboratorio** con las tres raíces y los nombres adaptados a XNU (`lab-full-xnu`) | `/media/pioxi/F20C31440C31055F/IOS-S7-archive/02-extractions/lab-full-xnu-20261114.img` | 21 474 836 480 B (20 GiB), SHA-256 `747d0245…ec27f`, verificada (E-0010…): cabe en USERDATA (23 431 790 592 B) |
| Herramientas de staging/tuning (`a5xelte-stage-ios-root.sh`, `herolte-tune-ios-root.sh`, `plutil_lite.py`) y su verificación | `tools/` | pruebas con `fakeroot` en verde; **no probadas sobre un montaje real** |
| Copias de seguridad de SYSTEM, USERDATA y RECOVERY del teléfono | NVMe, `IOS-S7-backup/2026-11-14-engineer-full/` | E-0123…E-0125, verificadas contra el teléfono |
| Kernel que llega a `bsd_init` y falla al montar la raíz | BOOT = `min16` | E-0177 |
| Escritor rápido y verificado de USERDATA | `tools/herolte-write-userdata.py` (+ `test_write_userdata.py`, 7 pruebas) | listo; **nunca ejecutado contra el teléfono** |

## Fases (mañana)
**F0 — comprobaciones, sin `sudo` y sin tocar el teléfono (10 min).** Hash de la imagen de laboratorio y de los `.dmg`; espacio libre (NVMe: ~200 GB; `/` solo 14 GB: **no trabajar en `/`**); `fakeroot`, `mkfs.hfsplus`, `fsck.hfsplus`, `7z`, módulo `hfsplus` ya están. Lo hago yo.

**F1 — preparar la imagen final (necesita `sudo`: lo teclea el Director con `!`).** Sobre una **copia** de la imagen de laboratorio (la original no se toca):
1. `cp` de la imagen al NVMe de trabajo (~5 min) y comprobar su SHA-256.
2. `sudo mount -t hfsplus -o force,rw,loop COPIA.img /mnt/ios-root` (lectura-escritura; Linux deja el diario vacío).
3. `sudo bash tools/herolte-tune-ios-root.sh /mnt/ios-root 20H392` (quita CommCenter, desactiva los vigilantes de SpringBoard, marca el asistente completado, `autorun`, esqueleto de `/private/var/containers`…).
4. `sudo umount`, `fsck.hfsplus -f -n`, firma `HX` en el offset 1024, SHA-256 de la imagen final y tamaño ≤ la partición. **Este es el hash que se autoriza.**
Riesgo: el *tuning* se probó con árboles falsos, no con el `launchd.plist` real; si falla, se arregla en la copia y se repite (sin coste: es un fichero).

**F2 — prueba del transporte, sin escribir el disco (5 min, con `adb`).** `herolte-write-userdata.py IMG SHA --execute --dry-transport` envía trozos a `/dev/null` en el teléfono y mide la velocidad. Es una lectura/escritura en la memoria del teléfono, no del disco; la haré con su visto bueno.

**F3 — escribir USERDATA (ROJO, borra Android; ~25 min a ~18 MB/s).**
- Requiere su autorización **con la imagen y el hash de F1**, registrada en gobierno (`device-write-userdata`, tarea T-0044). La herramienta se niega a escribir sin ella, o si la partición no es `sda18` de 23 431 790 592 B, o si está montada, o si el hash no es el autorizado.
- Cada trozo de 64 MiB se escribe por `nc | dd` y solo se acepta si el SHA-256 que calcula el teléfono al leerlo del disco coincide con el del PC; al final, el SHA-256 del prefijo de USERDATA leído en el teléfono debe ser el de la imagen.
- **Vuelta atrás:** las copias verificadas de USERDATA y SYSTEM (la misma herramienta escribe `USERDATA.img` de 23 431 790 592 B tal cual) y el BOOT original.
Texto de autorización a firmar (con el hash real de F1):
> Autorizo escribir en `USERDATA` del S7 desde TWRP, con `tools/herolte-write-userdata.py --execute`, la imagen `<RUTA>` con SHA-256 `<HASH>` (BORRA Android; copias verificadas E-0124/E-0125). Solo USERDATA. Firmado PioXI.

**F4 — primer arranque con raíz iOS (sin escribir más: sirve el BOOT `min16`).** El BOOT actual ya dice `rd=ufsroot0 ufsroot=USERDATA ufsrw=0` (UFS en solo lectura): el kernel debería **montar la raíz** (ya no `cannot mount root`) y lanzar `launchd`. Lo vemos en el anillo de mensajes. Es lo más probable que falle por algo nuevo (normal): se anota la última línea.

**F5 — iterar** (un cambio por vez, cada uno con su permiso): `ufsrw=1 rootrw=1`, los argumentos de `herolte-howto.md` §4 (`cs_enforcement_disable=1 unentitled_ios_sim_launch=1 ignition_level=1 launchd_unsecure_cache=1 …`), pantalla (`a5fb_*`, `sweetfb_*`), y por fin GPU/Wi-Fi/energía **de uno en uno** (`herogpu=1`… con sus pruebas).

## Qué puede salir mal y qué haremos
| Riesgo | Probabilidad (mi estimación, L0) | Respuesta |
|---|---|---|
| El *tuning* sobre el root real falla | media | arreglar en la copia (fichero), repetir |
| El `hfsplus` de XNU no monta la imagen creada en Linux (diario, nombres, xattrs) | baja-media | el laboratorio verificó nombres y diario con `fsck`; si falla, el log lo dice (`hfs_mount: …`) |
| `launchd` no arranca (firmas, `cs_enforcement_disable`, cachés) | **alta** | es el trabajo normal de F5 |
| La escritura en USERDATA se corta | baja | reanudable; la copia de USERDATA restaura |
| Se pierde algo de Android que importaba | — | las copias de SYSTEM/USERDATA son completas y verificadas; la tarjeta SD no se toca |

## Qué NO se hace sin su decisión
Escribir USERDATA; cambiar `ufsrw`; cargar GPU/Wi-Fi/energía; tocar EFS, RECOVERY o los bootloaders (nunca).

## Qué buscar en F4 (primer arranque con raíz iOS, anillo de mensajes)
Ordenado por lo que esperaría ver (L1: leído en `bsd_init.c`/`herolte_ufs.c`; sin medir):
1. **Desaparece** el `cannot mount root, errno = %d` repetido; aparecen líneas de `hfs_mount`/`hfs_mountfs` sin error y, justo después, las de `bsd_init` (`calling VFS_ROOT`…) — es el éxito del montaje.
2. Mensajes de `launchd`/`xpc` o de `bsd_utaskbootstrap`; un `panic` con la cadena de arranque (p. ej. `launchd exited`, `Process 1 exec of /sbin/launchd failed`) **se dibuja** en la consola temprana: copiarlo literal.
3. Si sigue el `cannot mount root`: leer el **`errno`**; mi anillo solo muestra la cadena de formato, así que habría que enganchar también los valores (mejora pendiente: imprimir el primer argumento entero).
4. Mensajes de `HEROLTE UFS` con errores de lectura (`lun … cmd … failed`) indicarían un problema de almacenamiento, no de la imagen.

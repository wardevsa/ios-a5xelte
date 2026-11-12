# Root de iOS para el S7 sin pagar nube: estado y camino Linux

Estado a 2026-11-12. **No se ha construido el root todavía.** Lo que sí está hecho es lo que no cuesta nada ni exige `sudo`.

## Hecho (todo fuera del repositorio, en `~/HackiOS/builds/device-day/ipsw-root/`)
- Descargados del IPSW **público** de Apple (iPhone10,3, iOS 16.7.16, build 20H392), con `tools/remotezip.py` (solo se bajan los miembros
  necesarios, 7,5 GB): `os.dmg` (4,7 GB), `systemos.dmg` (2,7 GB) y `appos.dmg` (10 MB).
- **Verificados** contra los resúmenes SHA-384 del propio `BuildManifest.plist` de Apple: los tres coinciden.
- `d22ap.adt` extraído del IPSW con `pyimg4` (como hace el workflow `ios-root`); no hace falta el repo privado para eso.
- Los binarios de Apple **no se suben a git** (`AGENTS.md`).

## Qué se descubrió sobre el camino Linux
| Pregunta | Resultado |
|---|---|
| ¿Hace falta `apfs-fuse`? | **No para extraer.** `7z` 23.01 (ya instalado) lee el APFS de los `.dmg`, **descomprime** los ficheros comprimidos de Apple (comprobado: `sbin/launchd`, 541 600 bytes, cabecera Mach-O válida) y expone **usuario, grupo, modo, enlaces duros (iNode) y symlinks** (`7z l -slt`) |
| ¿Soporta este PC HFS+? | Sí: módulo `hfsplus` del kernel y `mkfs.hfsplus` instalados |
| ¿Qué sigue pidiendo `sudo`? | montar la imagen HFS+ (`mount -t hfsplus -o force,rw`), poblarla con los propietarios de iOS (`chown`) y ejecutar `tools/a5xelte-stage-ios-root.sh` / `tools/herolte-tune-ios-root.sh` como root. Sin `sudo` sin contraseña en este PC, esos pasos los tiene que lanzar una persona |
| ¿Qué es específico de macOS en el pipeline? | `hdiutil` (crear y montar la imagen) y `plutil` (4 sitios de `herolte-tune-ios-root.sh`); `a5xelte-stage-ios-root.sh` no usa herramientas de macOS. En Linux: `mkfs.hfsplus -s -J` + `mount`, y un sustituto de `plutil` con `plistlib` |

## Camino propuesto (sin coste de nube)
1. Extraer los tres `.dmg` con `7z x` a directorios y guardar el manifiesto de propietarios/enlaces de `7z l -slt` (sin root).
2. `mkfs.hfsplus -s -J` sobre un fichero de 20 GiB; **con `sudo`**: montarlo y copiar con los propietarios del manifiesto y los enlaces duros.
3. Ejecutar el staging y el *tuning* (adaptando `plutil`), desmontar y comprimir (`root.img.gz.part*`, trozos de 1900 MB).
4. Comparar con la guía: tamaño ≤ 21 566 MiB (cabe en USERDATA), firma `HX` en el offset 1024.
Lo que cuesta es escribir y probar ese guion (propietarios y enlaces duros son lo delicado); no hay coste de cuota. El resultado **no se puede validar sin el
teléfono** (que iOS arranque desde él).

## Comparación con las otras opciones
| Opción | Coste | Bloqueo |
|---|---|---|
| Repo privado + workflow `ios-root` | cuota de macOS ×10 en repos privados; puede generar cargos | decisión del responsable |
| **Linux local (esta)** | ninguno | alguien con `sudo` para montar y poblar |
| Que lo facilite el responsable | ninguno | depende de él |

Instalar el root **borra todo el Android** del teléfono: consejo con el responsable antes.

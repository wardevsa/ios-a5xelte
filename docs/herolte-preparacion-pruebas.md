# HEROLTE: preparación de las pruebas en el S7 — estado a 2026-11-13

**Hasta hoy NO se ha probado nada en este Galaxy S7.** Las líneas de `HEROLTE_PROGRESS.md` sobre arranques de iOS, Wi-Fi, GPU o sonido son el
historial heredado del proyecto (otro teléfono y otro desarrollador): sirven de referencia, no son evidencia de esta unidad. Todo lo de abajo se
ha hecho y verificado **en el PC**, sin tocar el teléfono, las particiones ni montar imágenes.

## 1. Imágenes BOOT candidatas (solo escriben BOOT; ninguna se ha escrito)
| Peldaño | Imagen (`~/HackiOS/builds/device-day/…`) | Línea de arranque | Verificación |
|---|---|---|---|
| N1 sonda | `boot-candidates/probe-boot-clang.img` | — (no ejecuta XNU, vuelve a TWRP a los 60 s) | hash del kit (`SHA256SUMS`, `MANIFEST.sha256`: 199 ficheros OK) |
| **N2 XNU, solo lectura** | `boot-candidates-n2/xnu-boot-v2-n2-console-clang.img` | mínima de diagnóstico, con consola, `cpus=8`, **sin** `ufsrw=1` ni `rootrw=1` | `herolte-verify-boot.py --profile n2-readonly`: 0 fallos |
| N2 (variante) | `boot-candidates-n2/xnu-boot-v2-n2-readonly-clang.img` | la diaria sin `ufsrw/rootrw` (conserva `a5fb_noconsole=1`: sin texto en pantalla) | ídem, 0 fallos |
| ~~N2 antiguo~~ | `boot-candidates/xnu-boot-v2-clang.img` | la diaria **con** `ufsrw=1 rootrw=1` | **no es de solo lectura**: el verificador lo marca (2 fallos). No usarlo para N2 |

Hallazgo: `xnu-boot-v2-clang.img`, descrito en el kit como "peldaño N2", llevaba `ufsrw=1`, que deja escribir al driver UFS; `docs/estado-y-camino-a-flashear.md` dice que N2 debe
ir sin él (así USERDATA/Android quedan intactos). Las dos imágenes nuevas se construyeron con el mismo kernel DROP v2 (SHA-256 `e678b454…`), el mismo ADT y el mismo cargador (clang, de conveniencia)
sobre el BOOT original copiado del teléfono. Hashes en `boot-candidates-n2/SHA256SUMS`.

`tools/herolte-verify-boot.py` (solo lectura) comprueba: cabecera ANDROID!, SHA-1 de identificación, cola `SEANDROIDENFORCE`, que cabe en la partición de 40 MiB, cargador arm64, payload `SWEETXNU`
(tabla de segmentos, solapes, entrada, `kernel_end`, ADT con `dram-base/size` coherentes, línea de arranque), **que el payload se reproduce byte a byte con `mkpayload.py` desde el kernel y el ADT embebido**,
y frente al BOOT original: DTBH, ramdisk y direcciones sin cambios. `tools/test_verify_boot.py`: 9 pruebas, incluidas manipulaciones de bytes, cola quitada, truncado, línea de arranque y DTBH alterados.
**No prueba que arranque**: esa parte sigue siendo una hipótesis hasta N2.

Sigue abierto (decisión del responsable): cargador compilado con GCC (el del kit es de clang) y presupuesto de la línea diaria (604/607).

## 2. Root de iOS (20 GiB): qué está hecho y qué no (laboratorio T04-R, scratchpad de sesión + copia en `IOS-S7-archive/06-session-backups/`)
| Etapa | Estado |
|---|---|
| IPSW público descargado y verificado (SHA-384 de Apple) | hecho |
| Extracción con `7z`, manifiestos de propietarios/modos/enlaces/tiempos, verificación estricta de contenido (`os`, `systemos`, `appos`) | hecho: `systemos` 1459/1459 OK y `appos` 884/884 OK (verificación estricta). `os`: la verificación previa al enlazado dio 185 errores (4 ausentes y 181 enlaces duros sin crear); `relink.py` creó 37 046 enlaces, 0 nombres ausentes; la comprobación de `os` ya en la imagen poblada dio 318 070 OK, 2 `EXTRA` y 1 nombre normalizado. No hay un `os.final` equivalente al de las otras dos |
| Tuning (`plutil_lite`) y staging portables a Linux, probados con `fakeroot` | hecho (commits `5b48ed9`…`44cc748`); no probado con root real |
| Imagen HFSX de 20 GiB creada y **poblada con root real** (`lab-full.img.partial`, 12 GB) | hecho (2026-11-13 10:20), por el responsable con `sudo` |
| Verificación de la imagen | **FALLA** (`ROOT_HFSPLUS_LAB_FAILED`): metadatos del árbol OK salvo 2 `EXTRA` y 1 nombre normalizado; `fsck_hfs` dice "corrupt" |
| Imagen válida, comprimida en partes, firma `HX` | pendiente |
| Escribir el root en USERDATA | pendiente; borra Android; decisión del responsable |

**Causa del fallo (comprobada en la imagen, solo lectura):** de 329 nombres no ASCII distintos, 297 coinciden con la descomposición de XNU y **32 no**. Son atajos de
`WorkflowKit.framework/{ar,el,ro,th}.lproj/DefaultShortcuts/*.shortcut`. El `hfsplus` de Linux usa una tabla de descomposición Unicode distinta de la de XNU (Unicode 3.2):
alef con hamza (U+0623/0625) no se descompone, la tilde griega sale como U+030D en vez de U+0301, la coma bajo de rumano (U+0219/021B) no se descompone y el SARA AM tailandés (U+0E33) sí.
Impacto en iOS (hipótesis, no medida): esas 32 rutas no se podrían abrir por su nombre; nada del arranque depende de ellas. Pero `fsck_hfs` en iOS podría marcar el volumen.
Siguiente paso técnico: el experimento `nodecompose` (T04-R2, rev2), que necesita montar imágenes con `sudo` y la autorización del responsable. Mientras tanto no se ha ejecutado.

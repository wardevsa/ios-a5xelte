# HEROLTE: preparación de las pruebas en el S7 — estado a 2026-11-13

**Hasta hoy NO se ha probado nada en este Galaxy S7.** Las líneas de `HEROLTE_PROGRESS.md` sobre arranques de iOS, Wi-Fi, GPU o sonido son el
historial heredado del proyecto (otro teléfono y otro desarrollador): sirven de referencia, no son evidencia de esta unidad. Todo lo de abajo se
ha hecho y verificado **en el PC**, sin tocar el teléfono, las particiones ni montar imágenes.

## 1. Imágenes BOOT candidatas (solo escriben BOOT; ninguna se ha escrito)
| Peldaño | Imagen (`~/HackiOS/builds/device-day/…`) | Línea de arranque | Verificación |
|---|---|---|---|
| N1 sonda | `boot-candidates/probe-boot-clang.img` | — (no ejecuta XNU, vuelve a TWRP a los 60 s) | hash del kit (`SHA256SUMS`, `MANIFEST.sha256`: 199 ficheros OK) |
| **N2 XNU, solo lectura (candidata vigente)** | `boot-candidates-n2/xnu-boot-v2-n2ro-clang-20261113.img` (SHA-256 `26a39560ed963c89f1593b2b3db59faba55235c4140dce28686649f8799d1e29`) | mínima de diagnóstico, con consola, `cpus=8`, y **explícitos** `ufsrw=0 herolog=0 herodrop=0` | `herolte-verify-boot.py --profile n2-readonly`: **47 PASS, 0 FAIL**, salida 0; procedencia en `…20261113.PROVENANCE.txt` |
| N2 (versión previa, sin los `=0` explícitos) | `boot-candidates-n2/xnu-boot-v2-n2-console-clang.img` | mínima, sin `ufsrw`/`rootrw` | con las reglas actuales: 3 FAIL (faltan `ufsrw=0 herolog=0 herodrop=0`); no escribe, pero no es inequívoca |
| N2 (variante) | `boot-candidates-n2/xnu-boot-v2-n2-readonly-clang.img` | la diaria sin `ufsrw/rootrw` (conserva `a5fb_noconsole=1`: sin texto en pantalla) | 3 FAIL, igual que la anterior |
| ~~N2 antiguo~~ | `boot-candidates/xnu-boot-v2-clang.img` | la diaria **con** `ufsrw=1 rootrw=1` | **no es de solo lectura**: 4 FAIL. No usarlo para N2 |

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

## 3. Cómo funciona la regla de solo lectura de N2 (hechos del código, parches 0030/0031/0204/0206/0240/0334)
- `su.writable = (rw != 0)`: el driver UFS escribe con **cualquier** `ufsrw` distinto de 0 (1, 2, 0x1, `abc`, o el nombre sin valor), no solo con `=1`. `rootrw` se evalúa igual (0031).
- `herolog` (log persistente al final de USERDATA) solo escribe con `ufsrw`; `herodrop` (zona DROP) corre tras el remontaje en lectura-escritura. Por eso N2 lleva `ufsrw=0 herolog=0 herodrop=0` explícitos (cinturón y tirantes).
- El verificador (`--profile n2-readonly`) trata como habilitación todo lo que no sea exactamente `=0` para `ufsrw`, `rootrw`, `emmcwrite`; exige los argumentos de N2 (`ufsrw=0 herolog=0 herodrop=0 rd=ufsroot0 ufsroot=USERDATA cpus=8`);
  rechaza nombres duplicados (también repeticiones "inofensivas"), cualquier texto de escritura fuera de los segmentos del kernel (cabecera, cargador, ADT, ramdisk, DTBH, cola) y un `boot-args` en el ADT.
- Resultados registrados en `boot-candidates-n2/verify-all-20261113.txt`: candidata vigente 47 PASS/0 FAIL (salida 0); las cuatro anteriores con 3 o 4 FAIL (salida 1); `probe-boot-clang.img` 1 FAIL esperado (la sonda N1 no lleva payload XNU, el verificador es para N2).
- Pruebas: `python3 -W ignore tools/test_verify_boot.py` → 22 pruebas OK (positivas, cada forma de habilitación, duplicados, argumentos que faltan, texto de escritura en cabecera/cargador/ramdisk/ADT, magic, tamaños, cola, partición, segmentos, entrada, `kernel_end`, `phys_base`, reproducibilidad del payload). Mutación del verificador (4 reglas desactivadas una a una): la suite falla en los 4.
- Reconstruir: `tools/herolte-build-n2.sh KERNEL ADT LOADER STOCK OUTDIR NOMBRE` (no sobrescribe; escribe imagen, payload, línea, verificación y procedencia).

## 4. Preflight (DROP v2 y kit), 2026-11-13: 14 correctas, 1 aviso, 0 fallos, salida 0 (`boot-candidates-n2/preflight-20261113.txt`)
El aviso es "no hay compilador cruzado aarch64 (GCC) para el cargador": limitación del entorno, no un defecto del kit; el cargador del kit es de clang. Sigue **abierto** (decisión del responsable: autorizar el GCC de Arm descargado o compilarlo él). No se ha convertido en PASS.

## 5. `lab-full.img.partial.populated`: evidencia conservada y pregunta que resolvería R2
- Conservado sin cambios: `lab-full.img.partial` (21 474 836 480 bytes, mtime 10:20:30), `.populated`, `.populated.sha256`, `logs/verify_full.log` (`ROOT_HFSPLUS_LAB_FAILED`, SHA-256 antes y después `e724f981…c79496`), `audit/` (catálogo, `unicode_*`, `fsck_*`), y la copia verificada en `IOS-S7-archive/06-session-backups/`. Ni reparada ni regenerada.
- **Pregunta concreta de R2:** el volumen se pobló con el `hfsplus` de Linux por defecto, que descompone los nombres con su propia tabla. ¿Con la opción de montaje `nodecompose` y nombres ya descompuestos con la tabla de XNU (Unicode 3.2), el `hfsplus` de Linux escribe en disco nombres **byte a byte iguales a los que generaría XNU**, y `fsck_hfs` deja de marcar el volumen como corrupto? R2 lo mide con tres imágenes de 512 MiB (A sin `nodecompose`, B y C con `nodecompose`), nunca sobre `lab-full`.
- **Decisión humana que requeriría** (no tomada, no solicitada ahora): (1) autorizar ejecutar R2 con `sudo` (montar imágenes en bucle del laboratorio) con el ejecutor `rev2` validado (pendiente la ronda 2 de mutación y la revisión independiente); (2) según el resultado, elegir entre rehacer el root con `nodecompose` + nombres pre-descompuestos (imagen nueva, `lab-full` queda como evidencia), aceptar las 32 rutas con nombres distintos (documentado), o excluirlas del root. Hasta entonces R2 no se ejecuta y no se pide `sudo`.

# Auditoría del proyecto — 2026-11-12

Auditoría del jefe de proyecto suplente sobre lo que hay en el repositorio, el CI, el teléfono de pruebas y lo hecho durante la sesión.
Cada hallazgo lleva su evidencia. **Gravedad:** alta = bloquea instalar o puede dañar; media = causa pérdida de tiempo o riesgo
recurrente; baja = higiene.

## Resumen
| Gravedad | Nº | Estado |
|---|---|---|
| Alta | 4 | 1 resuelto en la rama (CI), 3 abiertos |
| Media | 7 | 3 resueltos o mitigados en la rama, 4 abiertos |
| Baja | 4 | abiertos |
Sin secretos ni datos personales en lo versionado de la rama (`git grep` de claves, contraseñas, correos; las únicas coincidencias son las palabras
"IMEI"/"serialize" en texto). Las copias del teléfono (IMEI) están fuera del repo con permisos 600/700.

## Alta
| # | Hallazgo | Evidencia | Estado |
|---|---|---|---|
| A1 | **No hay root de iOS** (20 GiB) | la cuenta solo tiene el fork público; `gh repo list` no muestra `ios-herolte-root` | **abierto.** Descargado y verificado el IPSW (7,5 GB, SHA-384 de Apple) y descubierto un camino Linux sin nube (`docs/herolte-root-linux.md`); falta construir y alguien con `sudo` |
| A2 | **DROP v2 y el splash nunca se han ejecutado en el teléfono** | solo pruebas de anfitrión y compilación en CI | abierto. Dudas de ejecución reales: `F_FULLFSYNC` desde un hilo del kernel, `renameat_internal` con contexto de kernel, pila, la caché de escritura del UFS |
| A3 | **El CI saltaba en silencio los parches que no aplican** | `build.sh` de darwin-xnu-build escribe "Skipping patch" y sigue; `xnu.yml` filtraba esas líneas | **resuelto en la rama** (commit `ci(xnu)`): el job falla si se salta un `NNNN-*.patch` propio; 0 falsos positivos en un log real. Falta llevarlo a `herolte` |
| A4 | **El cargador que se usaría se compiló con clang, no con el GCC validado** | no hay GCC aarch64 en el PC; se descargó el de Arm (hash verificado) pero el sistema de permisos bloqueó ejecutar un binario descargado | abierto: decisión del responsable (autorizar o compilar él) |

## Media
| # | Hallazgo | Evidencia | Estado |
|---|---|---|---|
| M1 | La línea de arranque diaria mide **604 de 607** caracteres | `mkpayload.py` limita a 607; no caben `herodrop=0` (+12) ni `herosplash=1` (+13) | abierto: hay que quitar un argumento (decide el responsable) |
| M2 | **Variante de módulo Wi-Fi/BT sin comprobar** | VENDOR trae `nvram.txt_c0_plus` y `nvram.txt_murata_c0_plus`, `bcm4359C0_semco.hcd` y `_murata.hcd`; la guía fija el primero | abierto: identificar el módulo de la unidad antes de culpar al Wi-Fi |
| M3 | `tools/validate-repo.py` ya fallaba (huecos y duplicados en la numeración de parches) y nadie lo usa como puerta | falla en `8d1cf43` y en la rama (un hueco más por 0334) | abierto |
| M4 | **Dos copias de mi trabajo**: el árbol del responsable y el `worktree` de la rama | los ficheros nuevos están sin versionar en `…/wardevsa-ios-a5xelte` y versionados en `…/wardevsa-ios-a5xelte-v2` | mitigado: trabajar desde el worktree (`git -C ../wardevsa-ios-a5xelte-v2 …`); si se quiere cambiar de rama en el otro árbol, hay que retirar antes sus copias sin versionar |
| M5 | **Sin log persistente en este teléfono**: USERDATA es ext4 y el final de la partición contiene datos de Android | lectura de los últimos 4 MiB: sin cabecera `HEROLOG1` | abierto: tras instalar iOS vuelve a existir; el plan de USB lo evitaría (`docs/herolte-usb-plan.md`) |
| M6 | **Binarios de herramientas con un fallo de importación en modo aislado** | `python3 -I tools/mkadt_herolte.py` falla (`No module named adt`); `mkpayload` y `herolte-adt-ram-banks` sí funcionan | mitigado: el guion usa `python3` sin `-I` para esas herramientas |
| M7 | La documentación de instalación contaba DROP v1 | `docs/herolte-howto.md` §5 decía "copies … on every boot" | **resuelto en la rama** |

## Baja
| # | Hallazgo | Evidencia |
|---|---|---|
| B1 | **No hay fichero de licencia** y el repo mezcla GPL-2.0 (cargador, de uniLoader), APSL-2.0 (XNU) y MIT (darwin-xnu-build) | no existe `LICENSE*`/`COPYING*`; mis ficheros nuevos no llevan SPDX salvo `splash.c`. Decisión del propietario |
| B2 | Las pruebas completas tardan ~2 min y usan `/tmp` | `test_core.py` sin `--quick` |
| B3 | `NOTES.md` (437 líneas) es historia del donante SWEET y se mezcla con la documentación HEROLTE | `AGENTS.md` pide no editarlo |
| B4 | Borrador `0333` y `herolte-drop.py.pre-block1` sin versionar en el árbol del responsable | `git status`; 0334 deja a 0333 sin efecto |

## Cobertura de pruebas (lo que hay)
| Área | Qué se prueba | Dónde |
|---|---|---|
| Núcleo DROP v2 | 36 comprobaciones: 2 560 imágenes de corte, fallo de cada barrera, 81 510 dobles fallos, 19 paquetes inválidos, ventanas grandes, reintentos; con ASan/UBSan | `xnu/drop-v2/test/test_core.py` |
| Anfitrión ↔ núcleo | formato byte a byte, orden de escritura, fallos de escritura | `test_host_pack.py` |
| Userland | `.drop/ready`/`consumed` | `test_userland.c` |
| Kernel | sintaxis y tipos contra cabeceras simuladas; compilación real en CI | `check_kernel_syntax.py`, run `43223873690` |
| Splash | decodificador frente a referencia, 8 blobs inválidos | `shim/herolte/test_splash.py` |
| **Sin cobertura** | ejecución real en el teléfono; `hero-run.c` en ejecución; integridad DMA del UFS bajo carga; estabilidad con 8 núcleos | — |

## Riesgos que dependen de decisiones del responsable
Instalar iOS (borra todo el Android) · escribir la zona DROP en USERDATA · autorizar el compilador de Arm · cómo conseguir el root · qué argumento
quitar de la línea de arranque · licencia · fusionar la rama.

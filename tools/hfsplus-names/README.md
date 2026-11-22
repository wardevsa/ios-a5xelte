# hfsplus-names: análisis de nombres Unicode entre XNU y el `hfsplus` de Linux (solo análisis)
No está conectado a ninguna herramienta de generación del root. Informe: `docs/herolte-unicode-hfsplus.md`.
- `build_xnu_nfd.sh BUILDTREE_TGZ OUTDIR`: compila el `utfconv` de XNU (extraído del árbol del CI) en un ejecutable de usuario (`xnu_nfd.c`).
- `hfs_names.py`: modelo XNU (`xnu_nfd`), tabla de Linux leída de `hfsplus.ko` (`linux_table`, `linux_nfd`) y la corrección propuesta (`hfs_component`, `find_collisions`, `too_long`).
- `test_hfs_names.py`: 9 pruebas (diferencial exhaustivo contra XNU real; regresión de la evidencia del laboratorio si existe).

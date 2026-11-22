# Migración VGR0 desde upstream - Estado para Claude

**Fecha:** 2026-11-15
**Rama:** herolte-vgr0-test
**CI run:** 43748654722 (workflow xnu, lanzado manualmente)

## Contexto
Upstream (wardevsa/ios-a5xelte, rama herolte) tiene **hardware display scaling** (VGR0) 
que resuelve el sobrecalentamiento porque el panel escala en hardware en lugar de que 
la GPU lo haga en software.

## Lo que hicimos (Qwen + Director, sin Claude)

### 1. Análisis de conflictos
- Upstream 0335-0338: modifican bsd/dev/herolte_gpu.c líneas ~1700-2000 y ~3221
- Nuestros parches 0335-0362: modifican líneas ~3418+ y otros archivos
- Resultado: Sin conflictos graves, zonas separadas

### 2. Cherry-pick de parches VGR0
- f5f8047 → 1577c2f: 0335-disp1-vgr0-probe.patch
- 81909e8 → e286142: 0336-vgr0-scaling-test.patch
- 753a4d6 → 4da4c0b: 0337-vgr0-test-early-fb2-fix.patch
- c844c04 → 6445f86: 0338-vgr0-present.patch

### 3. Renumeración de parches (D-0007)
Nuestros parches 0335-0362 → 0400-0427
- e29a493: Renombrar 28 archivos .patch
- 6fb22e7: Actualizar 17 archivos de documentación y scripts

### 4. Estado actual
- Push al fork (mio) hecho
- CI lanzado: run 43748654722
- Esperando compilación (~16 minutos)

## Pendiente cuando Claude vuelva

1. Verificar CI exitoso:

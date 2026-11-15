<!-- GENERADO por tools/governance.py render desde governance/data/*.toml. NO EDITAR A MANO: se pierde en el siguiente render. -->

# Tarea activa

**T-0012 — Pruebas N1 (sonda) y N2 (XNU solo lectura) en el S7: escribir BOOT desde TWRP**

- Estado: `in_progress`  - Nivel: C
- Acciones: device-read, device-write-boot
- Depende de: T-0013
- Aceptación: Imagen con SHA-256 y verificador PASS nombrada en la autorización; copias de BOOT y EFS fuera del teléfono; resultado registrado como evidencia del dispositivo, separado de las comprobaciones del PC.
- Notas de reanudación: Fase 1 (D-0033, imagen mínima 1): escrita (E-0043) y panic en kmem_range_init (E-0044). Intento 2 (D-0034): imagen min2 con vm_compression_limit=98304 vm_compressor=2 (E-0045), a escribir con tools/herolte-flash-boot.sh; NO reiniciar sin que el Director grabe. Ver docs/S7GE_FIRST_BOOT_ANALYSIS.md.

## Cómo reanudar
1. Lee `README.md` y `HANDOFF.md`; ejecuta `python3 tools/governance.py check` y `status`.
2. Si hay tarea en curso, sigue su campo `resume` y el último fichero de `checkpoints/`.
3. Si no la hay, toma la que indique `python3 tools/governance.py next`, márcala `in_progress` en `data/tasks.toml`, ejecuta `render` y anota el primer checkpoint.

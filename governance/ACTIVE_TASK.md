<!-- GENERADO por tools/governance.py render desde governance/data/*.toml. NO EDITAR A MANO: se pierde en el siguiente render. -->

# Tarea activa

**T-0012 — Pruebas N1 (sonda) y N2 (XNU solo lectura) en el S7: escribir BOOT desde TWRP**

- Estado: `in_progress`  - Nivel: C
- Acciones: device-read, device-write-boot
- Depende de: T-0013
- Aceptación: Imagen con SHA-256 y verificador PASS nombrada en la autorización; copias de BOOT y EFS fuera del teléfono; resultado registrado como evidencia del dispositivo, separado de las comprobaciones del PC.
- Notas de reanudación: Fase 1 EJECUTADA (E-0043); primer arranque = panic en kmem_range_init, clase B (E-0044, transcripción de terceros). D-0033 cubre SOLO la imagen mínima 1 y la restauración de BOOT. Siguiente intento: candidata min2 (E-0045), que necesita una autorización NUEVA con su hash. Ver docs/S7GE_FIRST_BOOT_ANALYSIS.md.

## Cómo reanudar
1. Lee `README.md` y `HANDOFF.md`; ejecuta `python3 tools/governance.py check` y `status`.
2. Si hay tarea en curso, sigue su campo `resume` y el último fichero de `checkpoints/`.
3. Si no la hay, toma la que indique `python3 tools/governance.py next`, márcala `in_progress` en `data/tasks.toml`, ejecuta `render` y anota el primer checkpoint.

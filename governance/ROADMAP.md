# Hoja de ruta

Hitos con **puertas de entrada y de salida** medibles. Un hito no se da por cerrado hasta cumplir su criterio con el nivel de evidencia indicado y registrarlo en `STATE.md`. Las tareas concretas y sus bloqueos están en `TASKS.md`; las decisiones, en `DECISIONS.md`.
Nivel = quién tiene que intervenir (A autónomo, B revisión, C autorización del Director).

| Hito | Objetivo | Puerta de salida (evidencia exigida) | Tareas | Nivel |
|---|---|---|---|---|
| **M0 Gobierno** | Un modelo nuevo puede incorporarse leyendo el repositorio | `governance.py check` y pruebas en verde; revisión del jefe técnico; D-0001 ratificada | T-0001 | A + B (revisión) |
| **M1 Candidatas verificadas en el PC** | Imágenes BOOT N1/N2 coherentes y reproducibles | Verificador PASS, hashes, procedencia (hecho: E-0001..E-0006), cargador decidido | T-0013 | A / C (decisión) |
| **M2 Bloqueo del root resuelto** | Elegir y validar cómo se escriben los nombres HFS+ | Decisión sobre T-0003; R2 ejecutado con ejecutor validado (rev2 ronda 2 + revisión independiente) y `fsck_hfs -n` en 0 | T-0003, T-0005, T-0006, T-0004 | A, C (R2), decisión del director |
| **M3 Primer contacto con el hardware** | N1 y N2 en el S7: ¿arranca el cargador/XNU, hay 8 núcleos y GPT del UFS? | Registro fotográfico/log **de esta unidad**, separado de las comprobaciones del PC (L3), BOOT original restaurable | T-0012 | C |
| **M4 Root verificable** | Imagen de 20 GiB con verificación en PASS | `verify_full` PASS, firma `HX`, ≤ 21566 MiB, hash registrado; la imagen de laboratorio se conserva | T-0015, T-0019 | B (generador) / C (montajes) |
| **M5 iOS instalado y arrancando** (N3) | iOS llega a SpringBoard en esta unidad | Log persistente y fotos de esta unidad (L4); copia de Android decidida **antes** de borrar | — | C (borra Android) |
| **M6 DROP v2 en el dispositivo** (N4) | El protocolo con cortes reales | Autoprueba a y b con verificación en el teléfono (L3) | — | C |
| **M7 S7GE: GPU en iOS** | Fases 0-4 de S7GE en esta unidad, luego recursos, compilador, Metal, composición | Pruebas de píxeles en esta unidad (L3), ABI revisado, brecha de seguridad de `Submit` cerrada | T-0008, T-0009, T-0010, T-0011, T-0016 | A / B / C |
| **M8 Registro en vivo y red por USB** | Dejar de volver a TWRP en cada prueba | Plan de `docs/herolte-usb-plan.md` con sonda en el teléfono (L3) | — | C |
| **M9 Periféricos restantes** | Bluetooth, códec de audio, sensores, reposo | Una prueba en el teléfono por función | — | A / C |

## Dependencias críticas
```
T-0001 (gobierno) ─► T-0017 (publicar)                      T-0013 (cargador) ─► T-0012 (N1/N2 en el S7)
T-0002 (Unicode, hecha) ─► T-0003 (decidir) ─┐
T-0005 (rev2 ronda 2) ─► T-0006 (revisión) ─► T-0004 (R2) ─┴─► T-0015 (root verificable)
T-0009 (integración origin/herolte) ─► T-0016 (renumerar/fusionar) ─► T-0018 (validate-repo)
```
Nada de M3 en adelante empieza sin una decisión `APPROVED` del director que nombre la acción, la imagen (con hash) y las copias de seguridad previas.

## Riesgos de calendario conocidos
- **Divergencia con upstream:** `origin/herolte` avanza (13 commits el 2026-11-13) y ya usa números de parche que nosotros usamos; cuanto más se espere, más caro será reconciliar (T-0009).
- **Evidencia volátil:** la imagen de laboratorio vive en `/tmp` (T-0019).
- **Disco:** `/` quedó a 0 bytes; hoy hay margen (≈15 GB), pero los 24 GiB de sandboxes originales siguen en `/` (T-0007).

# Ciclo grande n.º 2 (kernel 0428/0429 + audio + medidas), 16-nov

Se compila y se prueba UNA vez. Vuelta atrás: min37 (ya medida, `7db96c99…`). Imagen prevista: `min40` (min38* y min39* son de otra sesión).

| # | Cambio | Dónde | Marca en el log | Si falla |
|---|---|---|---|---|
| 1 | `herohalt`, `herogl`, `herosb`, `sweettop` por defecto | kernel 0428 | los mismos mensajes de siempre sin los argumentos | min37 |
| 2 | Línea de arranque 41 caracteres más corta (568) | imagen | — | min37 |
| 3 | `heroaudio=3`: `/dev/hakios-audio` antes de mediaserverd | línea de arranque | `HEROLTE AUDIO`/`hakios-audio` | quitar el argumento |
| 4 | plug-in de audio de HakiOS (`HakiosAudio.driver`) | paquete DROP 6 (`drop-audio-1`) | `hero-run: audio plug-in: drop zone 87232 bytes` y `put` | paquete sin `audio/` |
| 5 | Apagado real opcional: `herohalt=3` (PS_HOLD, valor leído 0x5300) | kernel 0429 | `HEROLTE: herohalt=3: power off` | `herohalt=1` |
| 6 | Medida de fluidez estable (log de min37c: 13,1 fps medios, SoC máx. 46 °C) frente a la nueva imagen | log | `A5XELTE FB: frames` | — |
Sin teléfono (verde): plan de aislamiento de HeroGPU (D-0015, T-0055), Mesa 26 con Panfrost (T-0037, requiere CI de `mesa-ios`).

**Serie de parches.** El HEAD actual lleva los parches de upstream 0339 (motor de vibración), 0340 (sonda MFC), 0341 (PWM) y 0343 (suelo de brillo). Los CI de HEAD (runs 43837870489, 43842546377) **fallaron** (0343 no aplica sin su 0342, que falta) y el informe del Director atribuye paradas del kernel (`os_refcnt zone_require_ro`) a haptics/MFC. El último CI correcto es el 43748654722 (commit 6fb22e7: serie con VGR0 y mis parches 0400-0427). **Propuesta:** mover 0339, 0340, 0341 y 0343 a `xnu/patches-pending/` (siguen en git) hasta revisarlos uno a uno, y dejar VGR0 (0335-0338; se activa solo con `herovgr=1`, y min38d con él fue lenta). Es un cambio de serie (amarillo): necesita la firma del Director.

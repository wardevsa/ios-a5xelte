# S7GE_POST_FLASH_ANALYSIS — cómo analizar el primer arranque (Fase 17, 2026-11-14)

**Procedimiento y herramienta preparados; nada se ha ejecutado en el teléfono.** **Corrección de un supuesto:** la directiva pedía un script "para extraer los logs del kernel después del arranque". **Con la línea de la variante mínima no existe ningún log que extraer**: `herolog=0` (no se escribe log persistente), `herodrop=0` (sin zona DROP), `ufsrw=0` (el UFS no se escribe) y no hay puerto serie ni USB de depuración en esta fase. **La única fuente es la pantalla.** Por eso la herramienta clasifica una **transcripción** escrita por una persona, no un log.

## 1. Flujo
1. Durante el intento: vídeo continuo de la pantalla (S7GE_MIN_BOOT_VALIDATION.md §4).
2. **Después**: transcribir **literalmente** las líneas que se lean (pausando el vídeo) a un fichero de texto **fuera de git** (`TRANSCRIPCION.txt`), una línea por línea de pantalla, con anotaciones libres de lo que ocurre ("reboot", "pantalla negra 60 s").
3. `python3 -I tools/herolte-boot-transcript-check.py TRANSCRIPCION.txt --min` → resultado **A-E**, las etapas reconocidas, los **prefijos prohibidos** que hayan aparecido y la última línea. Salida 0 solo si es **A**.
4. Contrastar con `S7GE_BOOT_LOG_EXPECTATIONS.md` y decidir (restaurar BOOT, fase 3, o analizar la última línea).
5. Registrar en `evidence.toml` como evidencia del dispositivo (`this-unit`), con el hash de la imagen probada, el resultado, y la transcripción **resumida** (no incluir datos personales).

## 2. Qué hace la herramienta (y qué no)
Reconoce las etapas por **texto** (`HEROLTE XNU LOADER`, `JUMP TO XNU`, `XNU ENTRY`, `XNU MMU ON`, `Darwin Kernel Version`, `cannot mount root`), los fallos del cargador (`ENTRY OUTSIDE KERNEL`, `BAD SWEETXNU PAYLOAD`, `PAYLOAD OVERLAPS XNU RAM`), un pánico, reinicios repetidos y una transcripción vacía, y avisa de los prefijos de hilos apagados (`HEROLTE WIFI/GPU/CPU/POWER/TMU/DROP`) con `--min`. Tiene 9 pruebas con texto sintético (`tools/test_boot_transcript.py`). **No** interpreta causas, **no** lee el teléfono y **depende de la transcripción**: una línea mal leída cambia el resultado. Un resultado A no prueba nada fuera de N2 (S7GE_MIN_BOOT_VALIDATION.md §3).

## 3. Preguntas que sí puede responder la transcripción (y las que no)
| Pregunta | ¿Responde? |
|---|---|
| ¿Arrancó el cargador, llegó a XNU, hasta qué etapa? | sí |
| ¿Cuántas CPUs ve XNU? ¿Leyó la GPT del UFS? | solo si esas líneas se leen y se transcriben |
| ¿Se aplicaron los boot-args de la variante mínima? | sí, por la **ausencia** de los prefijos prohibidos (y la línea `BOOTARGS` del cargador) |
| ¿Funciona la GPU / el Wi-Fi / la energía? | **no** (apagados) |
| ¿Qué pasó después de un pánico no visible? | no |

## 4. Para intentos posteriores (fases 3-4)
Cuando se active un subsistema (p. ej. `herogpu=1`) y exista alguna forma de log (serie/USB o `herolog=1` con `ufsrw=1`, que **cambia** la seguridad del intento y necesita su propia autorización), este documento se ampliará con un extractor de log real. Hoy sería inventar una fuente que no existe.

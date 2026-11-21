# Informe de aprendizaje: un sistema de gobierno para trabajar con autonomía sin perder el control

> *Informe retroactivo (D-0091), reconstruido a partir de `HEROLTE_PROGRESS.md`, el historial de Git y las evidencias de gobierno. Desde aquí el trabajo es del equipo de este repositorio.*

## 1. Qué hicimos y por qué
Con varias sesiones y modelos trabajando sobre un teléfono real, hacía falta que cada acción peligrosa estuviera autorizada, registrada y comprobable. Se creó una carpeta `governance/` con datos y una herramienta que valida las reglas.

## 2. El concepto
- **Decisión (D-):** una autorización o política con alcance exacto, fecha de vencimiento y aprobador. Las acciones peligrosas (escribir BOOT) exigen la aprobación **explícita del Director**, nunca inferida.
- **Evidencia (E-):** un hecho registrado e inmutable (un log, un hash, una observación) con nivel de confianza.
- **Tarea (T-)** y **relevo (H-):** el trabajo en curso y la transferencia entre sesiones, para que quien entre verifique en vez de creer.
- **Puerta (*gate*):** la herramienta `governance.py` que rechaza, antes de actuar, lo no permitido (*fail-closed*: ante la duda, bloquea).
- **Niveles de riesgo:** verde, naranja y rojo; lo rojo exige autorización firmada y de alcance limitado (p. ej. «escribir solo esta imagen, con este SHA-256, en BOOT, un intento»).

## 3. La evidencia (medido)
- D-0001 propone el sistema de gobierno; el Director lo aprobó el 2026-11-13. Una auditoría de la herramienta corrigió 17 hallazgos y dejó una política de autonomía aplicada por código (`gate`, `authorizes`, `review_ref`).
- D-0033: autorización roja de **un solo intento** para escribir la primera imagen N2 en BOOT, con su SHA-256 y tamaño. E-0049: BOOT escrito y leído de vuelta con hash coincidente; **EFS idéntico antes y después**.
- Hoy el repositorio lleva centenares de entradas (unas 290 evidencias y unas 90 decisiones a 18-nov) y 14 suites de regresión.
- Un error mío de proceso, que conste: registré una decisión como aprobada con frases del Director que no nombraban la acción. La puerta lo bloqueó; se rehízo pidiendo la aprobación explícita.

## 4. Cómo defenderlo
**Pregunta posible:** ¿Por qué tanto proceso para escribir una partición?
**Respuesta modelo:** Porque BOOT es lo único que, si se escribe mal, deja el teléfono sin arrancar, y un error con EFS no tiene arreglo. El proceso hace que cada escritura tenga alcance exacto, hash verificable y marcha atrás.

**Pregunta posible:** ¿Qué significa *fail-closed*?
**Respuesta modelo:** Que si la herramienta no puede demostrar que una acción está permitida, la rechaza, en vez de dejarla pasar.

**Pregunta posible:** ¿Por qué una aprobación debe nombrar la acción?
**Respuesta modelo:** Porque una frase general como «adelante» no define qué autoriza; el registro debe poder demostrar quién aprobó qué, sin que el asistente interprete a su favor.

## 5. Para profundizar
`governance/`, `tools/governance.py`, `governance/HANDOFF.md`, `AGENTS.md`.

# S7GE — el pánico de min10 (2026-11-14; observación del Director, transcrita en parte por ChatGPT; L2, E-0114)

## Lo que dice el pánico
`A5 XNU PANIC: Invalid kernel stack pointer (probably corruption). at pc 0xfffffff007378904, lr 0xfffffff007378844 (saved state: 0xfffffff008113cb0)`; FAR `0x9e`, ESR `0x96000005`, x1 `0x9e` (valores por IA a partir de fotos, sin verificar; las direcciones de la tabla de ChatGPT tienen un `f` de más).
**Simbolizado con el kernel que corría (CI 43615727583):** PC = `_vm_fault_internal + 0x24`; LR = `_vm_fault + 0x14`; el estado guardado está en `_excepstack + 0x3cb0`.

## Lectura (L1: código y números; ningún fallo del kernel es nuevo)
- **ESR `0x96000005`:** clase `0x25` = aborto de datos desde EL1; `DFSC 0x05` = fallo de traducción de nivel 1. **FAR `0x9e`** = dirección casi nula: es una desreferencia de **NULL + 0x9e** dentro de `vm_fault_internal` (el campo a 0x9e de la estructura que sale de `current_thread()`/`current_map()`, que aún no existe: `start.s` pone `TPIDR_EL1 = 0`).
- Es el **segundo fallo**. El primero (el que de verdad importa) entra en el manejador de abortos de datos del kernel, que llama a `vm_fault` sin hilo actual; ese fallo se produce al desreferenciar NULL y el sistema grita "Invalid kernel stack pointer" porque la pila de excepciones aún no pertenece a ningún hilo. **Por eso no vemos la dirección ni la causa del primer fallo.**
- **Dónde:** después de los cuatro `rb:` y del bloque 19, antes del bloque 20: exactamente en la **sonda de 0345** (la escritura de un píxel por el alias virtual). Es decir: **el acceso por el alias virtual provoca un aborto de datos**; el alias que mapeé en 0343/0344 no es válido en este momento (mismo fallo que en min9, que se veía como cuelgue porque el pánico se dibujaba por el propio alias).

## Correcciones al informe de ChatGPT
- "hemos conseguido arrancar el kernel en una ejecución posterior": **no consta**; no ha habido ninguna ejecución que pase del bloque 19.
- No hay corrupción de pila demostrada: el mensaje es genérico de esa fase.
- Las "líneas de investigación" (pila, mapeo de extra banks) apuntan a otro sitio: el fallo está en **mi parche de diagnóstico**, no en `arm_vm_init` del kernel.

## Siguiente (parche 0346)
No tocar el alias a ciegas: imprimir **TTBR1_EL1, TCR_EL1, `cpu_ttep`, el VA, la entrada L1 y la L2**, preguntar a la MMU con **`AT S1E1W`** y leer **PAR_EL1** (si falla, el código de fallo y el nivel), y solo escribir el píxel si la traducción existe; si no, detenerse con los números en pantalla. Con eso se ve por qué el alias no funciona (¿entrada L1 en otro índice? ¿VA fuera del rango de TTBR1? ¿atributos?).
**Pendiente real del bug original:** que el reinicio de min2-min7 tras apagar TTBR0 sigue sin diagnosticar; el alias es solo el medio para verlo.

# Informe de aprendizaje: por qué el S7 gasta ~500 mA con la pantalla apagada (min78 a min80)

Política D-0091. Fecha 2026-11-18. Evidencias: E-0293, E-0294, E-0295, E-0296.

## 1. Qué hicimos y por qué
Intentamos bajar el consumo con la pantalla apagada (iOS ~500 mA, el Linux de Samsung 25-35 mA en el mismo teléfono). Primero apagamos los núcleos ociosos (reposo profundo, PSCI) y no cambió nada; después medimos (min80) para saber **dónde** se gasta en lugar de seguir probando a ciegas.

## 2. El concepto
- **Reposo de núcleo (C-state por núcleo, aquí PSCI CPU_SUSPEND):** un núcleo ocioso se apaga solo él. Ahorra poco si ya estaba en `WFI` (espera con el reloj parado), porque un núcleo en WFI ya gasta casi solo fugas.
- **Reposo de clúster (CPD) y de sistema (SICD):** cuando *todos* los núcleos duermen, el sistema puede parar también relojes, buses y la memoria. Ahí está el ahorro grande: lo que rodea a los núcleos (memoria, interconexión, PLLs) gasta más que los núcleos parados.
- **idle-IP:** el PMU (controlador de energía) tiene cuatro palabras de 32 bits (`0x3e0..0x3ec`), un bit por bloque de hardware. Un bit a 1 significa «este bloque está ocioso». Otra palabra, la máscara (`0x3f0..0x3fc`), dice cuáles ignorar. El PMU solo deja entrar en SICD si todos los bits **no enmascarados** están ociosos.
- **Quién escribe esos bits:** en el código de Samsung (`exynos_update_ip_idle_status`, `exynos-powermode.c`) los escriben **los controladores por software**: cada driver avisa «estoy ocioso» al terminar su trabajo.

## 3. La evidencia (medido)
| Medida | Resultado |
|---|---|
| Reposo de núcleos: 0, 1 o 6 núcleos (min64, min71, min78, min79) | 536, 492, 497, 495 mA con pantalla apagada: casi igual |
| Residencia por núcleo, pantalla apagada (min80, último minuto) | cpu0 97,5 % ocioso; cpu1 97,2 %; el resto 98-99,9 % |
| Corriente con pantalla apagada en min80 (sin reposo profundo) | 505 mA de mediana (42 muestras) |
| `HEROLTE IDLEIP` (5 lecturas) | estado `00000000` x4, máscara `ffffffff` x4, siempre igual |

Lectura:
1. **Los núcleos no son el consumidor:** están ociosos casi todo el tiempo y aun así gastamos ~500 mA. Por eso apagarlos no cambió nada (esto es una conclusión medida).
2. **El PMU cree que no hay ningún bloque ocioso** (estado todo 0) y tiene **todas las máscaras en 1** (ignora todo): iOS no programa nada de esto. *Hipótesis, no medida:* como en Linux son los drivers quienes marcan «ocioso», aquí nadie lo hace, y el sistema no podría entrar en SICD aunque se lo pidiéramos.

## 4. Cómo defenderlo
**Pregunta posible:** «¿Por qué apagar los núcleos no redujo el consumo?»
**Respuesta modelo:** «Porque medimos que ya pasaban el 97-99 % del tiempo ociosos, y un núcleo ocioso en WFI consume muy poco. El consumo con pantalla apagada está en lo que rodea a los núcleos (memoria, relojes, interconexión), que solo se para con un reposo de sistema; para eso hace falta que el PMU vea los bloques como ociosos, y en nuestro iOS nadie se lo comunica.»

**Error mío, para que conste:** el parche 0443 borró por error el paso del PMU de 0441, y durante cinco pruebas (min73-min77) di explicaciones equivocadas (el temporizador y las señales «no despiertan») cuando lo que faltaba era una escritura. Lección: tras quitar código, comprobar con grep y reconstruir una imagen conocida buena antes de sumar cambios (E-0293).

## 5. Para profundizar
- `/tmp/herolte-work/ref/exynos-powermode.c` (copia del código de Samsung, ver `exynos_check_idle_ip_stat` y `is_sicd_available`).
- `/sys/power/sicd` y `/sys/power/blocking_cpd` en TWRP (leídos: sicd=1, cpd=0).
- Siguiente paso de diseño: saber qué bit es qué bloque (la propiedad `idle-ip` del DTB de Samsung) y probar escribir los bits de los bloques que **sí** estén ociosos; antes de eso, mirar qué consume más (memoria, G3D, radio).

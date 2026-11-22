# Informe de aprendizaje: apagar un clúster de CPU y por qué casi nos engañamos con una medida

Política D-0091. Fecha 2026-11-19. Evidencias: E-0297, E-0298, E-0299, E-0300, E-0301. Decisión de cupo: D-0092.

## 1. Qué hicimos y por qué
Tras ver que apagar núcleos sueltos no bajaba el consumo con la pantalla apagada (E-0295), probamos apagar **el clúster Mongoose entero** (CPD, el mecanismo de Samsung). Funcionó a la segunda (la primera se colgó), parecía ahorrar unos 42 mA... y una comparación mejor mostró que **no se puede afirmar** que ahorre nada. Este informe trata de cómo se llega a esa conclusión y de qué aprendimos sobre medir.

## 2. El concepto
- **CPD (Cluster Power Down):** apagar a la vez los núcleos de un clúster, su caché L2 y su lógica compartida. Exige tres cosas a la vez: todos los núcleos del clúster dormidos, el bit del PMU que habilita el apagado de clúster, y llamar al firmware con el **estado de suspensión de clúster** (`0x01000000`, no el `0x10000` de un núcleo suelto).
- **Variable de confusión:** algo que cambia entre dos pruebas y no es lo que quieres medir. Aquí, **cuánto tiempo llevaba encendido iOS** cuando apagamos la pantalla: justo tras arrancar hay tareas de fondo que gastan corriente.
- **Diseño A/B dentro de una misma prueba:** alternar la condición (CPD encendido/apagado cada 30 s) en el mismo arranque, para que lo demás (batería, temperatura, tareas) sea igual en las dos condiciones.
- **Intervalo de confianza por *bootstrap*:** remuestrear los datos miles de veces para ver cuánto puede variar una diferencia solo por azar. Si el intervalo incluye el cero, no se puede afirmar que haya efecto.
- **Error típico:** desviación entre muestras dividida por la raíz de cuántas hay; indica la precisión de una mediana.

## 3. La evidencia (medido)
| Prueba | Configuración | Corriente con pantalla apagada |
|---|---|---|
| min80 | sin reposo profundo | 505 mA (±4, n=41) |
| min82 | cuatro Mongoose dormidos, sin CPD | 502 mA (±9, n=30) |
| min83 | CPD siempre | 460 mA (±5, n=35), pero 2,5 fps |
| min84 | CPD solo con pantalla apagada | 491 mA (±16, n=18), 10,9 fps |
| **min85** | **A/B: CPD alterna cada 30 s** | **encendido 460 (±7, n=19) frente a apagado 471 (±10, n=23)** |

- Dentro del mismo arranque la diferencia es de **+11 mA con intervalo 95 % [−10, +32]**: incluye el cero, así que no hay ahorro demostrable por el CPD.
- Entre pruebas, la mediana baja cuanto más tarde se apaga la pantalla (505 mA a 205 s, 502 a 178 s, 491 a 208 s, 460 a 250 s, 466 a 328 s; r = −0,79 con solo 5 puntos).
- Hipótesis, **no demostrada**: la diferencia de min83 venía del tiempo transcurrido desde el arranque. Contra ella: las pendientes dentro de cada prueba no son coherentes (−5, +22, −14, −5, +13 mA/min).
- El CPD funciona de verdad (estado del PMU de la L2 `0x10050000` en lugar de `0x7`), y limitarlo a la pantalla apagada recupera la fluidez (de 2,5 a 10,9 fps). Lo que no demostramos es que ahorre.
- Un **error mío de proceso:** en las notas de min83 dije que ahorraba ~42 mA; lo corregí en E-0299 al ver el A/B.

## 4. Cómo defenderlo
**Pregunta posible:** ¿Por qué no basta con comparar la corriente de dos pruebas distintas?
**Respuesta modelo:** Porque entre dos pruebas cambian más cosas que la que quieres medir: cuánto llevaba encendido el sistema, la temperatura o las tareas de fondo. Por eso diseñamos un A/B dentro del mismo arranque, alternando la condición cada 30 segundos.

**Pregunta posible:** ¿Qué significa que el intervalo de confianza incluya el cero?
**Respuesta modelo:** Que con esos datos la diferencia observada podría deberse solo al azar de las muestras: aquí +11 mA con intervalo entre −10 y +32 mA, así que no podemos afirmar que el apagado de clúster ahorre corriente.

**Pregunta posible:** ¿Qué hacía falta para que el apagado de clúster funcionara y no colgara el sistema?
**Respuesta modelo:** Tres cosas a la vez: que los cuatro núcleos del clúster estén en la máscara de reposo, activar el bit de habilitación del PMU en el último núcleo en dormir, y llamar al firmware con el estado de suspensión de clúster (0x01000000), no el de núcleo suelto. Sin ese último detalle se colgaba el sistema.

**Pregunta posible:** ¿Qué decisión se toma ante un resultado negativo?
**Respuesta modelo:** Se registra como tal, se corrige lo anterior que lo contradice y se deja la función desactivada por defecto (el código se conserva) para buscar el consumo en otro sitio, en vez de mantener complejidad cuyo beneficio no se ha demostrado.

**Error mío, para que conste:** di por bueno un ahorro de 42 mA con una sola prueba por configuración y sin controlar el tiempo transcurrido desde el arranque. Lección: una diferencia entre pruebas separadas solo es una pista; hay que diseñar la comparación para que lo demás no cambie (E-0301).

## 5. Para profundizar
Parches `0451` a `0454`, `psci.c` de Samsung (`psci_suspend_customized_finisher`), evidencias E-0297 a E-0301 y `docs/aprendizaje/20261117-reposo-profundo-por-psci-y-el-error-0443.md`. Siguiente paso de ingeniería: buscar el consumo con la pantalla apagada en memoria, dominios de GPU y pantalla, y comparar con el estado que deja Linux en el mismo teléfono.

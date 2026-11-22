# Energía, rendimiento y temperatura a largo plazo: arquitectura (17-nov-2026)

Propuesta del ingeniero a pregunta del Director («que la batería no se drene tanto, el rendimiento sea bueno y no se caliente, a largo plazo»). Es un plan de ingeniería, no una decisión; nada de aquí autoriza escrituras. Las cifras marcadas «medido» salen de los logs de esta unidad; el resto son hipótesis a comprobar.

## 0. Dónde estamos (medido)
- Mongoose fijo a 2600 MHz / 1075 mV; los A53 «se dejan como están» (0330); GPU Mali fija a 650 MHz (`herogpu_mhz`). Sin tabla de frecuencias ni escalado por carga: `herocpu_mhz`/`herogpu_mhz` son interruptores, no una política. Único freno térmico: `herohot` (binario: o 2600 o 728 MHz; el valor por defecto era 80 C; en min51 ya está en 58 C).
- Consumo con la pantalla encendida en bloqueo: del orden de 1,4 A (lectura de −1466 mA), SoC 40-49 C (sensor más caliente 51 C). Un puerto USB de PC entrega 0,5 A (min54: cargador válido, fase de corriente constante, y aun así la batería baja).
- `timer coalescing off` y «CoreAnimation told 120 Hz»: el kernel despierta a los núcleos con más frecuencia de la necesaria. Sin estados de reposo profundos más allá de WFI (hipótesis: hay que verificar `cpu_idle` en el log).
- Wi-Fi sin ahorro de energía acordado con el AP (BCM4359 por PCIe con el firmware de Android), brillo y panel sin control propio.

## 1. Principio: un presupuesto de energía, no interruptores
Todo lo demás cuelga de un **gestor de presupuesto** (kernel) que reparte tres límites con la misma moneda (vatios): el que da la fuente (batería, puerto USB 2,5 W, cargador 10 W), el térmico (temperatura de piel ≈ 38-41 C) y el de la batería (corriente máxima sostenida). XNU ya tiene el hueco: la interfaz de rendimiento de CLPC (`cpu_perf_state`, `ml_processor_register` con `processor_up/down` y el control de clústeres P/E que iOS espera de AppleARMPMGR). Hoy esa interfaz no existe aquí; se implementaría como una **CLPC mínima propia** (`herolte_pm.c`): un hilo con política por clúster, sin la lógica propietaria de Apple.

## 2. Piezas (en orden de dependencia)
1. **Instrumentación primero.** No se optimiza lo que no se mide: corriente del medidor cada 1 s (hoy cada 30 s), potencia estimada por clúster con frecuencia×tensión, los 4 TMU del SoC y la temperatura de la batería (ya leída), contadores de cuadro (ya), y una prueba de consumo repetible (pantalla apagada, pantalla encendida en reposo, desplazamiento continuo). Cada cambio posterior se acepta con un número antes/después (mA y °C), registrado como evidencia.
2. **Tablas de operación (OPP) reales.** Para Mongoose, Cortex-A53 y Mali: pares frecuencia/tensión por ASV (los valores seguros de Samsung para el 8890 que se leen del propio teléfono: tablas ASV en la ROM de Android/DTB). Hoy sólo conocemos un punto que funciona (2600 MHz, 1075 mV, 650 MHz, `vdd_g3d 0x40`). Riesgo: un voltaje bajo → cuelgue o corrupción (como en el episodio del ADT, el fallo es silencioso y variado): se prueba con margen y estrés, nunca sin reversión.
3. **DVFS por carga.** Política tipo `schedutil`: utilización por clúster → siguiente OPP, subida rápida, bajada lenta (histéresis), con el mapa P/E de XNU (el planificador de clústeres ya distingue núcleos de rendimiento y de eficiencia por el ADT): lo ligero va a los A53 a baja frecuencia, lo pesado sube los Mongoose. La utilización ya la sabemos medir (`TOP`/`TOPMEM`).
4. **Reposo profundo.** Estados de reposo por núcleo y por clúster (apagado de núcleo por el PMU, `CPU_OFF`) y reposo de sistema con la pantalla apagada; con `timer coalescing` reactivado y temporizadores sin espera activa. Es lo que más afecta a la batería con el teléfono en el bolsillo (hoy sin medir; sospecho que es el mayor ahorro posible).
5. **GPU.** DVFS de la Mali por carga de cola (hoy fija), apagado del dominio `pd-g3d` entre cuadros cuando no hay trabajo, y un límite de cuadros por política (30 Hz en estático, 60 Hz sólo en movimiento). El escalado por VGR0 no compensó (min49: 4,2 fps): descartado salvo que se resuelva su espera de refresco.
6. **Pantalla.** Es **AMOLED** (S7): el negro no gasta; un tema oscuro y un fondo oscuro por defecto ahorran más que casi cualquier ajuste de CPU. Control de brillo con curva y sensor, y modo «siempre encendida» futuro con el estado de reposo del panel.
7. **Térmico.** Zonas con los TMU y la temperatura de la batería, un estimador de temperatura de piel, y un controlador escalonado/PID que baja el techo de OPP de GPU y CPU de forma gradual (no a 728 MHz de golpe). Límites: piel < 40 C en uso normal, parada dura del SoC a 85 C.
8. **Carga.** El cargador (MAX77854 a 0x69) se maneja por **tipo de fuente**: el MUIC (0x25) da BC1.2 (SDP/CDP/DCP/AFC); límite de entrada y corriente de carga se fijan según el tipo y se REBAJAN el presupuesto de CPU/GPU con 0,5 A. Hoy el icono ya sigue al cargador (0432); falta el control. Cada escritura al cargador: lectura previa, límites duros en el código (corriente de entrada máxima 1,5 A en este teléfono, tensión de fin de carga intacta), y la parada si la temperatura de la batería sube.
9. **Radios.** Ahorro de energía del Wi-Fi (PM1/PM2 del BCM4359, DTIM, ASPM L1.2 de PCIe), Bluetooth apagado, GPS apagado, y que `wifid` no despierte al sistema.
10. **Usuario.** Poda de demonios (`disabled.list`, ya hay 33), QoS: que las tareas de segundo plano (`dasd`, `duetexpertd`, `suggestd`: ya van a segundo plano por `hero-run`) no suban frecuencia.

## 3. Orden propuesto y primeras victorias baratas
Primero **medir** (1), después los **ahorros baratos que no tocan tensiones**: tema/fondo oscuro, `timer coalescing` activado, techo de CPU a un OPP intermedio (p. ej. 1976 MHz) y de GPU a 400-500 MHz como perfil seleccionable por argumento de arranque, frecuencia de cuadro adaptativa. Después DVFS (2-3) y reposo (4), que son lo difícil y lo que más rinde. Térmico y carga se escriben con la instrumentación ya funcionando.

## 4. Riesgos y reglas
- Tensiones/frecuencias: una a la vez, con imagen de vuelta atrás y prueba de estrés; nunca por encima de lo ya demostrado (2600 MHz/1075 mV, 650 MHz) sin datos de ASV.
- Cargador: sólo escribir tras leer y con límites duros en el código; la decisión de escribir al cargador es una acción roja separada que requiere la firma del Director.
- Mediciones: todo lo marcado «hipótesis» arriba se convierte en evidencia (E-xxxx) antes de diseñar sobre ello.
- Alcance realista: esto es el trabajo continuado de un controlador de energía completo; no cabe en una sesión. Lo medible y reversible va primero.

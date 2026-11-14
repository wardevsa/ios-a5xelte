# S7GE_MIN_BOOT_VALIDATION — qué comprobar en el primer arranque de la variante mínima (Fase 9, 2026-11-14)

**Plan de observación; nada se ha ejecutado en el teléfono.** Se aplica a `xnu-boot-v2-s7-min-20261114.img` (E-0040) si el Director autoriza la fase 1 de `docs/herolte-solicitud-n2.md`. Objetivo único: saber **si el cargador, el kernel y el ADT arrancan en esta unidad** (peldaño N2 de `estado-y-camino-a-flashear.md`). **No** es una prueba de iOS, de la GPU, del Wi-Fi, del root ni de DROP. Evidencia que genere: nivel **L3 de esta unidad** (`device = "this-unit"`), separada de las comprobaciones del PC.

## 1. Qué se puede observar (y qué no)
- Con `herolog=0`, `herodrop=0` y `ufsrw=0` **no se escribe ningún log persistente**: la única evidencia es **la pantalla** (foto o vídeo del Director). El texto de la consola es lo que hay.
- Sin `herogpu`, `heropower` ni `herowifi`: **no habrá** líneas `HEROLTE GPU/POWER/CPU/WIFI`; su ausencia es esperada, no un fallo.
- No hay puerto serie ni USB de depuración en esta fase (el plan USB es aparte: `docs/herolte-usb-plan.md`).

## 2. Secuencia esperada (según `docs/herolte-bringup.md`, Etapa 2; **no medida en esta unidad**)
1. Cargador `xnu_boot`: texto en pantalla `ENTRY` / `BOOTARGS` / `JUMP TO XNU`; si el cargador falla, muestra el motivo **30 s** y pide TWRP.
2. XNU: bloques de color (entrada, MMU, FP, tunables, `arm_init`) y el texto `XNU ENTRY` / `XNU MMU ON`.
3. Consola en C del kernel: banner, **8 CPUs** (`cpus=8`), lectura de la GPT del UFS.
4. Fallo esperado al montar la raíz (`rd=ufsroot0 ufsroot=USERDATA` y USERDATA es ext4): **eso cuenta como éxito de N2**, no es un error.

## 3. Criterios (los fija este plan *antes* de arrancar)
| Resultado | Cómo se ve | Veredicto |
|---|---|---|
| **A. N2 completo** | llega a la consola de C, informa 8 CPUs, lee el UFS y falla al montar la raíz (o se queda ahí) | **Éxito de N2**: hipótesis "XNU arranca en esta unidad" confirmada |
| **B. N2 parcial** | llega a `XNU MMU ON` o a parte de la consola y se para/panica | **Información útil**: anotar la última línea exacta; no es un fallo del procedimiento |
| **C. Cargador falla** | texto del cargador durante 30 s y vuelta a TWRP | anotar el motivo literal; el cargador y el ADT son lo sospechoso |
| **D. Pantalla negra / sin texto** | nada tras 60 s | no concluyente; anotar duración y qué pasa con las teclas; un solo intento no distingue "pantalla" de "no arranca" |
| **E. Bucle de reinicios** | reinicia solo | parar tras 3 ciclos; restaurar BOOT |
**Lo que no se debe concluir de A:** que iOS arranque, que la GPU funcione, que el Wi-Fi sea seguro, ni que la candidata normal sea segura (fase 3 necesita su propio permiso).

## 4. Protocolo del intento (propuesta; lo ejecuta el Director)
1. **Antes**: backup completo y recortado (KI-0008); en TWRP, leer `EFS` y `BOOT` y calcular su SHA-256 **en el teléfono** (lectura): deben coincidir con E-0036.
2. Escribir la imagen (solicitud §5) y **comprobar leyendo de vuelta** que los primeros 18 618 384 bytes dan el hash de la autorización.
3. Reiniciar el teléfono con una **cronología**: anotar el reloj al soltar los botones, tomar **vídeo continuo** de la pantalla (los textos pasan rápido) y observar **al menos 2 minutos** (`wdt=-1`: el kernel no tiene watchdog; un cuelgue exige reinicio forzado).
4. Reinicio forzado: Vol− + Power ~7 s; enseguida Vol+ + Home + Power para TWRP (no tocar S-Boot ni Download).
5. **Después**, en TWRP: leer `EFS` otra vez y comparar su hash con el de antes (no debe cambiar); decidir si se **restaura** `BOOT.img` (recomendado tras cada intento mientras no haya raíz) comprobando el hash.
6. Registrar: foto/vídeo (fuera de git), el resultado A-E, la última línea visible y las duraciones, en `evidence.toml` como **evidencia del dispositivo** con el hash de la imagen probada; **sin elevar niveles** de otras evidencias.

## 5. Qué se pregunta a la unidad con esto (y se queda sin responder)
| Pregunta | ¿La responde la fase 1? |
|---|---|
| ¿Arranca el cargador y llega a XNU? | **sí** |
| ¿Cuántas CPUs ve XNU? | **sí** (consola) |
| ¿Funciona la lectura del UFS? | **sí**, si lee la GPT |
| `AS_PRESENT`, GPU, Wi-Fi, energía | **no** (están apagados a propósito) |
| Fallos de lectura `0x42` con más de 1 GiB de RAM | **no** (sin GPU) |
Las respuestas sobre GPU llegan en fases posteriores, una imagen y una autorización por intento.

## 6. Riesgos conocidos y mitigación
Pantalla negra o reinicios: recuperable con las teclas y `BOOT.img` verificado (E-0036). Un fallo de escritura parcial de BOOT: comprobado con la lectura de vuelta y recuperable desde TWRP. Riesgo teórico de los pocos escritos de hardware que quedan (el hilo de bus/display puede tocar un mux de reloj; no leído a fondo): **no se ha observado**, y se acepta explícitamente al firmar.

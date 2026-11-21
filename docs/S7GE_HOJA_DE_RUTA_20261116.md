# Hoja de ruta: lo complejo que viene (16-nov-2026)

Propuesta del ingeniero, no una decisión. Cada línea sale de un fallo o límite medido; las estimaciones son de orden de magnitud, sin fechas. Nada de aquí autoriza ninguna acción roja.

## 0. Antes de nada: estabilidad y herramientas
- **Panic de turnstile en el kernel nuevo** (docs/S7GE_PANIC_TURNSTILE_20261116.md). Hasta saber su causa no se fusiona nada más al kernel.
- **Captura de panics**: los paneles no dejan texto en el anillo (un único volcado y el kernel cae antes del siguiente). Hacer que el manejador de panic escriba su texto y la pila en el anillo de USERDATA con un flush síncrono (UFS en modo polling, sin locks). Es la mejora que más tiempo ahorra a cada futuro fallo. Riesgo: tocar el camino de panic puede ocultar el panic original; hay que probarlo con un panic provocado desde `sysctl` de depuración.
- **CI más rápido**: variante `xnu-fast` con ccache (en medición). Siguiente: cachear los clones y las herramientas de host (bootstrap_cmds, dtrace, headers) y, si compensa, medir un runner arm64 de pago. Objetivo realista 8-10 min; 5 min exige además partir `build.sh` en fase de herramientas (cacheable por hash) y fase de kernel.
- **Banco de pruebas sin teléfono**: ejecutar en QEMU (docs/QEMU_TESTING.md) las partes que no dependen del SoC (VM, turnstiles, VFS) para cazar panics de la serie antes de gastar un arranque. Primera pieza: arrancar el kernel `HEROLTE` en QEMU virt con el mismo mkpayload y ver si llega a launchd.

## 1. Gráficos: de «GL por Mesa» a Metal (S7GE)
Hecho: Mali-T880 a 650 MHz, EAGL sobre Mesa/Panfrost, composición GL en backboardd, escalado por GPU (5 ms) o por VGR0.
Falta y por qué importa: CoreImage cae en un puntero nulo sin Metal (Mensajes, Safari al tocar una foto, Fotos), desenfoques y materiales de SpringBoard.
1. **Capa Metal mínima** (MTLDevice/CommandQueue/Texture/RenderPipeline/ComputePipeline) sobre una cola propia de HeroGPU. Primero lo que CoreImage pide en su camino de arranque, no Metal completo.
2. **Compilador de shaders**: AIR/metallib de Apple -> IR propio -> Midgard. El camino de Mesa 26 (Panfrost, T-0037) sirve de base para el backend Midgard y el ensamblador; el trabajo nuevo es el front-end AIR. Es la pieza más grande de todo el proyecto (meses).
3. **Aislamiento de clientes** (D-0015, T-0055): sin MMU por cliente cualquier proceso con acceso al nodo de GPU lee memoria de otros. Es un requisito de seguridad, no un adorno; antes de cualquier uso con aplicaciones no propias.
4. **Hilos y memoria de GPU**: el kernel de GPU hoy es de un solo cliente por diseño; planificar varias colas y su contabilidad en jetsam.

## 2. Rendimiento y memoria
- Lag (~13 fps): backboardd usa 128-146 % de un núcleo (36 % kernel). Palancas medibles: copias de superficie, número de pases de composición, frecuencia de CPU/GPU bajo carga, cuántos servicios sobran (disabled.list). Cada una con su experimento y la métrica TOP/TOPMEM, uno por imagen.
- Memoria (366 MB libres en el mejor caso): afinar el compresor y jetsam, ver qué demonios sobran en RAM (SpringBoard, mediaserverd), y decidir si merece activar el swap en USERDATA.
- Consumo y calor: 34-53 °C medidos; falta DVFS real con tablas de voltaje (hoy fijo a 2600 MHz/1075 mV) y apagado de núcleos con pantalla apagada.

## 3. Periféricos pendientes
| Periférico | Estado | Pieza difícil |
|---|---|---|
| Audio | `HakiosAudio` HAL + `heroaudio` en el kernel (min40, no probado por el panic) | codec y I2S del Exynos 8890, rutas de altavoz/auriculares |
| Wi-Fi | funciona (BCM4359, WPA2 en kernel) | COUNTRY_CODE/selector 383, canales (HW_SUPPORTED_CHANNELS error 6), WPA3/Enterprise, ahorro de energía |
| Bluetooth | desactivado (bluetoothd en heronoexec) | firmware del BCM4359 por UART/HCI |
| Cámara | nada | ISP de Exynos con firmware cerrado; probable que solo sea viable un modo reducido |
| Módem/SIM | nada | el CP de Samsung habla por protocolo RIL/IPC propio; sin él no hay llamadas ni datos |
| Sensores, háptico, huella | haptics en patches-pending (0339-0343) | revisar de uno en uno, atribución upstream |
| USB gadget | plan en docs/herolte-usb-plan.md | rndis/ncm para depurar sin TWRP |

## 4. Plataforma
- **Arranque autónomo**: hoy se escribe BOOT desde TWRP. Un arranque desde S-Boot sin recovery, con una entrada de menú para volver a Android/TWRP (sin tocar bootloaders).
- **Raíz iOS**: hoy en USERDATA sin cambiar la GPT. Medir la opción de una partición propia y la actualización incremental de la raíz (diff de volumen) en vez de reescribir imágenes enteras.
- **Seguridad**: `cs_enforcement_disable=1` y `launchd_unsecure_cache=1` siguen activos. Decidir qué parte de AMFI/código firmado se puede restaurar (Jefatura + Director; D-0015).
- **Actualizaciones**: flujo de paquetes DROP firmados por hash y generaciones (existe); falta un canal de recuperación si un paquete deja el userland inestable (hoy hay que volver a TWRP).

## 5. Gobierno y proceso
- Ratificaciones pendientes (D-0007, D-0009, D-0011..D-0013, D-0015) y revisión de Jefatura de la fusión (T-0054).
- Copia de seguridad en un segundo disco (D-0076, pospuesta). Sigue siendo el punto único de fallo más serio (EFS con IMEI).
- Una regla nueva que propongo: toda escritura de BOOT se hace con la imagen previa conocida-buena a un solo paso (ya existe) y con un **registro del texto del panic** como evidencia obligatoria cuando falle.

## Orden que propongo
1. Aislar el panic (en curso) y capturar panics.  2. CI rápido.  3. Audio probado.  4. Aislamiento de GPU (D-0015).  5. Capa Metal mínima para CoreImage.  6. Resto de periféricos por valor/dificultad.

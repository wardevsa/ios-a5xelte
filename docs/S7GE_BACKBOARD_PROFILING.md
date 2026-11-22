# Perfilado de backboardd y plan de fluidez (Carril A de la directiva de jefatura)

Datos: logs persistentes de `min33` (2.º arranque), `min33b` y `min34` (`~/HackiOS/builds/device-day/phase1-20261114/`, privados), líneas `TOP 5s` del kernel (`sweettop=1`) y muestras `SMP` del muestreador. Evidencia: E-0244, E-0248. Los plazos de la directiva no vinculan.

## 1. Quién gasta la CPU (media de 128 muestras de 5 s, `min33b` + `min34`, de 800 % posibles)
| Proceso | Media | Máx. | Nota |
|---|---|---|---|
| **backboardd** | **94 %** (146 % en `min34`) | 458 % | composición GL de CoreAnimation: el cuello |
| lsd | 40 % | 178 % | reconstrucción de LaunchServices tras borrar la base; baja a casi 0 en los arranques siguientes |
| launchd | 21 % | 200 % | picos al apagar |
| SpringBoard | 19 % | 371 % | |
| usermanagerd | 16 % | 69 % | |
| containermanager | 10 % | 67 % | |
| Preferences | 8 % | 79 % | solo con Ajustes abierto |
| kernel_task | 7 % | 27 % | |
| PosterBoard | 6 % | 182 % | fondos de pantalla |
| wifid | 5 % | 23 % | Wi-Fi apagado (herowifi=0) y el daemon sigue buscando |
| runningboardd | 5 % | 50 % | |
Total del sistema en `min34`: **302 % de 800 %** de media (máx. 1110 %). Es decir, hay CPU libre en media; el cuello es la latencia de `backboardd` (un proceso, pocos hilos activos a la vez).

## 2. Lo que el muestreador NO da todavía
El muestreador del kernel toma 1-3 muestras por arranque (intervalo por defecto ~90-120 s) y casi todos los hilos están dormidos en `mach_msg`; en 6 muestras solo 2 hilos de `backboardd`/`SpringBoard` estaban ejecutando. **No hay hotspots que reportar con rigor.** Además solo mapeamos a librería + offset (`tools/herolte-smp-images.py`); los ficheros de símbolos de la caché de dyld vienen comprimidos con un método de APFS que `7z` no lee (hace falta `ipsw` o una librería LZFSE).
Para perfilar de verdad: `sweetsample_s=2` (parche 0259; una muestra cada 2 s) durante 3-4 minutos de uso y agrupar los PC por librería. Hoy no cabe en la línea de arranque (605 de 607); el parche **0359** (`xnu/patches/0424-herolte-phone-defaults.patch`, sin CI aún) libera ~85 caracteres.

## 3. Experimentos propuestos (uno por imagen o en lotes con firma; cada BOOT lleva firma con SHA-256)
| # | Cambio | Qué se espera | Riesgo |
|---|---|---|---|
| E0 | 0359 (valores por defecto del teléfono) + `sweetsample_s=2` | Línea más corta y muestreo denso: primer perfil de `backboardd` por librería | bajo (los mismos valores) |
| E1 | `a5fb_hz=30` en vez de 60 | `backboardd` no intenta 60 Hz si el sistema da 11: menos trabajo desperdiciado | bajo |
| E2 | `heroquantum=500` | rodajas de CPU más cortas (parche 0286): menos latencia de la composición | bajo |
| E3 | `heronoexec += wifid,identityservicesd` | -5 % y picos de 32 % que no aportan sin red | bajo; Ajustes > Wi-Fi puede quedar vacío |
| E4 | `herocpu_mhz=2288` | comprobar si 2600 MHz aporta algo frente al calor (41-47 °C hoy) | bajo |
Orden recomendado: E0 primero (mide), luego E1-E3 de golpe en una sola imagen con rollback a `min34`, y E4 aparte. El objetivo de la directiva (20-25 fps) se mide con `A5XELTE FB: frames=… fps=…` (`tools/herolte-log-report.py`).

## 4. Qué dice esto de S7GE (Carril B)
La composición actual pasa por OpenGL ES sobre Mesa/Panfrost (OSMesa propio de upstream) con la Mali a 650 MHz; que `backboardd` tarde ~100 ms por cuadro es coherente con un camino GL traducido (`CA::OGL`) y no con un compositor Metal nativo. Cualquier mejora grande (>25 fps) viene de recortar trabajo por cuadro (menos capas, sombras `glsb3`, desenfoque) o del camino Metal. Hasta tener símbolos, no se puede decir más.

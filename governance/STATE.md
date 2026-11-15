# Estado actual de IOS S7

<!-- state-commit: 7a75c71 -->
**Verificado el 2026-11-15 sobre el commit `7a75c71`** (el estado se refresca en cada relevo; `check` avisa de la distancia).

## 1. En una frase
**iOS 16.7.16 arranca en el Galaxy S7 (SM-G930F) hasta la pantalla de inicio con táctil, CPU a 2600 MHz y GPU a 650 MHz** (BOOT `min31`, observación del Director y logs L2, E-0232); se ha instalado además el mecanismo DROP v2 (probado en el teléfono, E-0237) y, en el último paso escrito, `min33` con `herogl=1` más el paquete real 1 de userland (hero-run, Mesa/GL, `herosb`), **aún sin probar** (E-0241, E-0242).

## 2. Hechos medidos (con evidencia)
| Hecho | Evidencia | Nivel |
|---|---|---|
| Kernel (parches 0332-0355, CI) arranca, monta la raíz iOS en USERDATA (escrita con `herolte-write-userdata.py`, D-0048), `launchd` llega a `Early boot complete` y lanza `SpringBoard` y `backboardd` | E-0174, E-0187, E-0190 | L2 |
| El kernel anunciaba 1440x2560 mientras iOS pide 750x1334 (ADT iPhone 8): las superficies de pantalla quedaban a cero. Con `sweetfb_native=1 sweetfb_scale=1 sweetfb_lw=750 sweetfb_lh=1334` aparecen logo, pantalla de bloqueo, inicio y táctil | E-0217, E-0208, E-0209, `docs/S7GE_HITO_IOS_EN_PANTALLA.md` | L2 + observación |
| Reescalado por CPU: 88 ms por cuadro; con `sweetfb_gpu=1` (Mali) 5-6 ms; fps medios 2,8 -> 10-12 (máx. 27-46) | E-0220, E-0223, E-0226 | L2 |
| Relojes: Mongoose del bootloader ~242 MHz efectivos; con `herocpu_mhz=2600` (1075 mV) y `herogpu_mhz=650` (vdd_g3d 0x40) sin fallos; SoC 34-43 C con uso | E-0226, E-0230, E-0232 | L2 |
| DROP v2 en el teléfono: el kernel instaló el paquete de autoprueba y `verify_selftest.py` confirma ficheros, estado y token | E-0237 | L2 |
| Fallos de userland: `assetsd`/`PhotosFileProvider`/`fileproviderd` abortan (excepción sin capturar), Messages cae en CoreImage (puntero nulo, falta Metal), About crashea, Phone en blanco, fondo negro, «Sign in to your iPad» | E-0204, E-0220, E-0230, `docs/S7GE_USERLAND_FALLOS.md` | L2 / L0 |
| Memoria libre baja con el uso (477 -> 53-72 MB en minutos) | E-0220, E-0232, log min32 | L2 |
| Copias del teléfono (BOOT original E-0009, EFS, RECOVERY, SYSTEM, USERDATA Android) verificadas; USERDATA Android BORRADO por la escritura de la raíz iOS (D-0048) | E-0123, E-0124, E-0125 | L2 |
| Gobierno: decisiones D-0001..D-0071, evidencias hasta E-0242; cada escritura de BOOT/USERDATA lleva firma con SHA-256 del Director | `DECISIONS.md`, `EVIDENCE.md` | L2 |

## 3. Hipótesis (no demostradas)
- `herogl=1` + librerías Mesa/EAGL del paquete real darán composición por GPU, fondo y más fluidez (configuración de upstream, L4h; nunca vista en esta unidad).
- Los fallos de Fotos son una biblioteca de fotos sin crear en el primer arranque (no se ha visto el texto de la excepción).
- «iPad» viene de un dato de MobileGestalt (el ADT dice iPhone10,3 / iPhone X).
- El cierre ordenado a los ~7 min en `min27` lo provocó Vol- + Power del Director (no probado).

## 4. Git
| Árbol | Rama | Estado |
|---|---|---|
| `~/HackiOS/repos/wardevsa-ios-a5xelte-v2` (**worktree del ingeniero**) | `herolte-drop-v2` | publicada en `mio` hasta `0ad027b` (D-0069); commits locales posteriores solo de gobierno/herramientas |
| `~/HackiOS/repos/wardevsa-ios-a5xelte` (árbol principal **del responsable**) | `herolte-drop-fixes` | no tocar |
Remotos: `origin` = upstream (**sin push**), `mio` = fork del responsable (solo `herolte-drop-v2`).

## 5. Bloqueos abiertos (qué los desbloquea)
| Bloqueo | Quién | Siguiente paso |
|---|---|---|
| Probar `min33` + paquete real 1 (hay que arrancar y volver a TWRP para leer el log) | Director + Ingeniero | T-0012 |
| Metal / S7GE (Messages, desenfoques, fondos de iOS) | Ingeniero (largo plazo) | tras estabilizar userland |
| Excepción de `assetsd` sin texto; Wi-Fi/audio apagados a propósito | Ingeniero | tras ver `hero-run` en el log |
| Ratificaciones pendientes (D-0007, D-0009, D-0011..D-0013, D-0015) | Jefatura técnica / Director | tareas T-0014.. |

## 6. Riesgos
1. `min33`: si `backboardd` falla con `herogl=1` la pantalla puede quedar negra; vuelta atrás `min32` por BOOT (firma). Los ficheros de hero-run quedan en `/private/var/herolte` aunque se vacíe la zona.
2. Punto único de fallo de las copias (un solo disco; EFS contiene el IMEI); el hash de EFS impreso cambia entre sesiones (el teléfono lo modifica; comprobación antes/después en cada escritura).
3. TWRP a veces vuelve sin `adb` tras un reinicio forzado (desenchufar y enchufar); no usar Vol- + Power en iOS.
4. **Brecha de seguridad de la GPU** (`S7GE_ABI.md`) y `cs_enforcement_disable=1`: no ejecutar software no confiable.
5. Volatilidad del scratchpad (`/tmp`); los artefactos viven en `~/HackiOS/builds/device-day/` y el disco de trabajo.

## 7. Verificación de esta línea base (2026-11-15)
`governance check` sin errores; imágenes verificadas con `herolte-verify-boot.py` (58 PASS min33); cada escritura leída de vuelta (E-0211 … E-0242).

## 8. Dónde mirar
`HANDOFF.md` (empezar aquí) · `EVIDENCE.md` · `DECISIONS.md` · `docs/S7GE_HITO_IOS_EN_PANTALLA.md` · `docs/S7GE_USERLAND_FALLOS.md` · `docs/S7GE_BACKBOARDD_WAIT.md` · `docs/herolte-howto.md` §5 (DROP) · `tools/herolte-log-report.py` (resumen de un log)

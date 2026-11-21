# Actualización grande n.º 1 (min37 + paquete DROP 4): 13 cambios de una vez

Pedida por el Director («una update enorme, más de 10 cosas de golpe, si falla ya investigaremos»). Base buena de vuelta atrás: **min36** (`7c8363c5…`) y el paquete DROP 3. Cada cambio deja su marca en el log para saber cuál falla.

| # | Cambio | Dónde | Qué debería verse | Si falla |
|---|---|---|---|---|
| 1 | `a5fb_hz=30` en vez de 60 | línea de arranque (BOOT) | `A5XELTE FB: requested 30 Hz`; menos trabajo desperdiciado | volver a min36 |
| 2 | `heroquantum=500` | BOOT | rodajas de CPU más cortas (0286) | min36 |
| 3 | bloquear `identityservicesd` | `heronoexec` (BOOT) | `SPAWN FAILED … identityservicesd` | min36 |
| 4 | bloquear `parsecd` | `heronoexec` | idem | min36 |
| 5 | bloquear `mediaanalysisd` | `heronoexec` | idem | min36 |
| 6 | bloquear `photoanalysisd` | `heronoexec` | idem | min36 |
| 7 | bloquear `wifip2pd` (29 relanzamientos en min36) | `heronoexec` | desaparecen los `exec wifip2pd` | min36 |
| 8 | tabla de memoria cada 30 s | parche 0361 (kernel) | líneas `TOPMEM 30s: …` | solo logging |
| 9 | Wi-Fi: acepta el `COUNTRY_CODE` | parche 0362 (kernel) | `sets 51 … accepted` en vez de `REFUSED` | min36 |
| 10 | Wi-Fi: acepta el selector 383 | parche 0362 | `sets 383 … accepted` | min36 |
| 11 | hero-run nuevo: `files.remove` (solo `wallpaper.off`, `gestures.off`, `fps.off`) | CI `mesa-ios` + paquete (`autorun`) | `hero-run: files.remove: wallpaper.off taken out (0)` | paquete 5 con el hero-run anterior |
| 12 | fondo de pantalla propio (PNG degradado 750x1334) y reactivación de `herosb` | paquete: `wallpaper.png` + `files.remove` | `herosb: picture in …` en la 2.ª arrancada | borrar `wallpaper.png`/volver a poner `wallpaper.off` |
| 13 | app de ejemplo de código abierto (`HeroReddit`, arm64 sin cifrar) | paquete: `app=HeroReddit.app` | `hero-run: app HeroReddit.app: put in /Applications` e icono | `apps.remove` |

Más que ya incluye el kernel 0360: tiempo de sistema por proceso en las líneas TOP.

**No incluidos a propósito:** nada de Metal/S7GE; nada que cambie el pipeline de la GPU; ni cambios de frecuencia. No se bloquea `wifid` (el Wi-Fi funciona).
**Dos arranques:** el fondo se activa del todo en el **segundo** arranque (hero-run borra `wallpaper.off` mientras SpringBoard ya miró si existe). Se lo digo al Director.
**Lo que se escribe en el teléfono (cada uno con firma y hash):** BOOT min37 y la zona DROP (paquete 4, generación 4). Ninguna otra partición.

# S7GE — candidata min4 (2026-11-14, construida y verificada en el PC; NO escrita)

## 1. Qué es
`xnu-boot-v2-s7-min4-20261114.img`, SHA-256 `8e8725f3fbe42c830daa34d88796d479ece1ff5e33e64269ecd63cf070b980b4`, 18 618 384 B (E-0050). Respecto a min2 cambia **solo el kernel**: el del CI 43594581291 (rama `herolte-drop-v2` en `0900772`, kernel `af7b8760…954a7a`) con el parche `0338`. ADT original de 2 GiB (`dc817436…`, copiado, no redimensionado) y línea de arranque **idéntica** a min2 (`cmdline.txt` igual). Se vuelve al ADT de min2 porque min3 (1536 MiB) no cambió el síntoma.
Verificación: 47 PASS (constructor) y 57 PASS (independiente), 0 FAIL; `ci_check.py`: `0403-herolte-min4-diagnostic-marks: APLICADO`.

## 2. Qué añade el parche 0338 (solo dibuja, sin cambiar lógica)
| Dónde | Qué | Cómo se ve |
|---|---|---|
| `start.s`, tras `cbnz x21` | bloque naranja en x=240, **y=312** | persistente salvo que el texto de C lo pise |
| `start.s`, tras calcular `boot_args` | bloque naranja claro, **y=344** | ídem |
| `arm_init.c` | `A5 XNU STAGE 6: 6a processor_bootstrap done` / `6b maxmem and hygiene done` / `6c boot-args parsed, PAN set` | texto fugaz |
Los cinco bloques originales siguen (verde 88, azul 120, cian 152, magenta 184, amarillo 216, este último se dibuja **después** de los naranjas).

## 3. Cómo leerla
Usar `S7GE_MIN4_OBSERVATION_TEMPLATE.md` (checklist y tabla de interpretación) con `S7GE_STARTS_ANALYSIS.md` §3: el texto de C, si se imprime, **borra** parte del magenta, el amarillo y los naranjas (están en sus filas), de modo que "ver texto" y "ver esos bloques" son excluyentes en esa zona. Si tras min4 no queda claro, la siguiente es min5 (`S7GE_MIN5_DESIGN.md`, parche `0339`, bloques en x=1300 que el texto no puede pisar): **no está construida**.

## 4. Riesgo
Solo cambia el kernel por dibujos; el riesgo nuevo es una regresión del parche (menos bloques que en min2: restaurar BOOT). Mismo ADT y argumentos que min2, que ya se escribió y se restauró sin problemas en el flujo.

# S7GE — candidata min3 (2026-11-14, construida y verificada en el PC; NO escrita)

## 1. Qué es
`xnu-boot-v2-s7-min3-20261114.img`, SHA-256 `c70d3dd8151b891a93a42e0c703ff525b288a6c9c105966e757263a29313e36f`, 18 618 384 B (E-0048).
**Cambia una sola cosa respecto a min2:** el ADT. `chosen/dram-size` y el tamaño del primer banco de `hakios-ram-banks` pasan de `0x80000000` (2 GiB) a `0x60000000` (1 536 MiB); **solo difieren 2 bytes** del ADT (`tools/herolte-adt-resize-boot-bank.py`, con prueba de ida y vuelta de la serialización). Kernel (`62ea7501…`), cargador (`0a68abbd…`), BOOT de referencia y línea de arranque (`cmdline.txt` idéntico al de min2) **no cambian**.
Verificación en el PC: 47 PASS (constructor) y 57 PASS (independiente, con `--expect-arg` de los 9 argumentos), 0 FAIL. Rebuild exacto del payload incluido.

## 2. Por qué 1 536 MiB (evidencia y sus límites)
- `HEROLTE_PROGRESS.md` (2026-10-23/24, **teléfono del upstream**) y la ayuda de `mkadt_herolte.py`: *"1536 boots (with vm_compression_limit=98304), 2048 panics in write_pte_fast"*. Es la configuración que el upstream usó como estable. Nivel L4h ajeno, no medido aquí.
- **Matiz que la jefatura no recogió:** el upstream llegó después (2026-11-07, parches 0326-0329) a ~3 GiB con **2 GiB + bancos extra**, y nuestro ADT ya tiene esos bancos. Es decir, **min2 ya se parecía a esa configuración posterior**, así que 1 536 MiB no es una corrección demostrada, sino una **apuesta razonable y barata** (una variable) que acerca el ADT a la configuración más antigua conocida como estable. Se conservan los bancos extra a propósito, para cambiar solo una cosa; **mezcla 1 536 MiB + bancos extra que nadie ha probado**.

## 3. Correcciones a la lectura de la jefatura sobre el texto fugaz
La transcripción del Director dice `RS XNU STAGE 1…6`. En el código (`0010`/`0090`) el texto es **`A5 XNU STAGE n: …`** (el "RS" es lectura de "A5") y las etiquetas reales son: 1 `arm_init entered (MMU on)`, 2 `PE_init_platform done`, 3 `ml_parse_cpu_topology done`, 4 `cpu_bootstrap done`, 5 `kernel_startup_bootstrap done`, 6 **`cpu_init done`**, 7 **`entering arm_vm_init`** (no "arm_limit"/"cpu_limit").
- **Lo que sí demuestra** (si el texto es de min2): el kernel entró en C y llegó a la marca 6. Eso apoya mi hipótesis H1 (cuelgue en C), con lo que **queda superada** la parte de §6.1 que dejaba abierta H3.
- **Lo que NO demuestra:** que la causa sea `kmem_range_init`. **`kmem_range_init` va después de la marca 7** (`arm_vm_init` y luego el arranque de `kernel_startup`); si el texto termina en la 6, el punto de parada está **entre `cpu_init` y `arm_vm_init`** (`processor_bootstrap`, `maxmem`, PAN…), **antes** de donde `vm_compression_limit` o la RAM influyen. Con **min1** el vídeo mostró el panic en `kmem_range_init` (E-0033), es decir, min1 **superó** la marca 7: si la transcripción procede del primer arranque, no describe el cuelgue de min2.
- **Falta saber** de qué arranque (min1 o min2) es el texto, y si hubo una línea `STAGE 7` que no se leyó. El texto es de lectura rápida de una persona, sin vídeo archivado: **L2, no sube**.
**Consecuencia:** si el cuelgue de min2 está realmente antes de la marca 7, **min3 no lo arreglará** (cambia la RAM, que aún no se ha usado en ese tramo). Es un riesgo conocido de la apuesta, no un fallo de la imagen.

## 4. Qué cabe esperar
| Resultado | Lectura |
|---|---|
| Aparece `STAGE 7` y más texto, o un panic con consola | la RAM de 2 GiB era el obstáculo (escenario A/C de la jefatura) |
| Mismo cuelgue con las mismas marcas hasta la 6 | la RAM no es la causa; siguiente: marcas nuevas entre 6 y 7 (opción R: kernel nuevo, CI) |
| Menos marcas que en min2 | regresión del ADT: restaurar BOOT |
Para leerlo hace falta **cámara lenta del arranque** (≥ 120 fps si es posible, de cerca) y el texto literal.

## 5. Lo que NO se ha hecho
No se ha escrito nada en el teléfono ni se ha leído. D-0034 cubre min2 y la restauración, **no min3**: escribir min3 exige una decisión del Director que nombre esta imagen y este hash (texto en `docs/S7GE_FLASH_PROCEDURE.md`; partición por nombre `/dev/block/platform/155a0000.ufs/by-name/BOOT`, no `sda5`).

# S7GE_FIRST_BOOT_ANALYSIS — primer arranque de XNU en el S7 (variante mínima 1), 2026-11-14

**Proveniencia (importante).** **No he visto el vídeo.** Lo que sigue parte de una **transcripción de terceros**: Gemini transcribió los vídeos del Director y la jefatura (Qwen) la resumió; yo recibí el resumen. La transcripción puede tener errores de lectura (ya hay uno claro, §2). **Para confirmar hace falta mirar los fotogramas** (§5). Nivel de evidencia: observación de dispositivo de segunda mano → **L2**, sin elevar nada.

## 1. Qué se observó (según la transcripción)
```
HEROLTE XNU LOADER
COPYING KERNEL
RAM BASE 0000000080000000
panic(cpu 0 caller 0xffffff8007a8f9a4): kext_range_init: vm_map_locate_space failing for c7f72538b8 at 0xffffff7f126d6488 @vm_kern.c:357
handshake structure not initialized
```
Clasificador (`tools/herolte-boot-transcript-check.py --min`): **B** (N2 parcial). Pantalla con texto, bucle de fallo (Gemini). Qué **sí** demuestra: el cargador arranca, copia el kernel y salta; **XNU ejecuta código en esta unidad hasta su inicialización de memoria virtual y entra en `panic` con texto legible** (con símbolos: `keepsyms=1`). Qué **no**: nada más.

## 2. Qué dice realmente el panic (corrige las lecturas anteriores)
- **No es `kext_range_init` ni tiene que ver con kexts.** El kernel del CI contiene la cadena `kmem_range_init: vm_map_locate_space failing for claim %s size %#llx at %#llx @%s:%d` (medido con `strings` en el binario del CI): la transcripción dice `kext_range_init … failing for c7f72538b8 at 0x…` y **omite `claim <nombre> size 0x…`** → es una **lectura defectuosa** de esa misma línea. `kmem_range_init` (`osfmk/vm/vm_kern.c`, `STARTUP_RANK_THIRD`) **reserva rangos de dirección virtual del mapa del kernel** ("claims") para los asignadores del kernel (zonas, rangos de datos/punteros). Falla cuando **el total de lo reclamado no cabe en el espacio virtual libre**, que depende de la **memoria física declarada** (`sane_size`).
- **`handshake structure not initialized` NO es la causa**: es un mensaje del **volcado de memoria** (`osfmk/kdp/output_stages/out_shmem.c`, `kern_coredump_log`): el panic intenta escribir un core dump y no tiene configurado el destino. Es una **consecuencia** del panic.
- **"El panic de `panic.apple.com` es normal"**: sí, es el texto estándar de XNU; Gemini lo trató como una "incongruencia" sin serlo.
- La suposición de la jefatura (ADT "con otra topología") **no es lo que dice el código**; la causa más probable está **documentada por el propio proyecto** (§3).

## 3. Causa más probable (**hipótesis fuerte, no probada**)
Notas del proyecto (`HEROLTE_PROGRESS.md`, 2026-10-23/24, **teléfono del upstream**): *"Con 2 GiB el kernel ve la memoria pero entra en pánico en `kmem_range_init` (no entran sus rangos virtuales). … El log de `kmem` mostró por qué 2 GiB no entraba: el kernel (configuración macOS) reserva un **compresor de 16 × RAM**; **`vm_compression_limit` lo limita**."* Configuración que arrancaba: `vm_compression_limit=98304` (y `vm_compressor=2` en la línea de uso diario de `herolte-howto.md`).
**Lo que medí de nuestra candidata:**
- El ADT que enviamos (`embedded.adt`, `dc817436…`) declara **`dram-base 0x880000000`, `dram-size 0x80000000` = 2 GiB** del segundo banco (leído del propio fichero). Es justo el caso de las notas.
- La línea de arranque de N2 **no lleva `vm_compression_limit` ni `vm_compressor`** (ni la de la candidata normal).
→ Es decir: **reproduce la configuración que el upstream ya documentó como pánico en `kmem_range_init`**, no un fallo nuevo de este silicio. El kernel además imprime `HEROLTE KMEM: kernel_map … largest_free … claims … mem …` y una línea `HEROLTE KMEM: claim <nombre> <tamaño>` **antes** de entrar en el panic (parche del upstream para depurar exactamente esto): **esas líneas deberían estar en el vídeo** y confirmarían o desmentirían la hipótesis.
**Mi error de proceso** (a corregir, no de la jefatura): preparé N2 con el verificador (`herolte-verify-boot.py`), que comprueba la **estructura** de la imagen y los argumentos de **solo lectura**, pero **no** compara la línea de arranque ni el ADT con la configuración que ya se sabía que arrancaba. Debí comparar con `herolte-howto.md`/`HEROLTE_PROGRESS.md` antes de pedir la autorización. Queda como **KI-0009** y como punto de la lista previa.

## 4. Lo que corrige esto respecto al informe de la jefatura
| Afirmación | Realidad |
|---|---|
| "intenta cargar una extensión del kernel (kext)" | **No**: reserva VA del mapa del kernel (`kmem`) |
| "`handshake` = estructura de traspaso cargador→kernel" | **No**: es el volcado de core del panic |
| "el ADT no coincide con la topología" | el ADT **sí** describe un banco de 2 GiB; el problema es **cuánto reserva el kernel** para ese tamaño sin `vm_compression_limit` |
| "es como A5XELTE al principio" | no consta; **herolte** ya tiene esta lección documentada |
| "los 86 parches Mali no rompen el arranque; la T880 no tiene comportamiento eléctrico distinto" | **no se ha probado**: `herogpu=0` apaga la GPU en esta variante; el panic ocurre **antes** de cualquier acceso a la GPU |
| "hito histórico, éxito rotundo" | **hito real y acotado**: el cargador y el kernel **ejecutan** en esta unidad hasta `kmem_range_init`; el kernel **no completó el arranque** |

## 5. Para confirmar, mirar el vídeo (fotogramas, antes del panic)
1. Las líneas **`HEROLTE KMEM: kernel_map 0x… largest_free 0x… claims 0x… (N) mem 0x…`** y **`HEROLTE KMEM: claim <nombre> 0x…`** (los tamaños de los claims y `mem`). Si `mem` = `0x80000000` y hay un claim enorme (compresor), la hipótesis queda confirmada.
2. El texto **completo** del panic (nombre del claim, tamaño, dirección) y el número de línea (`@vm_kern.c:36xx`; la transcripción dice `357`, que no coincide con la fuente: probablemente un dígito perdido).
3. Si hay más líneas **anteriores** al panic (`XNU ENTRY`, `MMU ON`, etc.).

## 6. Siguiente intento propuesto (sin ejecutar; requiere NUEVA autorización)
**Candidata `xnu-boot-v2-s7-min2-20261114.img`** (ya construida y verificada en el PC, E-0045): la **misma** que la escrita, **solo añadiendo** `vm_compression_limit=98304 vm_compressor=2`; SHA-256 `595316aae927b3e7c960301790fa34557e5a296073a29df62522b67050edae21`, 18 618 384 B, 47 PASS (constructor) y 56 PASS (independiente), 0 FAIL. Cambia **una variable** (la del upstream) y mantiene todo lo demás. **D-0033 solo cubre la imagen anterior**: escribir esta exige otra decisión del Director con su hash. Si también panica, **el vídeo (`HEROLTE KMEM`) dirá cuánto reservar** y el siguiente paso sería un ADT con 1 536 MiB (la configuración que el upstream ya usaba: `--bank2-mb 1536`) o con los bancos extra (`herolte-adt-ram-banks.py`).
**Mientras tanto el teléfono** tiene escrita la imagen que da panic; si el Director quiere usar Android, hay que **restaurar BOOT** (cubierto por D-0033, `S7GE_FLASH_PROCEDURE.md` §4).

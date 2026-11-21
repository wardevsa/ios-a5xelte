# Informe de aprendizaje: llegar a unos 3 GiB de RAM con bancos dispersos

> *Informe retroactivo (D-0091), reconstruido a partir de `HEROLTE_PROGRESS.md` y del historial de Git. Este trabajo de octubre y principios de noviembre lo hizo el proyecto upstream y es la base heredada; las medidas son las que ese registro anota.*

## 1. Qué hicimos y por qué
La RAM utilizable pasó de 1,5 GiB a **3058 MiB** añadiendo bancos de memoria que están *debajo* del banco de arranque. Eso rompió cuatro suposiciones del kernel y hubo que arreglarlas una a una.

## 2. El concepto
- **Banco de memoria:** un rango contiguo de direcciones físicas. En el S7 hay varios y no empiezan en la dirección más baja.
- **`gPhysBase`:** el XNU de iOS supone que toda la memoria está por encima de su base física; con un banco por debajo, `pa - gPhysBase` sale **negativo**.
- **Tabla de páginas y granularidad:** con páginas de 16 KiB sobre un shim que mapea de 4 KiB, las sub-tablas deben juntarse; si la dirección virtual no es congruente con la física, no.
- **`kprintf` temprano:** el UART no está mapeado hasta `serial_init`; imprimir antes **cuelga sin mensaje**.
- **Zonas reservadas de S-Boot:** vienen en la línea de Linux, no en el DTB; si XNU las ignora, las pisa.

## 3. La evidencia (medido)
Cuatro arreglos propios sobre un port de Scion (S9):
1. Sin `kprintf` dentro de `arm_vm_init`: antes, cuelgue mudo en la etapa 7.
2. `pmap_object` indexado por página, no por `pa - gPhysBase`: antes, `vm_page_insert_internal ... past object bounds`.
3. Excluir `ess_setup=0x91200000`, `sec_tima_log=0x200000@0x92e02000`, `sec_avc_log` y `auto_summary_log` (de `/proc/cmdline` en TWRP).
4. VA de cada banco congruente con su PA (`ARM64_GRANULE_ALLOW_BLOCK`); antes, el assert `tt_entry_free` de `pmap_destroy`.
Resultado: 3058 MiB, «va de 10» según el registro. Un problema derivado: las superficies de iOS caen en el banco 2 y el IDMA de pantalla es de 32 bits, así que no se pueden mostrar directamente.

## 4. Cómo defenderlo
**Pregunta posible:** ¿Por qué un banco de RAM por debajo de la base rompe el kernel?
**Respuesta modelo:** Porque XNU calcula índices con `pa - gPhysBase`; con un banco inferior sale un valor negativo y las comprobaciones de rango de los objetos de VM fallan.

**Pregunta posible:** ¿Por qué un `kprintf` podía colgar sin mensaje?
**Respuesta modelo:** Porque el UART se mapea en `serial_init`, más tarde que `arm_vm_init`; escribir antes accede a una dirección sin mapear y no hay consola para decirlo.

**Pregunta posible:** ¿Qué papel tuvo `/proc/cmdline` de TWRP?
**Respuesta modelo:** S-Boot reserva zonas (logs de seguridad) que anuncia solo en la línea de Linux; leerla con TWRP indicó qué direcciones no debía tocar XNU.

## 5. Para profundizar
Parches `0326`-`0329`, `tools/herolte-adt-ram-banks.py`, `osfmk/arm64/` (pmap, arm_vm_init).

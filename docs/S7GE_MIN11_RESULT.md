# S7GE — resultado de min11: el alias estaba bien formado pero medía 2 MiB (2026-11-14; L2, E-0118)
Datos A5V (transcritos de una foto por ChatGPT; no verificados contra la imagen, pero coherentes entre sí):
| Campo | Valor | Decodificación |
|---|---|---|
| `TTBR1` / `cpu_ttep` | `0x882532000` | iguales: la tabla final es la activa; está en el banco 2 de RAM |
| `TCR` | `0x00000022a5192519` | **TG0 = 0 y TG1 = 2: granularidad de 4 KiB**; T0SZ = T1SZ = 25 (39 bits); IRGN/ORGN = 1, SH = 2; IPS = 2 |
| `VA` | `0xfffffffe00002000` | **mal leído**: el código da `VM_MIN_KERNEL_ADDRESS + 2 MiB = 0xffffffe000200000` |
| `L1e` | `0x3800000882569003` | tabla válida (tipo 3) a `0x882569000`; atributos de tabla XN/AP: los que puse con `init_ptpages` |
| `L2e` | `0x00600000e2a00605` | **bloque** (tipo 1) de **PA `0xe2a00000`**, AttrIndx 1, SH 2, AF 1, PXN y UXN; el PA está alineado a **2 MiB** |
| `PAR` | `0x44000000e2a00000` | **F = 0 (traducción correcta)**, PA `0xe2a00000`, atributo `0x44` = Normal no cacheable |

## Conclusión (la causa del fallo del alias)
El mapeo **funciona**, pero cubre **2 MiB** (el bloque L2 de una granularidad de 4 KiB), no los **32 MiB** que supuse al copiar el parche del donante (que traduce con 16 KiB). El framebuffer mide **14,7 MB** (`A5XELTE_FB_BLOCKS = 8` bloques de 2 MiB en `start.s`): solo las primeras ~364 filas están en el alias. La prueba `AT S1E1W` se hizo sobre el **primer píxel** del bloque (válido), y **la escritura de la sonda en la fila 1500** (≈ 8,6 MB) cayó en el segundo bloque **sin mapear** ⇒ fallo de traducción ⇒ aborto de datos ⇒ el manejador llama a `vm_fault` sin hilo actual ⇒ segundo fallo en `_vm_fault_internal+0x24` (NULL + 0x9e) ⇒ "Invalid kernel stack pointer". Es el mismo fallo que dejó `min9` colgada (los bloques ≥ 20 están en filas > 364) y el que impidió ver nada en `min8`.
Esto además **corrige** una frase mía y de ChatGPT: la pila no está corrupta, el mensaje es genérico en esta fase.

## Parche 0347
Mapea `A5XELTE_FB_BLOCKS` (8) bloques L2 consecutivos (PA `0xe2a00000 + k·2 MiB`) en lugar de uno. Con esto el alias cubre las 2560 filas. Se mantienen la sonda con `AT` y las impresiones `A5V` (útiles si algo vuelve a fallar). **Nada de lo anterior cambia el misterio original** (el reinicio tras apagar TTBR0 de min2-min7); el alias es el instrumento para verlo.

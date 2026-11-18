# Informe de aprendizaje: leer el disco (UFS) y montar el primer sistema de archivos

> *Informe retroactivo (D-0091), reconstruido a partir de `HEROLTE_PROGRESS.md` y del historial de Git. Este trabajo de octubre lo hizo el proyecto upstream y es la base heredada; las medidas son las que ese registro anota.*

## 1. Qué hicimos y por qué
XNU esperaba un volumen raíz y no tenía driver de almacenamiento. Se escribió un controlador mínimo del UFS del S7, se le hizo leer la tabla de particiones y se montó primero una imagen de prueba y después la raíz real de iOS 16.7.16 en la partición USERDATA.

## 2. El concepto
- **UFS:** memoria flash con protocolo SCSI sobre un enlace serie. El anfitrión no manda bytes sueltos: arma una **lista de peticiones** (UTRD) en RAM con paquetes **UPIU** y toca un *timbre* (doorbell).
- **LUN y W-LUN:** un UFS expone varias unidades lógicas (aquí 4) y unidades «bien conocidas» como la del dispositivo (0xD0).
- **GPT:** la tabla de particiones (128 entradas); aquí desde BOTA0 hasta USERDATA, de unos 21,5 GB.
- **HFS+ (variante HFSX):** el sistema de archivos que el XNU de esta serie monta como raíz.
- **Raíz sin sellar:** iOS verifica un volumen firmado; aquí se continúa sin él (`root volume is not authenticated; continuing unsealed`).

## 3. La evidencia (medido)
1. TEST UNIT READY devolvió una respuesta real (CHECK CONDITION): el transporte funcionaba pero el disco decía «no listo».
2. LUN 0-3 respondían NOT READY y 4-7 ILLEGAL REQUEST: el S7 tiene 4 unidades.
3. Hipótesis: S-Boot deja el UFS en bajo consumo. **Confirmada**: tras `START STOP UNIT (ACTIVE)` al W-LUN 0xD0, `READ(10)` de LBA 1 devolvió la firma `EFI PART`.
4. Un volumen HFSX de 32 MiB se montó (`hfs: mounted HEROTEST`) y falló después, como se esperaba, por `exec of /sbin/launchd failed, errno 2`.
5. Raíz real: 20480 MiB en 3 partes con SHA-256, escrita en bloques de 64 MiB con lectura de comprobación (320/320).

## 4. Cómo defenderlo
**Pregunta posible:** ¿Por qué el disco respondía NOT READY si S-Boot ya lo había usado?
**Respuesta modelo:** Porque S-Boot lo deja en un modo de bajo consumo; el estándar exige activarlo con START STOP UNIT. Lo comprobé porque Linux hace lo mismo, y con ese comando el READ devolvió datos.

**Pregunta posible:** ¿Por qué se montó antes una imagen de 32 MiB?
**Respuesta modelo:** Para validar sola la cadena disco→bloque→HFS con algo barato de escribir y de revertir, antes de gastar una escritura de 20 GB.

**Pregunta posible:** ¿Para qué leer lo escrito después de cada bloque?
**Respuesta modelo:** Porque un adb que se corta o una escritura silenciosamente corrupta daría una raíz rota que parece un fallo de iOS. La lectura con SHA-256 distingue un fallo de transporte de un fallo de software.

## 5. Para profundizar
Parche `0204` (UFS), `tools/herolte-flash-root.py`, workflow `ios-root`, `docs/herolte-bringup.md`.

# ANÁLISIS ESTRATÉGICO — ¿Driver nuevo estilo S7GE para Wi-Fi?

*(Texto de la Jefatura Técnica (Qwen) recibido del Director el 2026-11-15 con «Autorizo todo lo siguiente ya que lo he leído conscientemente. Firmado PioXI». Se guarda un resumen fiel de lo que ordena; el ingeniero anota correcciones en `docs/S7GE_MIN35_ANALYSIS.md` y en el relevo H-0114: (1) `network.txt` NO usa `ssid=`/`password=` sino el nombre en la 1.ª línea y la contraseña en la 2.ª, y es OPCIONAL; (2) las acciones de §5 «cuando el Director autorice» (escribir la zona DROP, flashear min36) siguen necesitando la firma con hash.)*

## Resumen de lo ordenado
- **Respuesta a la pregunta del Director:** no hace falta un driver nuevo estilo S7GE para el Wi-Fi: el driver existe (BCM4359 por PCIe, probado en upstream) y falta el firmware.
- **Fase 1 (driver existente primero):** 1.1 extraer el firmware de VENDOR en solo lectura (acción roja) con `tools/herolte-wifi-extract.sh`; 1.2 el Director crea `network.txt` en su PC (el ingeniero no lo ve ni lo registra); 1.3 el ingeniero prepara el paquete DROP con el firmware; 1.4 imagen con `herowifi=1`; 1.5 el Director flashea y prueba.
- **Fase 2 (si falla):** analizar los logs del kernel y corregir lo concreto (PCIe, energía/clock, NVRAM, compatibilidad).
- **Fase 3 (último recurso, solo si la 2 falla repetidamente):** driver nuevo (meses).
- **En paralelo (verde/amarillo):** parche 0360 (tiempo de sistema en el muestreador) con CI («autorizado por D-0030»); preparar la imagen de fluidez con `a5fb_hz=30`, `heroquantum=500` y bloquear `wifid` e `identityservicesd`.

## Texto de autorización de §3 Paso 1.1 (el que el Director firmó al autorizar el documento)
```
Autorizo ejecutar tools/herolte-wifi-extract.sh en el S7 desde TWRP para extraer
fw.bin, clm.blob y nvram.txt de la partición VENDOR en solo lectura.
Los archivos se copian a ~/HackiOS/builds/device-day/wifi-firmware/ en el PC.
Solo lectura en VENDOR, sin escritura en el teléfono.
Firmado PioXI.
```

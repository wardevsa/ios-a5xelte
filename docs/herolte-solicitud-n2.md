# Solicitud de autorización ROJA para escribir BOOT en el S7 (N2) — 2026-11-14 (actualizada con la decisión de jefatura)

**Estado:** la candidata está lista y verificada **en el PC**; **nada se ha escrito en el teléfono** y esta solicitud **no autoriza nada** hasta que el Director la apruebe con sus palabras (D-0010). Hasta ahora todas las comprobaciones son L2 (PC): que arranque es una **hipótesis** que solo el teléfono puede probar (L3).

## 0. Decisión de la jefatura técnica (2026-11-14) y plan por fases
**Primer flasheo: la variante de menor huella de hardware; la candidata normal queda de reserva para un segundo flasheo, que necesitaría su propia autorización.** Cada escritura en BOOT es una operación roja distinta y la autorización nombra una imagen y un hash.
| Fase | Qué | Autorización |
|---|---|---|
| 1 | Escribir **`xnu-boot-v2-s7-min-20261114.img`** en BOOT y arrancar (N2 de menor huella) | **la que se pide aquí** |
| 2 | Observar y registrar el arranque (`docs/S7GE_MIN_BOOT_VALIDATION.md`); volver a TWRP; comprobar BOOT/EFS | lectura de particiones: cubierta si el Director la nombra |
| 3 | Si la fase 2 es buena: escribir la candidata normal `xnu-boot-v2-s7-20261114.img` (Wi-Fi/energía/GPU activados) | **nueva autorización** del Director con su hash |
| 4 | Activar subsistemas uno a uno (un boot-arg por intento) | **una autorización por cada nueva imagen** |
**Precisión sobre el riesgo:** los hilos que la variante mínima evita ya funcionaron en un teléfono del upstream con la misma GPU (`GPU_ID 0x880`, Mali-T880; no en esta unidad; **no** es un Galaxy A5 ni un Exynos 7580). El riesgo no es "registros equivocados" sino que **esta unidad** (otro silicio, otro bin de tensión) se comporte distinto: por eso se activan de a uno. "Dañar componentes" es una posibilidad teórica que no se ha observado, no una probabilidad medida.

## 1. Imagen (fase 1)
| | |
|---|---|
| Nombre | `xnu-boot-v2-s7-min-20261114.img` (carpeta `~/HackiOS/builds/device-day/boot-candidates-n2-run3-min/`, E-0040) |
| SHA-256 | `07ddfa069c7f53936964e05f174ddced6a75b6ff690180e648a082c941115db3` |
| Kernel | `kernel.development.herolte`, SHA-256 `62ea7501ee4483dc83bb6402ac2210153ecb55e535208ddabf52942a3ec02d5b`, compilado por el CI (run `43579309448`, rama `herolte-drop-v2`, commit `50a3abc`); los 6 parches 0332-0337 constan como aplicados (E-0037) |
| Cargador | `loader-clang/xnu_boot.Image` (clang; D-0016), SHA-256 `0a68abbd…7cfc` |
| ADT | `embedded.adt`, SHA-256 `dc817436…bbd0` |
| Base | el BOOT original del teléfono, SHA-256 `adc519d0…3348` (E-0009) |
| Línea de arranque | `debug=0xc keepsyms=1 -noprogress cpus=8 rd=ufsroot0 ufsroot=USERDATA cs_enforcement_disable=1 wdt=-1 -wdt_no_pmu wdt_test=no_user_checkin ufsrw=0 herolog=0 herodrop=0 herowifi=0 heropower=0 herogpu=0` — **almacenamiento de solo lectura** (sin `ufsrw=1`, el driver UFS rechaza escribir; USERDATA y Android quedan intactos) **y sin los hilos de Wi-Fi, energía ni GPU** |
| Tamaño | 18 618 384 bytes en una partición BOOT de 41 943 040 |
**Reserva (fase 3, NO incluida en esta autorización):** `xnu-boot-v2-s7-20261114.img`, SHA-256 `2c155829b1c6c7c5161b0bf245ae4015e5b041a01ad907507c84f3b70a648f40` (E-0038): la misma sin los tres `=0` de hardware.

## 2. Verificaciones hechas (PC)
- Variante mínima: verificador del constructor (`--profile n2-readonly`) **47 PASS, 0 FAIL**; ejecución independiente con `--expect-arg` de los 7 argumentos clave: **54 PASS, 0 FAIL**. (La candidata normal: 47 y 51 PASS, 0 FAIL.)
- Cabecera Android, SHA-1 id, ramdisk y direcciones de carga idénticos al BOOT original; el payload se anexa y la línea de arranque se lee del payload.
- La candidata anterior (`26a39560…`, E-0001) se conserva; esta es nueva con el kernel que incluye los parches de upstream.
- Pruebas de host de DROP v2, de `ci_check` y del adaptador de nombres en verde.

## 3. Copias de seguridad (estado real: `docs/S7GE_BACKUP_STATUS.md`, 2026-11-14)
- **Verificadas contra el teléfono el 2026-11-12 y re-verificadas hoy:** BOOT (= E-0009), EFS, CPEFS, PERSISTENT, PARAM, PERSDATA, **RECOVERY (completa)**, BOTA0/1 en `~/HackiOS/backups/device-herolte/2026-11-12/` (permisos 600, fuera del teléfono y de git).
- **Snapshot del Director de hoy (NVMe):** `BOOT.img` bueno (el prefijo de 41 943 040 bytes = E-0009; 98 bytes de cola de `dd`); `EFS.img` bueno (difiere de la de 11-12 solo en 8 bytes del superbloque ext4: un montaje más); **`RECOVERY.img` truncada (16 %), no usar**; `SYSTEM.img` 5,7 GB **sin verificar**; **`USERDATA.img` 0 B (falló)**. Copia de USERDATA en tarjeta SD: **declarada, no verificada** (sin ruta ni hash).
- **Lo que la fase 1 necesita está cubierto** (volver al BOOT original, EFS, RECOVERY); no se toca USERDATA. **Pendiente de tu decisión:** aceptar que SYSTEM/USERDATA no están verificados porque la fase 1 no los toca, y la lectura de las particiones en el teléfono (`device-read`) para comparar.
- Riesgo señalado: las copias de 11-12 siguen en un solo disco; hay además `EFS.img` de hoy en el NVMe.

## 4. Qué se escribiría y qué no
- **Solo la partición BOOT** (`/dev/block/platform/155a0000.ufs/by-name/BOOT`), desde TWRP, con la imagen de arriba. **Nunca** EFS, RECOVERY ni bootloaders (AGENTS.md; regla X).
- Ningún otro dispositivo, ninguna otra partición, sin tocar USERDATA.

## 5. Procedimiento propuesto (para que lo revise y apruebe el Director)
1. Con el teléfono en TWRP y la imagen copiada al teléfono (o por `adb`), comprobar su SHA-256 **en el teléfono** antes de escribir.
2. Escribir en BOOT: `dd if=<imagen> of=/dev/block/platform/155a0000.ufs/by-name/BOOT` (o Instalar → imagen → Boot) y verificar leyendo de vuelta los primeros 18 618 384 bytes con el mismo hash.
3. Reiniciar; observar la pantalla. **Resultado esperado de N2:** texto del kernel en pantalla, 8 núcleos, GPT del UFS; falla al montar la raíz (USERDATA es ext4): es lo esperado.
4. Si no arranca (sin texto): Vol− + Power ~7 s y enseguida Vol+ + Home + Power para TWRP.
5. **Vuelta atrás:** reescribir `BOOT.img` (E-0009) desde TWRP y comprobar su hash.
**Opcional antes (N1, la sonda `probe-boot-clang.img`, SHA-256 `541f86aa…`):** no ejecuta XNU; confirma el hardware y vuelve a TWRP a los 60 s. Es el peldaño de menor riesgo; el Director decide si quiere N1 antes de N2.

## 6. Riesgos y límites
- **"Solo lectura" significa almacenamiento, no hardware.** Con la línea de N2 tal cual, el kernel arranca por defecto el hilo de **Wi-Fi** (escribe GPIO WLAN_EN/PERST, una puerta de reloj de CMU, registros del PMU y el PHY/PCIe del chip), el de bus/display (puede cambiar un mux de reloj del display) y los de energía y medición (lectura de TMU/PMIC, medición de CPU); **no** cambia tensión ni frecuencia de CPU (falta `herocpu_mhz`), según lo leído (`docs/S7GE_SPLIT_PLAN.md` §3; Wi-Fi y bus no leídos a fondo). Probado solo en el teléfono del upstream. **Variante de menor huella** ya construida y verificada en el PC (`xnu-boot-v2-s7-min-20261114.img`, SHA-256 `07ddfa069c7f53936964e05f174ddced6a75b6ff690180e648a082c941115db3`, E-0040): añade `herowifi=0 heropower=0 herogpu=0`; el Director elige cuál usar (con la mínima se pierden los logs de GPU/energía en el primer intento).
- **No está probado nada en este teléfono**; el resultado puede ser pantalla negra o reinicio. Mitigación: copias verificadas y el arranque a TWRP por teclas; S-Boot y modo Download no se tocan.
- Un fallo de escritura parcial de BOOT es recuperable desde TWRP/Download con `BOOT.img`; por eso el paso 2 exige comprobar el hash leyendo de vuelta.
- Esta solicitud usa el módulo `herolte-verify-boot.py`, que comprueba consistencia, no comportamiento.

## 7. Texto que el Director puede usar para autorizar (solo la fase 1)
> «Autorizo `device-write-boot` (y `device-read` de las particiones BOOT y EFS para comprobarlas antes y después) en el S7 para escribir `xnu-boot-v2-s7-min-20261114.img` (SHA-256 `07ddfa069c7f53936964e05f174ddced6a75b6ff690180e648a082c941115db3`) en la partición BOOT (`/dev/block/sda5`), desde TWRP, siguiendo `docs/herolte-solicitud-n2.md` y `docs/S7GE_MIN_BOOT_VALIDATION.md`; solo BOOT; vuelta atrás con `BOOT.img` (E-0009). Acepto que SYSTEM y USERDATA no están verificados y que la fase 1 no los toca. No autoriza ninguna otra imagen.»
**Antes de firmar:** confirmar en TWRP con `ls -l /dev/block/platform/155a0000.ufs/by-name/` que BOOT es `sda5`.
**Dos advertencias sobre el borrador de jefatura:** (1) citaba el hash como `07ddfa06...8f40`: **`…8f40` es el final de la candidata NORMAL** (`2c155829…8f40`), no de la mínima (`…5db3`); la autorización **debe llevar el hash completo y exacto**, porque el script de escritura lo compara. (2) incluía el **número de serie del teléfono**: no debe ir en documentos ni en git; si hay más de un dispositivo conectado se usa `ANDROID_SERIAL` en el entorno de quien ejecuta.

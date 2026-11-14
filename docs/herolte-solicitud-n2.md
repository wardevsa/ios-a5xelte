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

## 3. Copias de seguridad (E-0036, verificadas el 2026-11-14)
`~/HackiOS/backups/device-herolte/2026-11-12/`: BOOT (= E-0009), EFS (contiene el IMEI), CPEFS, PERSISTENT, PARAM, PERSDATA, RECOVERY, BOTA0/1; todas con `SHA256SUMS` correcto, permisos 600, **fuera del teléfono**, no en git. **Riesgo señalado:** todas están en el mismo disco del PC; una segunda copia (sobre todo EFS) fuera de él es prudente (decisión del Director).

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
> «Autorizo `device-write-boot` (y `device-read` de las particiones BOOT y EFS para comprobarlas antes y después) en el S7 para escribir `xnu-boot-v2-s7-min-20261114.img` (SHA-256 `07ddfa06…5db3`) en la partición BOOT, desde TWRP, siguiendo `docs/herolte-solicitud-n2.md` y `docs/S7GE_MIN_BOOT_VALIDATION.md`; solo BOOT; vuelta atrás con `BOOT.img` (E-0009). No autoriza ninguna otra imagen.»
**Antes de firmar:** que el backup de esta jornada esté completo, recortado y comprobado contra el teléfono (KI-0008), y confirmar en TWRP con `ls -l /dev/block/platform/155a0000.ufs/by-name/` que BOOT es `sda5`.

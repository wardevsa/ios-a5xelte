# Solicitud de autorización ROJA para escribir BOOT en el S7 (N2) — 2026-11-14

**Estado:** la candidata está lista y verificada **en el PC**; **nada se ha escrito en el teléfono** y esta solicitud **no autoriza nada** hasta que el Director la apruebe con sus palabras (D-0010). Hasta ahora todas las comprobaciones son L2 (PC): que arranque es una **hipótesis** que solo el teléfono puede probar (L3).

## 1. Imagen
| | |
|---|---|
| Nombre | `xnu-boot-v2-s7-20261114.img` (carpeta `~/HackiOS/builds/device-day/boot-candidates-n2-run3/`; copia en NTFS, E-0038) |
| SHA-256 | `2c155829b1c6c7c5161b0bf245ae4015e5b041a01ad907507c84f3b70a648f40` |
| Kernel | `kernel.development.herolte`, SHA-256 `62ea7501ee4483dc83bb6402ac2210153ecb55e535208ddabf52942a3ec02d5b`, compilado por el CI (run `43579309448`, rama `herolte-drop-v2`, commit `50a3abc`); los 6 parches 0332-0337 constan como aplicados (E-0037) |
| Cargador | `loader-clang/xnu_boot.Image` (clang; D-0016), SHA-256 `0a68abbd…7cfc` |
| ADT | `embedded.adt`, SHA-256 `dc817436…bbd0` |
| Base | el BOOT original del teléfono, SHA-256 `adc519d0…3348` (E-0009) |
| Línea de arranque | `debug=0xc keepsyms=1 -noprogress cpus=8 rd=ufsroot0 ufsroot=USERDATA cs_enforcement_disable=1 wdt=-1 -wdt_no_pmu wdt_test=no_user_checkin ufsrw=0 herolog=0 herodrop=0` — **solo lectura**: sin `ufsrw=1`, el driver UFS rechaza escribir (USERDATA y Android quedan intactos) |
| Tamaño | 18 618 384 bytes en una partición BOOT de 41 943 040 |

## 2. Verificaciones hechas (PC)
- Verificador del constructor (`herolte-verify-boot.py --profile n2-readonly`): **47 PASS, 0 FAIL**.
- Ejecución independiente con `--expect-arg cpus=8 ufsrw=0 herolog=0 herodrop=0`: **51 PASS, 0 FAIL**.
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
- **No está probado nada en este teléfono**; el resultado puede ser pantalla negra o reinicio. Mitigación: copias verificadas y el arranque a TWRP por teclas; S-Boot y modo Download no se tocan.
- Un fallo de escritura parcial de BOOT es recuperable desde TWRP/Download con `BOOT.img`; por eso el paso 2 exige comprobar el hash leyendo de vuelta.
- Esta solicitud usa el módulo `herolte-verify-boot.py`, que comprueba consistencia, no comportamiento.

## 7. Texto que el Director puede usar para autorizar
> «Autorizo `device-write-boot` (y `device-read` de la partición BOOT) en el S7 para escribir `xnu-boot-v2-s7-20261114.img` (SHA-256 `2c155829…8f40`) en la partición BOOT, desde TWRP, siguiendo `docs/herolte-solicitud-n2.md`; solo BOOT; vuelta atrás con `BOOT.img` (E-0009).»

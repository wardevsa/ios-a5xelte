# Estado del proyecto y camino hasta flashear — 2026-11-12

Informe del jefe de proyecto suplente. **No se ha flasheado nada.** Flashear o formatear el teléfono exige consejo con el responsable.

## 1. Respuesta corta
**Instalar iOS completo: todavía no.** Faltan tres cosas (§3). **Pero hay una escalera de pruebas que solo escribe BOOT y no borra el Android**
(§4), y los dos primeros peldaños ya tienen todo preparado salvo el visto bueno del responsable.

## 2. Qué es cada pieza (y qué se está compilando)
| Pieza | En una frase |
|---|---|
| **XNU / el kernel** | el núcleo de iOS (código abierto de Apple), adaptado por el proyecto al Exynos 8890 del S7 con unos 260 parches |
| **El cargador (`shim`)** | un programa pequeño que arranca primero (lo lanza S-Boot de Samsung) y deja el kernel de iOS en memoria |
| **El ADT** | la "lista de hardware" que iOS espera encontrar; se saca del IPSW público de un iPhone X y se adapta al S7 |
| **La imagen BOOT** | la partición donde el S7 guarda lo que arranca: cargador + kernel + ADT + línea de arranque. Es lo único que se escribe en las primeras pruebas |
| **El root de iOS** | los 20 GiB de ficheros de iOS (la "carpeta del sistema"); va en USERDATA, y **escribirlo borra Android** |
| **DROP** | el mecanismo para meter ficheros extra en iOS sin rehacer los 20 GiB: se escriben al final del almacenamiento y el kernel los copia al arrancar |
| **DROP v2** | DROP rehecho para que un corte de energía o un fallo del disco no deje el sistema a medias |
**Lo que ha compilado GitHub** (en un servidor macOS, porque XNU solo se compila con herramientas de Apple), ya **terminado con éxito**:
el **kernel con DROP v2** (parche `0334`, run `43223873690`, 34 min), un fichero `kernel.development.herolte` de 17 MB, y `mesa-ios`
(run `43223964125`: librerías gráficas y `hero-run`, el programa que recoge lo que DROP deja listo). `ci_check.py` confirma que
0334 **se aplicó** (260 parches aplicados, 4 saltados, todos de blacktop) y `preflight.py` clasifica el kernel como DROP v2.

## 3. Lo que falta para instalar iOS completo
| # | Bloqueante | Estado |
|---|---|---|
| 1 | ~~Kernel con DROP v2 compilado y comprobado~~ | **hecho**: compiló, 0334 aplicado, clasificado como DROP v2 (SHA-256 `e678b454…`) |
| 2 | **El root de iOS (20 GiB)** | no existe en tu cuenta (el repo privado de la guía no está). Opciones y costes en `xnu/drop-v2/deviceday/RUNBOOK.md`: nube privada (puede costar cuota), construirlo en este PC (hace falta `sudo` + `apfs-fuse`) o que lo facilite el responsable |
| 3 | **Decisión del responsable** | instalar borra todo el Android; además hay que confirmar la escritura de la zona DROP en USERDATA |
Ya resuelto en esta sesión: **ADT** (sacado del IPSW público), **copias del teléfono** (BOOT, EFS, etc., verificadas), **imágenes BOOT candidatas** con el kernel v2 (`xnu-boot-v2-clang.img`, 18,6 MB) y de sonda (`probe-boot-clang.img`, 1,8 MB),
**cargador** (de clang; el compilador oficial de Arm está descargado y con el hash verificado, pero **no se ha ejecutado**: el sistema de permisos bloqueó ejecutar un binario descargado, y recompilar el cargador con GCC queda a decisión del responsable), **paquete de autoprueba** de DROP v2.
Aún por sacar del teléfono (lectura): firmware Wi-Fi/BT y comprobar si el módulo es `murata` o `semco`.

## 4. La escalera de pruebas (de menos a más riesgo)
| Peldaño | Qué escribe | Qué se aprende | Cómo se vuelve atrás |
|---|---|---|---|
| **N1. Probe** (`probe.Image`) | solo BOOT | confirma que esta unidad es el mismo hardware que la del proyecto (MIDR, MPIDR, FDT, RAM). No ejecuta XNU; a los 60 s vuelve a TWRP | volver a escribir `BOOT.img` (copia verificada) |
| **N2. XNU arranca, solo lectura** | solo BOOT | que el cargador, el kernel y el ADT arrancan en esta unidad (texto en pantalla, 8 núcleos, GPT del UFS). **Sin `ufsrw=1` el driver UFS no escribe** (`ufs_write_blocks` lo rechaza), así que USERDATA y Android quedan intactos; fallará al montar la raíz (es ext4), y eso es lo esperado | igual |
| **N3. Instalación completa** | BOOT + USERDATA (20 GiB) | iOS arranca | restaurar BOOT; **Android se pierde** |
| **N4. DROP v2 en el teléfono** | zona DROP (USERDATA) | el protocolo nuevo, con la autoprueba | `herolte-drop.py --clear` |
Mi recomendación: **N1 y N2 pueden hacerse en cuanto el responsable lo autorice**; N3 y N4 esperan al root y a su consejo.
Cuidado: la línea de arranque diaria mide 604 de 607 caracteres (no cabe `herodrop=0` sin quitar otra cosa).

## 5. Trabajo pendiente "como DROP v2" (backlog priorizado)
| Prio | Tarea | Por qué | Esfuerzo |
|---|---|---|---|
| 1 | **Que el CI falle si salta un parche nuestro** | hoy un parche roto se salta sin error y sale un kernel viejo; `ci_check.py` lo detecta a mano (ya se usó con éxito), falta ponerlo en `xnu.yml` | pequeño |
| 2 | **USB en modo dispositivo (red + log en vivo)** | acaba con volver a TWRP en cada prueba; hay una pila heredada (0072–0081) y el hardware medido (`docs/herolte-usb-plan.md`) | grande; necesita sonda en el teléfono |
| 3 | Presupuesto de la línea de arranque (604/607) | impide añadir opciones; ampliar el formato del payload o acortar argumentos | pequeño-medio |
| 4 | Cerrar flecos de DROP v2 | limpieza de `trash/`, prueba real en el teléfono, actualizar la guía tras probar | pequeño |
| 5 | Wi-Fi: variante de módulo y elección de red | la guía fija el `nvram` de `semco`; esta unidad trae también `murata` | pequeño |
| 6 | Micrófono y auriculares (codec Cirrus), luego Bluetooth (servicio `AppleBluetooth` fino) | funciones que faltan; Bluetooth es la más abordable | medio-grande |
| 7 | Sensores (servicio HID tipo `AppleSPU`), reposo, vibración | pendientes | grande |
| 8 | Safari/JIT y desenfoques (Metal) | limitaciones conocidas | grande, largo plazo |
| — | Cámara, módem, huella | descartadas (`docs/herolte-peripherals.md`) | — |
Mantenimiento: `tools/validate-repo.py` ya fallaba (huecos y duplicados en la numeración de parches) y nadie lo usa como puerta; retirar el borrador 0333.

## 6. Qué no sé todavía
Si 0334 compila en XNU (lo dirá el CI); el comportamiento real de `F_FULLFSYNC` desde el kernel; si el cargador de clang se comporta como el de GCC
(por eso se descargó el compilador de Arm); la estabilidad a largo plazo con 8 núcleos y la integridad del DMA del UFS bajo carga.

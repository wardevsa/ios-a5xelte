# Informe de aprendizaje: Wi-Fi desde cero hasta navegar en iOS

> *Informe retroactivo (D-0091), reconstruido a partir de `HEROLTE_PROGRESS.md` y del historial de Git. Este trabajo de octubre y principios de noviembre lo hizo el proyecto upstream y es la base heredada; las medidas son las que ese registro anota.*

## 1. Qué hicimos y por qué
El S7 tiene un chip Wi-Fi Broadcom (BCM4359) que solo funciona con su firmware y un protocolo propio. iOS necesitaba una interfaz de red (`en0`) y un demonio Wi-Fi funcional. Se hizo en cuatro pasos: enlace PCIe, firmware, WPA2 en el kernel e integración con iOS.

## 2. El concepto
- **PCIe:** bus serie; el chip está en el canal 0. Para levantarlo hay que respetar el orden y los tiempos de Samsung.
- **brcmfmac / msgbuf:** protocolo del controlador de Broadcom: colas de mensajes en RAM del anfitrión para control, datos y eventos.
- **Supplicant y handshake de 4 vías:** WPA2 necesita derivar claves (PMK por PBKDF2, PTK, MIC) y desenvolver la GTK con AES. Android lo hace con `wpa_supplicant`; el firmware de Samsung **no** trae ese soporte.
- **Interfaz de red en XNU:** `en0` se crea con la KPI de interfaces y `configd`/`wifid` hablan con ella.
- **`_LimitLoadToDeviceTree`:** un job de launchd solo arranca si el ADT trae un nodo con ese nombre.

## 3. La evidencia (medido)
- El enlace PCIe subió al primer intento; `14e4:4415`, ChipCommon `0x17094359`.
- Firmware cargado en TCM: RTE 9.96.17 en BCM43596 C0. Primer escaneo: 11 redes en 2,4 y 5 GHz.
- Con `sup_wpa=1` el firmware respondió **-23 (BCME_UNSUPPORTED)**. En 0312 el AP expulsaba cada ~5 s con razón 15 (timeout del 4-way).
- Handshake escrito en el kernel (SHA-1, HMAC, PBKDF2 y AES a mano, verificados contra `hashlib` y RFC 3394). Resultado: **`CONNECTED with WPA2 in 1649 ms`** y **`DHCP OFFER: 192.168.1.25`**.
- En iOS: `en0` con 9391 tramas enviadas y 11076 recibidas (15154960 bytes); el icono Wi-Fi no salía porque `wifid` nunca lanzaba (faltaba el nodo `wlan` del ADT).
- Medido después: Wi-Fi activo cuesta ~120 mA con la pantalla encendida.

## 4. Cómo defenderlo
**Pregunta posible:** ¿Por qué hubo que implementar WPA2 en el kernel?
**Respuesta modelo:** Porque el firmware de Samsung no trae supplicant (responde BCME_UNSUPPORTED) y en Android lo hace una aplicación. Sin él el AP expulsa por timeout del 4-way handshake.

**Pregunta posible:** ¿Cómo sabes que tu criptografía era correcta?
**Respuesta modelo:** Se verificó en dos sitios: una transcripción a Python contra `hashlib` y los vectores del RFC 3394, y de nuevo en el teléfono al arrancar (`PBKDF2 ok, AES key unwrap ok`). Y la prueba final fue que el AP aceptó las claves y respondió el DHCP.

**Pregunta posible:** ¿Por qué no salía el icono Wi-Fi con la red funcionando?
**Respuesta modelo:** `wifid` nunca se lanzaba: su job exige un nodo `wlan` en el árbol de dispositivo y el ADT no lo tenía.

## 5. Para profundizar
Parches `0308`-`0315`, `bsd/dev/herolte_wifi.c`, `SweetWLAN.cpp`, `SweetNetworkStack.cpp`.

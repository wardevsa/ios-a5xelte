# Guardar un archivo en Archivos en el S7 (investigación del 2026-11-22)

Qué se intentó: guardar un MP3 descargado en Safari con «Guardar en Archivos». Evidencias E-0399 a E-0410.

## Lo que ya está resuelto
1. **`mediaserverd` abortaba con cualquier vídeo** (E-0399): nuestro parche 0046/0061 puso `DisplayPipePlaneBaseAlignment` como número y VideoToolbox/QuartzCore leen un diccionario. Parche 0488.
2. **«Internal error, couldn't communicate with a helper application» al guardar** (E-0401): las extensiones de app (`SaveToFiles`, `DocumentManager.Service`, `PhotosFileProvider`) abortaban con
   `plugin has invalid sandbox or container: error 2` porque la operación 4 del «Sandbox» del kernel (ruta del contenedor) devolvía ENOENT. Parche 0489 v2: para el propio proceso, usuario no root
   y un buffer que empieza por `?` (lo pone PlugInKit) devuelve 0 y `/private/var/mobile`. **Confirmado en el teléfono** (E-0409): sin ese error ni cierres.
3. **Arranques atascados en el logo** (E-0403 a E-0408): no era el kernel ni el estado de SpringBoard; la causa probable era la tanda 1 de trabajos desactivados (los siete de Apple Watch, CarPlay
   y FaceTime, sospechados; sin demostrar uno a uno). Con la lista de 25+11 llega a la pantalla de inicio y el bucle de `lskdd` (484 arranques en 13 min) desaparece.

## Lo que queda: «Content Unavailable» en Archivos
- Síntoma: al guardar sale una barra de búsqueda; al elegir una etiqueta, «Content Unavailable... unknown error»; en la app Archivos, lo mismo.
- **Etiquetas:** Archivos las saca de Spotlight (`com.apple.spotlight.SearchAgent`), que no existe a propósito (searchd desactivado). Registro: `failed lookup: ... spotlight.SearchAgent ... error = 3`
  y `CSSearchQueryErrorDomain -2001`. Es esperable, y no se arregla sin traer Spotlight.
- **«En mi iPhone» (el sitio donde se guarda de verdad):** el proveedor `LocalStorageFileProvider.appex` (`com.apple.FileProvider.LocalStorage`) **no llega a ejecutarse nunca**. Registro unificado:
  `NSFileProviderInternalErrorDomain Code=0 "No valid file provider found from URL file:///.../Safari/Downloads/.../*.mp3"`.
- Lo que se sabe del lado del sistema (cadenas de `FileProviderDaemon.framework` en la caché local; sin símbolos): fileproviderd tiene el error
  `[ERROR] Extension %@ doesn't have a group container for document group %@ specified via %@. Ignoring the extension.` y `[DEBUG] ignoring call for LocalStorage`; la extensión
  `LocalStorageFileProvider` declara `NSExtensionFileProviderDocumentGroup = group.com.apple.FileProvider.LocalStorage`.
- Lo que SÍ existe en disco: el contenedor de grupo `group.com.apple.FileProvider.LocalStorage` (Containers/Shared/AppGroup/3872A83B-...) y el contenedor de la extensión (PluginKitPlugin/FCC2AA60-...).
- Lo que NO se sabe: si fileproviderd rechaza la extensión por falta de contenedor de grupo (los registros de ese error no aparecen en el registro unificado, que oculta los argumentos `<private>` y no guarda
  los niveles bajos), o por otra causa (personas: una línea `Persona List failed with error NSPOSIXErrorDomain Code=2` aparece cerca; el sistema por lo demás carga las personas).
- **Sonda escrita (DROP 61):** el censo de `hero-run` imprime, para `LocalStorage`, `SaveToFiles` y `DocumentManager.Service`, los registros de LaunchServices: entitlements, `application-groups`,
  `groupContainerURLs` y `dataContainerURL`. Si a LocalStorage le faltan los grupos y a las otras no, la causa está en LaunchServices.

## Cómo oír el MP3 mientras tanto
Safari conserva la descarga en su carpeta (`Safari/Downloads/<id>/*.mp3`) y el botón de descargas de Safari abre una vista previa (QuickLook; el registro muestra su `QLPreviewControllerView`).

# Estado real — microfase 5

Completadas las bases, el catálogo de cinco productos y ocho creadores ficticios, y los formularios de consulta y figura personalizada. `cartel.jpg` permanece intacto. Hasta el cierre de la microfase 5 no se había creado ningún commit ni push.

Microfase 3: acceso individual de creadores/docente, sesiones revocables, recuperación de visitante de un solo uso, paneles por rol, conversación persistida y asignación/reasignación docente. La migración 0004 se aplicó a la base de trabajo que estaba en 0003: conserva sus dos solicitudes anteriores, ambas sin acceso de visitante y disponibles solo al docente y destinatario autorizado. No se han provisionado credenciales reales en la base de trabajo.

Microfase 3, comprobación manual confirmada por el usuario: visitante y creador intercambian mensajes; el docente asigna y reasigna; el creador anterior pierde acceso incluso por URL directa. Esto es distinto de las pruebas HTTP automatizadas de la fase 3 (7 correctas).

Microfase 4 implementada: fotos privadas JPG/PNG en la solicitud inicial o desde la conversación, selección y vista previa local, dos confirmaciones separadas por lote, registro de aceptación y permisos de lectura/borrado. La migración 0005 está aplicada a la base de trabajo y conserva las solicitudes anteriores. La prueba previa de esta fase pasó 7/7. En el entorno de desarrollo inicial se obtuvieron 8 pruebas correctas y 1 omitida por falta de Pillow. Posteriormente, el usuario ejecutó manualmente `python -m pytest tests -q -p no:cacheprovider` y confirmó **9 passed, sin omisiones**. Es un resultado comunicado por el usuario, distinto de la ejecución anterior del agente. No se ha hecho inspección real de navegador de esta fase.

Corrección posterior de microfase 4: el rechazo observado se producía porque solo llegaba una de las dos confirmaciones. La plantilla sí tenía ambos `input`, pero los estilos generales de campos aplicaban relleno a los checkboxes, dejando la segunda casilla difícil de reconocer o usar según la captura aportada. Se definieron tamaño, apariencia, foco, `id` y etiqueta `for` para cada casilla; el servidor sigue exigiendo ambas y ahora indica cuál falta. Si hay error se conservan alias y descripción, y se avisa de que hay que volver a seleccionar el archivo. Solo el visitante solicitante ve el formulario de subida posterior y puede usar su ruta POST; creador y docente conservan lectura, y docente y visitante conservan eliminación.

Comprobación automatizada de la corrección: **10 passed, 1 warning** con `.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp=data\pytest-consent-fixed`. La regresión lee el HTML real del formulario, usa sus nombres y valores en multipart con PNG auténtico y confirma persistencia, panel docente sin asignación y permisos de los tres roles. Chrome y el servidor local están presentes, pero los intentos de captura con Chrome no produjeron archivo; no se ha verificado el clic ni la apariencia final en navegador real. La observación visual inicial procede del usuario, no de esta ejecución.

Al cierre de la microfase 4, la demo seguía limitada a datos ficticios y uso local. La revisión general de textos y gráficos se aborda en la microfase 5, descrita a continuación.

## Microfase 5: mejora gráfica y textos

Se ha renovado el escaparate con portada en dos columnas, productos visibles en la primera pantalla, catálogo de imágenes grandes y una sección propia para la figura personalizada. Las cinco ilustraciones SVG locales se han rehecho y se ha añadido una ilustración de proceso; todas se identifican como ejemplos. Se mantiene la paleta del cartel original, sin usarlo como fondo ni modificarlo. Los datos del catálogo y las solicitudes existentes no se han editado.

Los paneles conservan una presentación más sobria. Los estados se traducen desde un único módulo sin cambiar sus valores de base de datos: `received` se muestra como «Nueva solicitud» e `in_conversation` como «En conversación». Tarjetas y detalle muestran tipo, producto cuando existe, cliente, creador y fecha de actividad; la acción se llama «Ver conversación». Los mensajes indican autor y fecha. No se han añadido indicadores de lectura, notificaciones ni cambios en reglas de negocio, sesiones, permisos o almacenamiento.

Comprobaciones: antes de editar, **10 passed, 1 warning**. Tras los cambios, **10 passed, 1 warning** con `.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp=data\pytest-phase5-final`. La advertencia es una deprecación de Starlette/AnyIO. Se actualizaron dos expectativas de pruebas que dependían de textos anteriores, conservando sus verificaciones funcionales.

Inspección real en Chrome local, con datos ficticios y sesiones separadas: 13 capturas en `docs/capturas/` de portada, catálogo, producto, solicitud, acceso, tres paneles y conversación en escritorio o móvil. En todas las vistas se comprobaron ausencia de imágenes rotas y de desbordamiento horizontal. En la solicitud móvil se verificaron las dos casillas visibles y desmarcadas. Se midió contraste del texto general (10,83:1) y del botón principal (7,05:1), foco de teclado visible (contorno sólido de 3 px) y un mensaje muy largo sin desbordamiento en móvil. Las capturas no contienen enlaces privados de recuperación ni credenciales. La revisión no sustituye una evaluación integral de accesibilidad ni una prueba manual de cada interacción.

Las páginas de Areaware, ban.do y Ugmonk se consultaron como referencia de presentación de objetos; no se pudieron valorar de forma fiable todos sus detalles visuales mediante la herramienta web. La composición y las ilustraciones implementadas son propias. El directorio actual no pertenece a un repositorio Git (`git status` devuelve «not a git repository»); no se inicializó Git ni se hizo commit o push.

**Siguiente microfase propuesta:** estudiar notificaciones y seguimiento de lectura con criterios de necesidad, privacidad y aceptación concretos. Siguen pendientes el endurecimiento y las decisiones operativas antes de cualquier despliegue público. Esta microfase 5 se detiene para revisión de apariencia.

## Aprobación y primer punto de control

El usuario aprobó la apariencia de la microfase 5. También confirmó manualmente que funcionan las solicitudes, el intercambio de mensajes entre visitante y creador, la asignación y reasignación docente, la pérdida de acceso del creador anterior tras reasignar —incluso mediante URL directa— y las fotografías privadas. Estas son comprobaciones manuales comunicadas por el usuario; no se atribuyen al arnés automático.

Se prepara el primer punto de control Git local en WebIES. La base de datos de trabajo, `.env`, los adjuntos privados, la cuarentena y las capturas locales quedan excluidos del repositorio. No se configura remoto ni se hace push.

La creación del punto de control quedó detenida por el entorno: Git pudo inicializar `.git` en WebIES, pero no pudo crear `.git/index.lock` al ejecutar `git add` (`Permission denied`). La revisión automática de permisos rechazó la elevación. Por tanto, todavía no hay archivos preparados, commit ni etiqueta. Es necesario habilitar escritura en `WebIES/.git` para terminar este punto de control.


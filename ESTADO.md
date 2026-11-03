# Estado real — microfase 6 corregida

La apariencia de la microfase 5 fue aprobada por el usuario. La demo local tiene catálogo, solicitudes, sesiones por rol, asignación docente, conversación privada y avisos de mensajes nuevos. Sigue en WebIES, sin despliegue, remoto nuevo, commit ni push de estos cambios. El punto de control anterior es `6f5116c` con etiqueta `v0.1.0-demo-local`.

## Decisión vigente sobre fotografías

Se retiró toda la función de fotografías: el formulario de figura solo pide alias y descripción; la conversación no tiene selección, vista previa ni galería. Las rutas HTTP antiguas de subida, lectura y eliminación responden 404. El envío multipart a `/figura-personalizada` se rechaza con 415. Los registros de adjuntos y aceptaciones, los archivos de almacenamiento privado y la migración 0005 permanecen intactos. La web explica que visitante y creador acordarán por otro canal cómo entregar imágenes y recuerda los derechos y permisos necesarios, incluida la intervención del representante legal si la persona es menor.

En la microfase 4 sí existieron fotos privadas. El usuario comunicó entonces una ejecución manual de **9 passed, sin omisiones** y más tarde confirmó manualmente solicitudes, conversación, asignación y reasignación, pérdida de acceso por URL del antiguo creador y fotografías. Esas observaciones corresponden al funcionamiento anterior y no son resultados del arnés actual.

## Lectura y avisos

La migración 0006 ya estaba aplicada a la base de trabajo antes de estas correcciones; inicializó como leído el historial previo para las personas que ya tenían acceso, sin crear fechas de lectura ni cambiar contenido. Se hizo una copia privada antes de migrar. El recuento documentado tras esa migración era 13 usuarios, **4 encargos, 12 mensajes**, 1 adjunto, 1 aceptación y 4 sesiones. No se alteraron esos datos de trabajo para esta reparación.

El servidor entrega un corte firmado y ligado al usuario y al encargo para los mensajes incluidos en cada respuesta. El POST de lectura, protegido por CSRF, solo acepta ese corte; un mensaje posterior continúa pendiente. El navegador distingue el último mensaje incorporado a pantalla del último confirmado. Si falla el POST, mantiene el corte y ofrece «Reintentar lectura». Las tarjetas proceden de una plantilla única compartida por HTML y sondeo. El sondeo incorpora cualquier encargo recién visible y retira los que dejan de estar autorizados, sin recargar ni borrar borradores. «Nueva para ti», «Nueva sin asignar» y «N mensajes nuevos» no cambian el estado del encargo.

## Verificación posterior al arreglo

- Suite completa con SQLite y directorios temporales: **12 passed, 1 warning**. La advertencia es la deprecación conocida de Starlette/AnyIO. Incluye corte firmado, reintento idempotente, CSRF, permisos, asignación/reasignación, persistencia, migración histórica y rutas de fotografías retiradas. Durante la actualización se detectó y corrigió un fallo de orden de tokens CSRF en una prueba y se aisló también la prueba de portada de la base de trabajo.
- `node --check app/static/notifications.js`: correcto.
- Chrome real, con dos perfiles separados y base ficticia: visitante envió consulta, el creador recibió tarjeta y aviso sin recarga, respondió, el visitante recibió el aviso en móvil y mostró el mensaje conservando el borrador. Se simuló un fallo al confirmar lectura; el botón permitió reintentar y el contador se limpió después. En el formulario móvil se comprobó ausencia de controles de fotos, conservación de la descripción y ausencia de desbordamiento horizontal. Las capturas finales se guardaron en `data/phase6-browser-20261103-164554/` (ignorada por Git).
- No se ha repetido una inspección visual completa de todas las páginas tras esta retirada; el diseño general aprobado se conservó. La revisión de tres roles y selección de archivo registrada antes de la retirada es histórica y no describe el estado vigente.

Las pruebas automáticas y la revisión de Chrome de la microfase 6 están realizadas. **La revisión manual del usuario de esta versión corregida sigue pendiente**; las comprobaciones manuales anteriores corresponden a versiones previas.

Los comandos exactos están en [README.md](README.md) y el detalle de reglas y pruebas en [INFORME_MICROFASE_6.md](INFORME_MICROFASE_6.md).

## Siguiente paso

Revisar con el usuario la demo corregida, especialmente avisos y texto sobre entrega externa de imágenes. Se preparó en el árbol de trabajo el futuro despliegue GitHub → Render + Neon: controlador Psycopg, configuración de producción, Alembic por entorno, Python 3.12 y script de arranque. La suite aislada pasó **15/15** tras esos cambios; el esquema compila para el dialecto PostgreSQL y Alembic genera SQL PostgreSQL hasta la revisión 0006, pero no hubo conexión ni migración contra PostgreSQL real. La red del entorno impidió instalar Psycopg aquí. No se crearon servicios ni se hizo push. Sin correo, push, WebSockets, pagos ni IA.

El commit solicitado **no se pudo crear en este entorno**: `git add -A` falló al crear `.git/index.lock` con `Permission denied`. Se comprobó que el archivo de bloqueo no existe; no se cambiaron permisos ni se eliminó nada. La identidad Git ya está configurada. La preparación de despliegue queda también sin commit en el árbol de trabajo. Véase [docs/despliegue-opcion.md](docs/despliegue-opcion.md).

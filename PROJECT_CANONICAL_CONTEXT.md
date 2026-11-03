# Contexto canónico

## Decisiones

- Aplicación monolítica con FastAPI, Jinja2, HTML/CSS/JavaScript sencillo, SQLAlchemy y Alembic.
- Python 3.12; SQLite para la demo y una URL configurable para facilitar evolución posterior.
- Ocho creadores se representarán por alias ficticios y roles `visitor`, `student` y `teacher`.
- Un encargo puede ser una consulta sobre producto o una figura personalizada. El destinatario puede quedar vacío hasta asignación manual por docente.
- Estados: `received -> in_conversation -> accepted -> completed`; cualquier encargo activo puede pasar a `cancelled` según la regla de negocio que se concrete.
- Una oferta o aceptación no constituye pago ni compra formal.
- Las fotografías no aparecerán en el catálogo; los adjuntos se almacenarán fuera de la carpeta pública.
- En microfase 2, cada envío local crea un visitante interno con alias aleatorio y guarda el alias visible en el encargo. Ese alias escrito no acredita identidad. La consulta de producto toma el creador como destinatario desde la base; la figura queda sin destinatario. Solicitud y mensaje inicial se confirman juntos; ofertas en céntimos enteros. Token CSRF firmado y cookie SameSite Strict; confirmación genérica tras 303, sin endpoint público de encargos.
- En microfase 3, las solicitudes nuevas tienen acceso de visitante por sesión revocable y enlace privado de un solo uso (48 h). Las antiguas conservan `visitor_access_enabled = false`; no se vinculan por alias. Docente ve todas y asigna/reasigna figuras; creador ve solo las asignadas y pierde acceso tras reasignación. Visitante ve solo las suyas. Contraseñas PBKDF2-HMAC-SHA256 con sal, tokens de sesión y recuperación aleatorios con huella SHA-256 en la base. Mensajes pasan de `received` a `in_conversation`; no se amplían otros estados.
- En microfase 4, cada lote de fotos de una figura crea una aceptación con versión `fotografias-v1-2026-11`, fecha y aceptante, enlazada a sus adjuntos. Se exigen dos declaraciones separadas si hay archivos. Pillow valida y regraba JPG/PNG sin EXIF. Máximo tres fotos activas, 5 MB cada una y 16 MB por petición. Almacenamiento privado fuera de `static`, comprobación de permisos para cada lectura y borrado; una reasignación retira acceso al creador anterior. La aceptación no demuestra por sí sola los derechos ni el permiso de imagen; si aparece un menor, el docente debe revisar la autorización del representante legal antes de utilizar la foto.

## Pendientes explícitos

Pendientes: limitación de intentos, recuperación asistida para visitantes sin enlace, política de retención y limpieza de cuarentena, revisión docente de imágenes de menores, despliegue con HTTPS y demás transiciones de estado. `SECRET_KEY` de `.env.example` es solo un marcador local; debe sustituirse antes de cualquier uso fuera de la máquina local.


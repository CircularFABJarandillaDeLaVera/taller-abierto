# Arquitectura

La aplicación es un monolito pequeño: FastAPI recibe peticiones, las rutas delegan en lógica de negocio comprobable, SQLAlchemy accede a SQLite y Jinja2 renderiza la presentación. Alembic conserva la evolución del esquema.

## Datos

`users` contiene alias y rol. `products` pertenece a un creador. `orders` identifica solicitante, destinatario opcional y producto opcional; así una figura personalizada puede permanecer sin asignar. `messages` pertenece a un encargo y a su autor. `attachments` pertenece a un encargo, registra quién lo subió, procedencia, nombre interno, nombre original, MIME y tamaño.

Las claves foráneas están activadas en SQLite. Se restringe borrar usuarios, productos relacionados o autores; mensajes y adjuntos se eliminan con su encargo. La interfaz no decide permisos: esa responsabilidad queda para servicios/reglas futuros.

## Identidad, fotografías y privacidad

El visitante futuro deberá identificarse con una sesión o mecanismo equivalente; el alumno y docente necesitarán cuentas/sesiones verificables. Elegir un alias no bastará. Las fotografías deberán aceptar solo tipos permitidos (inicialmente JPEG/PNG/WebP), con límite de tamaño definido antes de activar cargas, nombre interno aleatorio, comprobación MIME real, consentimiento de uso para el encargo y eliminación a petición o al vencer la retención. Se almacenarán fuera de `app/static` y se entregarán tras autorización; nunca se mostrarán en catálogo.

## Transiciones previstas

El solicitante crea en `received`. Participantes autorizados pueden iniciar conversación y pasar a `in_conversation`; el destinatario puede proponer `accepted`; el destinatario o docente puede marcar `completed`; el solicitante o docente puede pedir `cancelled`, sujeto a una regla que aún debe concretarse. El docente asigna manualmente figuras personalizadas; esta decisión es revisable.


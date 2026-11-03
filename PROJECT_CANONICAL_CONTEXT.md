# Contexto canónico

## Arquitectura y dominio

- Una aplicación FastAPI con Jinja2, CSS/JavaScript local, SQLAlchemy, Alembic y SQLite local; Python 3.12. `cartel.jpg` es referencia visual y se conserva. Los ocho creadores, cinco productos y precios son ficticios.
- Una solicitud de producto se dirige al creador obtenido en el servidor. Una figura personalizada queda sin destinatario hasta que el docente la asigna manualmente; puede reasignarla. La solicitud y su primer mensaje se guardan juntos. Las ofertas son céntimos enteros y no implican pago.
- Roles `visitor`, `student`, `teacher`; alias visible no acredita identidad. Creadores y docente usan credenciales individuales con hash y sesiones revocables. Visitante usa sesión y enlace privado de recuperación de un solo uso. Las solicitudes anteriores a la identificación siguen sin acceso recuperable para el visitante y no se reclaman por alias.
- El docente ve todos los encargos; el creador solo los asignados; el visitante solo los propios recuperables. Toda lectura, respuesta y asignación comprueba permiso en el servidor. Los POST tienen CSRF. Los mensajes tienen autor y fecha. Una respuesta puede pasar el estado interno de `received` a `in_conversation`; la lectura no cambia el estado. Los demás estados previstos (`accepted`, `completed`, `cancelled`) no tienen todavía flujo de interfaz.

## Avisos y lectura

- La migración `0006_order_reads` conserva el historial e inicializa un corte técnico de mensajes previos como leídos para quienes ya tenían acceso, sin inventar fecha histórica ni reasignar encargos. `order_reads` guarda por usuario y encargo último ID mostrado y versión de asignación vista.
- El servidor entrega un corte firmado, ligado a usuario, encargo y mensaje efectivamente entregado. El navegador lo confirma por POST con CSRF; si falla, puede repetir el mismo corte aunque los mensajes ya estén en pantalla. Un mensaje posterior no queda leído por ese intento. Mensajes propios no generan novedad. El docente recibe un solo aviso por conversación para figuras sin asignar o mensajes ajenos; el creador recibe «Nueva para ti» por asignación sin que todo el historial cuente como nuevo.
- El panel y el sondeo comparten la plantilla de tarjeta. El endpoint privado devuelve todos los encargos autorizados y sus avisos; el cliente añade o retira tarjetas sin recarga. Sondeo cada 10 s configurable, solo en pestaña visible y con sesión; no hay WebSockets, correo ni push.

## Fotografías: función retirada

La microfase 4 permitió subir fotografías, pero la decisión vigente retira por completo controles, vistas y rutas de subida, lectura y eliminación. Los adjuntos y aceptaciones previos, sus archivos privados fuera de `static` y todas las migraciones se conservan sin acceso desde la aplicación. El formulario de figura pide solo alias y descripción. Después de asignar al creador, las partes acordarán por otro canal la entrega de imágenes. La web recuerda que se requieren derechos o autorización de uso y permiso expreso de la persona representada; para menores interviene su representante legal. No se solicitan documentos de identidad.

La apariencia fue aprobada por el usuario. También confirmó manualmente el intercambio de mensajes, asignación/reasignación y pérdida de acceso del creador anterior, además de la antigua función de fotos. Esto es distinto de las pruebas automatizadas y de la posterior revisión en Chrome con datos aislados. Punto de control previo: `6f5116c`, etiqueta `v0.1.0-demo-local`.

## Pendientes

Antes de uso público: endurecer acceso (incluida limitación de intentos), política de retención y tratamiento de datos históricos, gestión operativa de credenciales y recuperación, HTTPS y pruebas con PostgreSQL real. Se preparó el destino GitHub → Render + Neon: Psycopg 3, Python 3.12, URL por entorno para Alembic, guardas de TLS y secreto en producción, y arranque con migración y carga idempotente. Render Free no ofrece predeploy; el script lo hace antes de iniciar Uvicorn. No se ha desplegado ni probado contra Neon. Cuentas, encargos, mensajes y sesiones deben permanecer en PostgreSQL, nunca en el disco temporal de Render. Véase [docs/despliegue-opcion.md](docs/despliegue-opcion.md).

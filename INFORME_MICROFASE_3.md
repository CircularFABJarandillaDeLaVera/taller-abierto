# Informe de la microfase 3 — Taller Abierto

## Funcionalidades implementadas

- Acceso individual para creadores y docente mediante contraseñas con hash PBKDF2-HMAC-SHA256 y sesiones revocables de 12 horas.
- Sesión de navegador para el visitante y recuperación mediante un enlace privado de un solo uso, válido durante 48 horas. El alias escrito no acredita identidad.
- Paneles separados: el visitante ve sus solicitudes, cada creador ve solo las que tiene asignadas y el docente ve todas, incluidas las anteriores a esta fase.
- Mensajes persistidos con autor y fecha, respuesta desde el detalle y actualización mediante recarga. El texto se muestra escapado.
- Asignación y reasignación docente de figuras personalizadas. Al reasignar, el creador anterior pierde acceso.
- Permisos comprobados en cada lectura y operación; formularios POST protegidos con CSRF y cookies HttpOnly, SameSite y Secure cuando corresponde a producción.
- Migración `0004_identity` aplicada sin borrar datos: las dos solicitudes preexistentes se conservaron y no pueden reclamarse por coincidencia de alias.

## Pruebas ejecutadas

Antes de editar pasaron las 6 pruebas existentes. Después pasaron **7 de 7 pruebas** con:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=data\pytest-phase3-verified
```

Se comprobaron inicio y cierre de sesión, credenciales erróneas, caducidad, CSRF, acceso cruzado entre creadores y visitantes, asignación exclusiva del docente, pérdida de acceso tras reasignación, recuperación de un solo uso, texto escapado y persistencia de mensajes y asignación al reabrir SQLite. La compilación sintáctica también terminó correctamente. Hubo una advertencia de deprecación de Starlette, sin fallos de prueba. La base de trabajo quedó en la revisión `0004_identity` y conserva dos solicitudes anteriores con acceso de visitante deshabilitado.

Estas verificaciones fueron pruebas HTTP automatizadas; no se realizó inspección visual real en navegador.

## Preparación y arranque local

Desde la raíz de WebIES, con `.venv` activado:

```powershell
alembic upgrade head
python -m app.seed
python -m app.provision luna_taller --role student
python -m app.provision norte_creativo --role student
python -m app.provision docente_demo --role teacher
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Cada comando de provisionamiento solicita una contraseña de forma interactiva. Para probar otros creadores, repetirlo con su alias y `--role student`. No se han provisionado credenciales reales en la base de trabajo durante esta microfase.

## Recorrido de los tres roles

La portada local es `http://127.0.0.1:8000/`. Usar únicamente datos ficticios y sesiones de navegador separadas.

1. **Visitante:** abrir `http://127.0.0.1:8000/productos/figura-personalizada-3d` o `http://127.0.0.1:8000/figura-personalizada`, enviar una solicitud y guardar de forma privada el medio de recuperación mostrado una sola vez en la confirmación. Abrir `/panel`, leer el seguimiento, responder y cerrar sesión. Recuperar el acceso con el medio guardado.
2. **Creador:** abrir `http://127.0.0.1:8000/entrar` en otra sesión, entrar con su alias y la contraseña provisionada, abrir `/panel`, seleccionar un encargo asignado y responder. Usar «Actualizar» para ver mensajes nuevos.
3. **Docente:** abrir `/entrar` en una tercera sesión con el alias docente provisionado, entrar en `/panel`, revisar solicitudes y seleccionar una figura personalizada para asignarla a un creador. Puede cambiar la asignación y comprobar que solo el nuevo destinatario tiene acceso.

## Limitaciones y siguiente paso

La demo permanece restringida a pruebas locales con datos ficticios. Antes de un despliegue público faltan HTTPS y configuración segura de producción, limitación de intentos de acceso, gestión formal de cuentas y recuperación, política de conservación de datos y controles para fotografías. No hay WebSockets, IA, pagos ni subida de archivos.

El siguiente paso es la revisión visual y funcional de los tres recorridos con sesiones reales separadas en escritorio y móvil, seguida del endurecimiento de los puntos anteriores antes de considerar una publicación.

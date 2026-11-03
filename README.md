# Taller Abierto

Taller Abierto será una demo de escaparate y gestión de encargos para ocho jóvenes del ciclo de Comercio y Marketing. Su valor diferencial frente a un catálogo sencillo es que prepara la conversación, el destinatario del encargo y su seguimiento; no es una tienda ni una web oficial del centro.

## Fases 0 a 5

La aplicación incluye catálogo educativo, solicitudes, paneles privados, conversación por recarga y fotografías privadas para figuras personalizadas. Creadores y docente entran con contraseña individual; el visitante usa sesión de navegador y un enlace privado de recuperación.

Se ha inspeccionado `cartel.jpg` y se conserva el original. La interfaz usa sus referencias cromáticas (azul marino, verde, blanco y acentos amarillo/naranja), sin usar el cartel como fondo ni crear logotipos.

La microfase 5 renueva la portada, el catálogo y las fichas con ilustraciones SVG locales de ejemplo, y mejora la lectura de paneles y conversaciones. No modifica los datos ni los permisos. Las capturas de revisión visual con datos ficticios están en `docs/capturas/`; se generan de nuevo, en una base aislada, con `.\.venv\Scripts\python.exe scripts\visual_review.py` si hay Chrome instalado en la ruta indicada por el script.

## Carga del catálogo de ejemplo

Con la base migrada, ejecutar:

```powershell
python -m app.seed
```

El comando crea ocho creadores y cinco productos solo si faltan, usando alias y `slug` estables. Puede repetirse sin duplicar ni borrar datos ajenos.

## Preparación local

Se ha elegido Python 3.12 (comprobado en el entorno: 3.12.10). En PowerShell, desde esta carpeta:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
New-Item -ItemType Directory -Force data | Out-Null
alembic upgrade head
uvicorn app.main:app --reload
```

Abrir `http://127.0.0.1:8000/` y comprobar `http://127.0.0.1:8000/health`. Las pruebas se ejecutan con `python -m pytest tests -q -p no:cacheprovider` y usan bases temporales. `pytest.ini` limita la búsqueda de pruebas a `tests/`, sin explorar `data/`.

Rutas principales: `/catalogo`, `/productos/figura-personalizada-3d` y `/creadores`. Las ilustraciones son SVG locales marcadas como ejemplos; no son fotografías de alumnos.

## Solicitudes locales de ejemplo

Tras migrar y cargar los ejemplos, abrir `http://127.0.0.1:8000/productos/figura-personalizada-3d` para consultar u ofrecer un importe al creador, o `http://127.0.0.1:8000/figura-personalizada` para describir una figura pendiente de asignación docente. Usar solo alias y contenidos ficticios. Las fotografías se pueden adjuntar al crear la figura o después. El servidor valida campos y CSRF, guarda solicitud y mensaje inicial en una transacción y redirige a una confirmación que muestra una sola vez el enlace privado de recuperación. Los importes se guardan como céntimos enteros; una oferta no es pago ni compra.

Comprobación: `python -m pytest tests -q -p no:cacheprovider`.

## Tres roles en local

Desde la raíz del proyecto, con `.venv` activado:

```powershell
alembic upgrade head
python -m app.seed
python -m app.provision luna_taller --role student
python -m app.provision norte_creativo --role student
python -m app.provision docente_demo --role teacher
uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

El comando solicita y confirma la contraseña sin mostrarla ni guardarla en archivos del proyecto. Repetirlo renueva el hash y revoca sesiones existentes. Provisionar individualmente los demás creadores con su alias si se van a probar. Contraseñas: PBKDF2-HMAC-SHA256 con sal aleatoria y 600 000 iteraciones; sesiones y recuperación: tokens aleatorios de alta entropía guardados solo como huellas SHA-256.

1. Visitante: abrir `http://127.0.0.1:8000/productos/figura-personalizada-3d` o `/figura-personalizada`, enviar datos ficticios, guardar el enlace privado que aparece una vez en la confirmación y entrar en `/panel`. Cerrar sesión desde el panel; abrir el enlace guardado y pulsar «Continuar» para recuperar la conversación. El enlace dura 48 horas y se consume al usarlo.
2. Creador: en otra sesión de navegador, abrir `/entrar` con su alias y contraseña; `/panel` muestra sus encargos asignados. Abrir uno, responder y actualizar la página.
3. Docente: en otra sesión, abrir `/entrar` con `docente_demo`; `/panel` muestra todos los encargos, incluidos los anteriores. En una figura personalizada, elegir creador y guardar la asignación. Se permite reasignar; el creador anterior pierde acceso.

La sesión dura 12 horas y se revoca al cerrar sesión. Las solicitudes anteriores a la migración 0004 permanecen visibles al docente, pero no son reclamables por alias. Cada lectura, respuesta y asignación comprueba permisos en el servidor. Los formularios POST usan CSRF; cookies HttpOnly, SameSite y Secure cuando `APP_ENV=production`. Para ejecutar la suite: `python -m pytest tests -q -p no:cacheprovider`.

## Fotografías privadas de figuras

Instalar la nueva dependencia desde `requirements.txt` y migrar:

```powershell
python -m pip install -r requirements.txt
alembic upgrade head
```

En `/figura-personalizada` se pueden adjuntar hasta tres JPG/PNG de 5 MB cada una, o enviar la solicitud sin archivos. En `/panel/solicitudes/{id}` las personas autorizadas pueden añadir fotos después, hasta tres activas en total. Cada lote exige por separado la declaración de derechos y el permiso de la persona representada; la fecha, versión del texto y usuario aceptante quedan vinculados a los adjuntos de ese lote. El docente debe revisar la autorización correspondiente cuando aparezca un menor; marcar las casillas no sustituye esa revisión. Publicar las imágenes en catálogo o redes exigiría otra autorización.

Los archivos se guardan con nombres aleatorios en `ATTACHMENTS_DIR` (por defecto `./private_uploads`, fuera de `app/static` y excluido de Git). Se decodifican, se limitan a 6000 píxeles por lado y 20 millones de píxeles, se orientan y se vuelven a guardar sin EXIF. La petición multipart completa se limita a 16 MB. Solo solicitante, creador actualmente asignado y docente pueden abrir la URL privada de una foto; solicitante y docente pueden eliminarla. Al eliminar, el archivo se mueve primero a cuarentena privada, se quita el registro activo y luego se borra físicamente. Si falla el movimiento inicial, se conserva registro y archivo; si falla el borrado final, queda un archivo en cuarentena `.deleting` que requiere limpieza administrativa, sin acceso público. Se conserva solo la trazabilidad mínima de la aceptación.

Esta demo todavía no debe exponerse públicamente: faltan HTTPS y despliegue seguro, limitación de intentos de acceso, gestión formal de cuentas, retención de datos y revisión de permisos de menores. No hay WebSockets, pagos ni IA.

## Estado y límites

Los datos son ficticios. No hay pagos, carrito, stock, IA, WebSockets ni despliegue. La identidad y los permisos por participante funcionan en local; todavía faltan controles operativos antes de exponer conversaciones o encargos públicamente. La situación real y el siguiente paso están en [ESTADO.md](ESTADO.md); las decisiones ampliadas están en [PROJECT_CANONICAL_CONTEXT.md](PROJECT_CANONICAL_CONTEXT.md).


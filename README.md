# Taller Abierto

Demo educativa de escaparate y encargos para ocho creadores ficticios del ciclo de Comercio y Marketing. No es una tienda ni una web oficial del instituto. Cinco productos de ejemplo tienen precios orientativos. La apariencia toma colores de `cartel.jpg`, que se conserva intacto.

## Funciones actuales

- Catálogo, fichas y creadores; consulta u oferta a partir de un producto.
- Solicitud de figura personalizada con alias y descripción, pendiente de asignación docente. Las fotografías se acordarán después con el creador por otro canal. La aplicación ya no admite subirlas, verlas ni eliminarlas.
- Acceso individual de creadores y docente; sesión del visitante y enlace privado de recuperación de un solo uso. Paneles, asignación o reasignación docente y conversación privada con CSRF.
- Avisos dentro de la web y lectura por persona. «Mi espacio» cuenta conversaciones con novedades. «Nueva para ti» y «Nueva sin asignar» son distintos de mensajes nuevos. Las consultas no marcan lectura; el navegador confirma el corte de mensajes mostrados. Si falla, puede reintentarlo. El estado del encargo no cambia al abrirlo.

Los avisos se consultan cada 10 segundos mientras haya una sesión válida y la pestaña esté visible. `POLL_SECONDS` permite entre 5 y 120 segundos. No hay avisos con la web cerrada, correo, push, WebSockets ni sonido.

## Instalación local

Python 3.12. Desde la raíz WebIES en PowerShell:

```powershell
if (-not (Test-Path .venv)) { py -3.12 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
New-Item -ItemType Directory -Force data | Out-Null
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Abrir `http://127.0.0.1:8000/`; salud en `/health`. `app.seed` puede repetirse sin duplicar el catálogo ni borrar datos ajenos. Si ya existe `.env` o la base, conservarlos. Alembic aplica solo migraciones pendientes. La revisión 0006 inicializa los mensajes anteriores como leídos para quienes tenían acceso; no modifica encargos, mensajes ni adjuntos.

Para preparar accesos de demo, ejecutar por separado y elegir contraseñas privadas cuando el comando las solicite:

```powershell
.\.venv\Scripts\python.exe -m app.provision luna_taller --role student
.\.venv\Scripts\python.exe -m app.provision docente_demo --role teacher
```

Repetir el primer comando para otros alias de creadores si se necesitan. Provisionar de nuevo revoca sesiones anteriores de esa cuenta. Nunca registrar contraseñas ni enlaces de recuperación en capturas o informes.

## Recorridos

1. Visitante: abrir `/productos/figura-personalizada-3d` para consultar al creador o `/figura-personalizada` para describir la idea. Usar datos ficticios. Tras enviar, guardar en privado el enlace de recuperación que aparece una vez. La figura queda sin asignar. `/panel` muestra sus encargos; después puede cerrar sesión y recuperar el acceso con el enlace.
2. Creador: en otro perfil de navegador, entrar en `/entrar` y abrir `/panel`. Solo ve sus solicitudes. Puede leer y responder; al reasignar una figura, el antiguo creador pierde acceso y su tarjeta.
3. Docente: en otro perfil, entrar en `/entrar`, revisar `/panel` y asignar una figura desde su detalle. Ve las solicitudes sin asignar y las novedades propias.

Las sesiones duran 12 horas y se pueden revocar. Los enlaces de recuperación duran 48 horas y se consumen una vez. Las solicitudes anteriores a la identificación de visitantes no se reclaman por coincidencia de alias. La oferta es orientativa y no implica pago ni compra.

## Comprobaciones

Las pruebas usan bases y carpetas temporales. Para aislar también la configuración de entorno al ejecutarlas en PowerShell:

```powershell
$testRoot = Join-Path $env:TEMP ('ta-suite-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot | Out-Null
$env:DATABASE_URL = 'sqlite:///' + (Join-Path $testRoot 'isolated.db').Replace('\','/')
$env:ATTACHMENTS_DIR = Join-Path $testRoot 'private'
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp (Join-Path $testRoot 'pytest')
node --check app/static/notifications.js
```

Chrome instalado en la ruta indicada por el script permite revisar dos sesiones ficticias y guardar capturas en una carpeta ignorada por Git, con una base aislada:

```powershell
.\.venv\Scripts\python.exe scripts\phase6_browser_review.py
```

## Datos históricos y límites

La antigua función de fotografías se retiró de la interfaz y de todas sus rutas. Los adjuntos y aceptaciones previos, sus archivos privados y las migraciones se conservan sin acceso desde la aplicación. `ATTACHMENTS_DIR` sigue describiendo dónde están los archivos históricos, fuera de `static` y de Git. No moverlos ni eliminarlos como parte de la actualización. Antes de enviar imágenes por otro canal se requieren derechos o autorización de uso y permiso expreso de la persona representada; para menores debe intervenir su representante legal.

El proyecto sigue limitado a uso local con datos ficticios. Se preparó el controlador PostgreSQL, la lectura de `DATABASE_URL` en Alembic, el arranque de Render y las comprobaciones de configuración; **no se ha desplegado ni probado contra PostgreSQL real**. Para abrirlo públicamente faltan endurecimiento de acceso, retención de datos y verificación de la conexión Render–Neon. El objetivo es GitHub → Render con PostgreSQL externa en Neon. [Estado](ESTADO.md), [decisiones](PROJECT_CANONICAL_CONTEXT.md) y [pasos de despliegue](docs/despliegue-opcion.md).

# Informe de microfase 6 — avisos y retirada de fotografías

## Resultado

`order_reads` guarda un corte por persona y conversación. Los mensajes propios no generan avisos, las consultas no marcan lectura y abrir HTML no cambia el estado del encargo. El servidor firma un corte para los mensajes entregados a ese usuario y conversación; el POST con CSRF confirma hasta ese punto. El navegador guarda por separado último mensaje recibido y último corte confirmado. Ante fallo de confirmación ofrece reintentar el mismo corte, sin reclamar como leído ningún mensaje posterior.

«Mi espacio» cuenta conversaciones con novedades. El docente ve «Nueva sin asignar» y mensajes ajenos sin duplicar la conversación; el creador ve «Nueva para ti» cuando se le asigna una figura y el historial anterior se trata como contexto. Al reasignar pierde acceso el antiguo creador. Las tarjetas se renderizan desde la misma plantilla en el panel y en el sondeo; se añaden encargos recién visibles y se retiran los no autorizados, sin recargar ni perder borradores. El sondeo es privado, cada 10 segundos por defecto (`POLL_SECONDS`, 5–120), solo con sesión válida y pestaña visible. Retrocede ante errores y no roba el foco.

Se retiró la función de fotografías: no hay selector, vista previa, casillas ni galería. Las rutas previas de subida, lectura y borrado responden 404, incluso por petición directa; `/figura-personalizada` rechaza multipart con 415. Solo se pide alias y descripción. El texto indica que, una vez asignado un creador, acordarán la entrega por otro canal y recuerda derechos de uso, permiso expreso de imagen e intervención del representante legal para menores. Registros históricos, archivos privados y migraciones no se han borrado y ya no se ofrecen por HTTP.

## Historial y datos

La revisión 0006 inicializó los mensajes anteriores como leídos para quienes ya tenían acceso. Es una inicialización técnica, sin fecha histórica inventada. No asignó figuras ni cambió contenido. Antes de aplicarla se creó una copia privada excluida de Git. La comprobación anterior a esta reparación registró 13 usuarios, 4 encargos, 12 mensajes, 1 adjunto, 1 aceptación, 4 sesiones y 10 cortes; comparación exacta de las tablas previas con la copia. En esta reparación no se migró ni escribió sobre la base de trabajo.

## Comandos

Desde WebIES, en PowerShell, para instalación o migración local **solo si falta una revisión** y arranque:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Pruebas con entorno temporal aislado:

```powershell
$testRoot = Join-Path $env:TEMP ('ta-suite-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot | Out-Null
$env:DATABASE_URL = 'sqlite:///' + (Join-Path $testRoot 'isolated.db').Replace('\','/')
$env:ATTACHMENTS_DIR = Join-Path $testRoot 'private'
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp (Join-Path $testRoot 'pytest')
node --check app/static/notifications.js
.\.venv\Scripts\python.exe scripts\phase6_browser_review.py
```

El script de navegador crea su propia base y perfiles ficticios en `data/phase6-browser-*`, excluidos de Git.

## Verificaciones y alcance

Antes del arreglo, la suite de fase 6 había dado **12 passed** y Chrome había revisado tres sesiones con la antigua función de fotos. Esos resultados son históricos. Después del arreglo, la suite completa dio **12 passed, 1 warning** (deprecación Starlette/AnyIO) y `node --check` pasó. Las pruebas HTTP verificaron corte, reintento idempotente, CSRF, lectura independiente, mensajes propios, asignación y reasignación, pérdida de acceso, recuperación del visitante, persistencia, migración y conservación de adjuntos sin rutas públicas. Una prueba de portada se aisló de la base de trabajo.

En Chrome real, dos perfiles y base ficticia: visitante envió consulta; creador recibió tarjeta y aviso sin recarga, respondió; visitante móvil recibió aviso, mostró respuesta y conservó el borrador. Se simuló un fallo al guardar lectura; apareció «Reintentar lectura», el corte recibido quedó por delante del confirmado y el contador se limpió tras repetir. Se comprobó que el formulario móvil no tiene controles de fotos, conserva la descripción y no desborda horizontalmente. Capturas finales en `data/phase6-browser-20261103-164554/`; no contienen encargos de trabajo. No se repitió la inspección completa de todas las páginas ni una prueba manual de tres perfiles después de esta retirada.

## Prueba manual con encargos existentes

1. Abrir `/panel` con perfiles separados de visitante, creador y docente, sin registrar aquí contraseñas ni enlaces privados. El sondeo funciona mientras la web esté abierta.
2. Desde una conversación autorizada, responder como visitante. En el panel del creador, esperar hasta 10 segundos: debe aparecer «N mensajes nuevos». Abrir la conversación y comprobar que desaparece el aviso de ese creador.
3. Responder como creador con la conversación del visitante abierta y un borrador escrito. Pulsar «Ver mensajes nuevos»; debe aparecer la respuesta sin perder el borrador. La lectura del visitante no debe alterar la del docente.
4. Como docente, asignar o reasignar una figura. El nuevo creador debe ver «Nueva para ti»; el anterior debe perder tarjeta y acceso por URL directa. La historia previa no debe presentarse como mensajes nuevos.
5. En `/figura-personalizada` comprobar que solo se pide alias y descripción. En un detalle de figura no debe haber selector ni galería; las rutas antiguas de fotos no deben funcionar.

## Límites y siguiente paso

No hay avisos con la web cerrada, correo, push, WebSockets, IA ni pagos. La demo sigue siendo local. Antes de exponerla públicamente faltan seguridad operativa, política de datos y adaptación de SQLite a PostgreSQL persistente. Objetivo de despliegue futuro: GitHub → Render + Neon; aún no se ha preparado. No se desplegó ni se hizo commit o push.

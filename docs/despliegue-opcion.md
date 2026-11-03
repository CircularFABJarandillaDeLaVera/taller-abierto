# Preparación de despliegue: GitHub → Render + Neon

Estado: **preparado en código, sin publicar**. No se ha creado ningún servicio, remoto ni base externa; la SQLite de trabajo y sus fotografías históricas siguen locales. La revisión manual del usuario de la microfase 6 sigue pendiente.

## Decisiones técnicas

- Render: un Web Service Python 3, plan Free, código desde GitHub. `.python-version` fija la rama 3.12; Render admite ese archivo. Build: `pip install -r requirements.txt`. Start: `sh scripts/start_render.sh`. Salud: `/health`. La documentación oficial usa Uvicorn con `0.0.0.0` y `$PORT`; el script hace eso. [FastAPI en Render](https://render.com/docs/deploy-fastapi), [versión de Python](https://render.com/docs/python-version).
- Neon: PostgreSQL externa, con URL de conexión **directa** y TLS. En la variable privada `DATABASE_URL` de Render, cambiar solo el prefijo que entrega Neon de `postgresql://` a `postgresql+psycopg://`, conservando el resto y `sslmode=require` o un modo TLS más estricto. El controlador declarado es Psycopg 3. La aplicación acepta también el prefijo original y lo normaliza; Alembic utiliza la variable de entorno. No pegar una URL real en Git, capturas ni informes. [Conexión segura en Neon](https://neon.com/blog/oops-proof-your-vibe-code-with-neon-because-mistakes-happen), [dialecto Psycopg de SQLAlchemy](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html).
- `scripts/start_render.sh` valida `APP_ENV=production`, `DATABASE_URL` PostgreSQL con TLS y una `SECRET_KEY` privada de al menos 32 caracteres; después ejecuta `alembic upgrade head`, `python -m app.seed` y Uvicorn. Las migraciones y la carga de ejemplo son repetibles. Render Free no dispone de comando predeploy, de modo que se hacen antes de aceptar tráfico en cada arranque. [Secuencia de despliegue de Render](https://render.com/docs/deploys), [limitaciones Free](https://render.com/docs/free).
- Cuentas, encargos, mensajes, sesiones, enlaces de recuperación y cortes de lectura permanecen en PostgreSQL, no en el disco temporal de Render. Las cookies siguen siendo HttpOnly y SameSite; `APP_ENV=production` activa Secure. La fotografía está retirada: no hay rutas de subida o lectura y los archivos históricos no se trasladan a Render.

## Variables privadas en Render

| Variable | Preparación |
| --- | --- |
| `APP_ENV` | `production` |
| `DATABASE_URL` | URL **directa** de Neon, con TLS y controlador `postgresql+psycopg` |
| `SECRET_KEY` | Valor aleatorio privado, estable entre reinicios; mínimo 32 caracteres |
| `POLL_SECONDS` | Opcional; `10` por defecto |
| `APP_NAME` | Opcional; `Taller Abierto` por defecto |

`PORT` lo proporciona Render. No configurar `ATTACHMENTS_DIR` para el alojamiento: es legado local sin función de fotos. Usar la sección **Environment** de Render para secretos; `.env.example` conserva solo marcadores locales. [Variables y secretos en Render](https://render.com/docs/configure-environment-variables).

## Pasos que realizará el equipo

1. Revisar manualmente la microfase 6 y este código, y crear el commit bloqueado en el entorno del agente. Antes de publicar en GitHub, revisar también los cambios de preparación de despliegue; no subir `.env`, `data/`, `private_uploads/` ni capturas. Crear un repositorio privado en GitHub y hacer el primer push cuando se autorice. No hay remoto configurado por el agente.
2. Crear un proyecto **Free** en Neon, elegir una región razonable respecto de Render y copiar la URL directa de conexión. Guardarla fuera del repositorio. Verificar la oferta Free vigente en la consola antes de usarla; los límites pueden cambiar. [Neon Free, actualización de octubre de 2026](https://neon.com/blog/neon-free-plan-1-gb-per-project).
3. Conectar el repositorio en Render y crear un Web Service **Free**. Elegir Python, raíz del repositorio, build `pip install -r requirements.txt`, start `sh scripts/start_render.sh`, health `/health` y, para revisar el primer lanzamiento, desactivar el autodespliegue si la interfaz ofrece esa opción. Añadir las variables privadas antes de iniciar el servicio. Render entregará una URL `onrender.com` con HTTPS. [Crear servicio web](https://render.com/docs/web-services).
4. Después de verificar que migraciones y catálogo arrancan, provisionar por separado las cuentas de docente y creadores en **la base Neon**, desde una terminal local con la URL en una variable de entorno temporal. No usar la base SQLite de trabajo ni copiar credenciales locales. `python -m app.provision <alias> --role teacher` y `--role student` solicitan la contraseña sin escribirla en el repositorio. Limpiar la variable al terminar. Probar los tres roles con datos ficticios antes de compartir la URL.

Para provisionar sin escribir la URL en archivos ni en la línea de comandos (PowerShell, con el entorno instalado):

```powershell
$neonUrl = Read-Host 'URL directa de Neon' -AsSecureString
$env:DATABASE_URL = [System.Net.NetworkCredential]::new('', $neonUrl).Password
.\.venv\Scripts\python.exe -m app.provision docente_demo --role teacher
.\.venv\Scripts\python.exe -m app.provision luna_taller --role student
Remove-Item Env:DATABASE_URL
```

El comando local debe ejecutarse tras instalar `requirements.txt`, que ahora declara Psycopg. Si Neon entrega `postgresql://`, la aplicación lo adapta a Psycopg 3; la URL debe conservar `sslmode=require`. No copiar datos locales por defecto: el catálogo se carga de modo reproducible en la base nueva.

## Límites y verificaciones pendientes

Render Free suspende el servicio tras 15 minutos sin tráfico y su sistema de archivos es efímero; el primer acceso puede tardar en reactivarlo. La aplicación no guarda datos nuevos en ese disco. El plan Free puede limitar horas, ancho de banda y tráfico saliente hacia Neon; confirmar condiciones vigentes antes de publicar. [Limitaciones de Render Free](https://render.com/docs/free).

Se compiló el esquema SQLAlchemy para el dialecto PostgreSQL, se generó sin conexión el SQL de Alembic hasta `0006_order_reads`, se verificó la configuración y se ejecutó la suite SQLite aislada (**15 passed**). **No se ha ejecutado Alembic contra PostgreSQL real ni probado la conexión Render–Neon**; eso requiere un proyecto Neon de prueba y autorización para crear servicios. El entorno impidió instalar Psycopg desde la red, así que también queda pendiente verificar el controlador instalado en Render. Antes de abrir acceso público siguen pendientes limitación de intentos, gestión de cuentas y retención de datos. Tampoco se han probado tráfico real, disponibilidad ni condiciones legales del alojamiento. No se prometen plazos ni costes.

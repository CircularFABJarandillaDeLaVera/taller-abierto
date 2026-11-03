# Informe de la microfase 5 — apariencia y textos

## Resultado

La portada presenta «Tu idea. Nuestra próxima creación» con accesos a creaciones y figura personalizada. En escritorio y móvil se alcanzan a ver productos en la primera pantalla. El catálogo muestra imágenes grandes sobre fondos suaves; las cinco ilustraciones SVG son locales, más detalladas y marcadas como ejemplos. La sección «Un regalo que se parece a ti» explica referencia, propuesta y pieza sin sugerir generación automática. Se mantienen los productos, creadores y textos de la base de datos.

Los paneles muestran «Mis encargos», «Solicitudes recibidas» o «Gestionar encargos», según el rol. Las tarjetas indican número, tipo, producto, cliente, creador, última actividad y un estado legible en español. «Nueva solicitud» corresponde al estado interno `received`; «En conversación», a `in_conversation`. En el detalle, los mensajes identifican autor y fecha. El mapeo de estados está centralizado en `app/presentation.py`; el valor persistido no cambia.

Los formularios, permisos de fotografía, sesiones, asignación y almacenamiento siguen con su comportamiento anterior. Las casillas de derechos y permiso de imagen conservan su validación y su estilo específico. No se añadieron notificaciones, seguimiento de lectura, WebSockets ni IA.

## Comprobaciones

Antes de editar: **10 passed, 1 warning**. Después: **10 passed, 1 warning**, con:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp=data\pytest-phase5-final
```

La advertencia procede de la deprecación `anyio.abc.BlockingPortal` en Starlette. Dos pruebas que buscaban rótulos antiguos se ajustaron a los nuevos textos; sus verificaciones funcionales permanecen.

Se inspeccionó Chrome real en local mediante `scripts/visual_review.py`, con base y sesiones ficticias separadas. Las 13 capturas están en [`docs/capturas/`](docs/capturas/): portada y catálogo en escritorio y móvil; producto en escritorio y móvil; solicitud móvil; acceso escritorio; panel docente, creador y visitante; conversación en escritorio y móvil. En todas se comprobaron carga de imágenes y ausencia de desbordamiento horizontal. En la solicitud móvil se verificaron ambas casillas visibles y desmarcadas. El texto general y el botón principal alcanzaron contrastes de 10,83:1 y 7,05:1; el foco por teclado mostró contorno sólido de 3 px; un mensaje largo no desbordó la conversación móvil.

Para repetir la revisión visual en este equipo:

```powershell
.\.venv\Scripts\python.exe scripts\visual_review.py
```

El script usa `data/phase5-visual.db` y Chrome local; no toca la base de trabajo. No se realizó una auditoría integral de accesibilidad ni se enviaron formularios manualmente durante esta microfase. La suite HTTP cubre los recorridos funcionales existentes. Las capturas usan datos ficticios y no contienen credenciales ni enlaces de recuperación.

Se consultaron las páginas de [Areaware](https://www.areaware.com/es), [ban.do](https://www.bando.com/) y [Ugmonk](https://ugmonk.com/) para la presentación de objetos. La herramienta web permitió consultar contenido y estructura, pero no inspeccionar de forma fiable todos sus detalles visuales. No se copiaron marcas, fotos, textos ni composiciones completas. `cartel.jpg` se inspeccionó y permanece intacto.

## Archivos principales

- `app/static/styles.css`, `app/static/illustrations/*.svg`, `app/templates/`: composición, imágenes y textos.
- `app/presentation.py`, `app/templating.py`: estados y fecha de actividad para las plantillas.
- `scripts/visual_review.py`, `docs/capturas/`: revisión en navegador y referencias visuales con datos ficticios.
- `ESTADO.md` y este informe: situación y resultados.

## Estado y siguiente paso

La demo sigue siendo local y usa datos ficticios. Queda pendiente la revisión de apariencia por el equipo y el endurecimiento necesario antes de publicarla. La siguiente microfase propuesta es definir y, si se justifica, implementar notificaciones y seguimiento de lectura con permisos y criterios de aceptación explícitos. No se ha empezado esa microfase. No se desplegó, ni se hizo commit o push.

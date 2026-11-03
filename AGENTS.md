# Instrucciones de trabajo

- La raíz única es `C:\Users\circularfab\Documents\WebIES`; no crear proyectos hermanos ni escribir fuera de ella.
- Conservar `cartel.jpg` y cualquier trabajo previo. No usarlo como fondo ni presentar el proyecto como web oficial.
- Mantener responsabilidades separadas: configuración, base de datos, modelos, lógica de negocio, rutas, plantillas, estáticos y pruebas.
- Toda regla de permisos, asignación o transición de estado debe poder probarse sin depender de la plantilla.
- No añadir pagos, carrito, stock, proveedores de IA, LangGraph o WebSockets sin una necesidad documentada y una fase explícita.
- No implementar autenticación improvisada: un alias enviado por el navegador no prueba identidad.
- Los adjuntos futuros vivirán fuera de `app/static` y se servirán solo después de comprobar permisos.

## Verificaciones

Desde la raíz: `python -m pytest -q` y, para una base local limpia, `alembic upgrade head`. Antes de entregar cambios, comprobar que `/` responde, `/health` no filtra información sensible y que no se han creado secretos ni bases de datos de trabajo versionables.


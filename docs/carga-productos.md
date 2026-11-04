# Preparar productos del aula

Para las entregas reales se necesitan **dos tipos de archivos**:

1. Una copia de [productos-plantilla.csv](productos-plantilla.csv) rellenada en UTF-8, con una fila por producto. Guárdala como `data/productos-aula.csv`, carpeta ignorada por Git. El campo `artisan_alias` debe ser el alias exacto de un perfil de artesano ya existente; la importación no crea cuentas ni perfiles. Usa un `slug` único y estable, como `lampara-luna-01`. El precio es orientativo: escríbelo con punto decimal, por ejemplo `12.50`.
2. Una fotografía pública por producto dentro de `app/static/products/`, en JPG, PNG o WebP. Escribe en el CSV la ruta relativa `products/nombre-del-archivo.jpg`. Cada archivo debe pesar como máximo 10 MB. No coloques aquí fotografías privadas de encargos. Las imágenes públicas se incorporarán al repositorio y al siguiente despliegue de la web.

Ejemplo de fila ficticia (no forma parte de la plantilla):

```csv
lampara-luna-01,luna_taller,Lámpara de muestra,Pequeña lámpara decorativa,PLA,12.50,products/lampara-luna-01.jpg
```

Las columnas son obligatorias y van en el orden de la plantilla. Si una descripción contiene comas, enciérrala entre comillas dobles. Antes de importar, confirma los alias de los artesanos y revisa los textos y fotografías que se publicarán.

## Validación y carga, cuando lleguen las entregas

Desde la raíz del repositorio, con `DATABASE_URL` apuntando temporalmente a la base elegida:

```powershell
.\.venv\Scripts\python.exe -m app.import_products .\data\productos-aula.csv
.\.venv\Scripts\python.exe -m app.import_products .\data\productos-aula.csv --apply
```

El primer comando **solo valida** CSV, imágenes, alias y conflictos con productos existentes. `--apply` vuelve a validar todo y guarda el lote completo en una transacción. Repetirlo omite los productos idénticos; si un `slug` ya existe con datos distintos, se detiene sin modificarlo. No se borran productos ni se alteran encargos. No introduzcas la conexión ni secretos en el CSV, en Git o en la línea de comandos. Cuando se autorice la carga real, se podrá usar una conexión directa TLS a Neon en una variable de entorno temporal desde el equipo local; el plan gratuito de Render no necesita terminal para esta operación. Publica primero las fotografías estáticas en Render y después ejecuta la importación para que no aparezcan imágenes rotas.

# Organización del taller: preparación de cuentas

Esta fase conserva los valores internos `STUDENT` y `TEACHER` para no convertir ni duplicar cuentas existentes. En pantalla se muestran **Artesano/a** y **Responsable de tienda**. El nuevo valor `ADMIN` se reserva para la cuenta de la persona administradora. Las solicitudes de cliente siguen utilizando acceso privado de visitante; el docente puede actuar como cliente en una ventana privada. No se crean cuentas de cliente para el alumnado.

## Habilitar la cuenta administradora

Esta operación es explícita y se realiza **después de aplicar la migración 0007** en el entorno elegido. Primero hay que identificar el alias exacto y la cuenta propia. No se promueven automáticamente las cuentas `TEACHER` existentes.

1. Si la cuenta propia aún no existe, provisionar **solo ese alias confirmado** como responsable con `python -m app.provision <alias> --role teacher`. El programa pide la contraseña dos veces sin mostrarla. No ejecutar el comando sobre una cuenta existente sin decidir antes que se desea restablecer su acceso.
2. Ejecutar `python -m app.admin_setup <alias>`. El programa muestra ID, alias y rol, y exige escribir una confirmación que incluye el ID. Solo promueve una cuenta responsable activa con contraseña, conserva la contraseña, cierra sus sesiones anteriores y no altera otras cuentas. Si ya existe un administrador, se detiene.
3. Entrar en `/panel`, comprobar el rótulo **Administrador** y abrir **Gestionar accesos**. No hay registro público privilegiado.

Para operar contra Neon desde PowerShell sin cambiar `.env`, usar una conexión **directa** con TLS solo durante el comando. El CLI local está instalado en `.neon-tooling/` y la rama vinculada es `production`:

```powershell
$neonDirect = (& .\.neon-tooling\node_modules\.bin\neon.cmd connection-string production --project-id billowing-night-37089716 --database-name neondb --ssl require --config-dir .neon-tooling\config --no-analytics).Trim()
if ($LASTEXITCODE -ne 0) { throw 'No se obtuvo la conexión de Neon' }
$env:DATABASE_URL = $neonDirect
try {
    # Ejecutar aquí únicamente el comando aprobado para el alias identificado.
    # .\.venv\Scripts\python.exe -m app.provision <alias> --role teacher
    # .\.venv\Scripts\python.exe -m app.admin_setup <alias>
} finally {
    Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    Remove-Variable neonDirect -ErrorAction SilentlyContinue
}
```

No imprimir la conexión, añadirla a Git ni copiar `.env` a Render. Hasta identificar la cuenta administradora y aprobar la operación, no ejecutar esos comandos en Neon.

## Preparar dos responsables y ocho artesanos

En `/panel/cuentas`, el administrador puede crear responsables y artesanos; cada responsable puede crear únicamente artesanos. El servidor comprueba el rol de quien envía cada formulario. Un perfil de artesano existente sin contraseña se **vincula** por su ID: conserva sus productos, encargos y mensajes. Los ocho perfiles de muestra creados por el catálogo pueden utilizarse así, sin duplicarlos. Para un perfil nuevo, elegir un alias único; la interfaz avisa si ya existe. Antes de crear dos responsables, revisar si ya existen cuentas `TEACHER` con los alias previstos y decidir caso por caso si conservarlas, activarlas o restablecerlas.

Cada alta o restablecimiento genera una contraseña aleatoria individual. Solo aparece una vez en la respuesta del gestor y se guarda únicamente su hash. Entregarla directamente a su destinatario por un canal privado; pedirle que use **Cambiar mi contraseña** al entrar. El restablecimiento revoca las sesiones previas. La desactivación también revoca sesiones y se puede revertir sin borrar el perfil ni sus datos. No se muestran contraseñas anteriores.

## Propuesta para una fase posterior

Una ficha de producto podría ofrecer impresión 3D de un color, impresión multicolor y acabado pintado a mano. El modelo futuro deberá distinguir quién **diseña**, quién **fabrica** (incluida una empresa externa) y quién **realiza los acabados**. Los importes de la ficha podrán seguir siendo orientativos y el presupuesto final se acordaría en privado. No se implementan aquí variantes, pagos, comisiones, donativos ni pasarelas. El encaje legal e institucional de estas posibilidades queda pendiente de confirmar; la web no hace afirmaciones al respecto.

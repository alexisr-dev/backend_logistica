from django.db import migrations


def sincronizar(apps, schema_editor):
    """Alinea `is_active` con `activo` en las filas que ya existían.

    A partir de ahora `Usuario.save()` mantiene el espejo, pero sobrescribir
    `save()` no toca las filas ya guardadas: sin esta migración, un usuario dado
    de baja antes del cambio seguiría con `is_active=True` y podría iniciar
    sesión indefinidamente.
    """
    Usuario = apps.get_model("usuarios", "Usuario")
    # `update()` en crudo es correcto aquí: el modelo histórico de la migración
    # no tiene el `save()` sobrescrito, y se están fijando los dos campos a la vez.
    Usuario.objects.filter(activo=False, is_active=True).update(is_active=False)
    Usuario.objects.filter(activo=True, is_active=False).update(is_active=True)


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0002_codigorecuperacion"),
    ]

    operations = [
        migrations.RunPython(sincronizar, reverse_code=migrations.RunPython.noop),
    ]

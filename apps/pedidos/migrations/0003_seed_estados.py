from django.db import migrations

ESTADOS = [
    ("pendiente", "Pendiente", 1),
    ("confirmado", "Confirmado", 2),
    ("en_preparacion", "En preparación", 3),
    ("en_camino", "En camino", 4),
    ("entregado", "Entregado", 5),
    ("cancelado", "Cancelado", 6),
    ("devuelto", "Devuelto", 7),
]


def cargar_estados(apps, schema_editor):
    EstadoPedido = apps.get_model("pedidos", "EstadoPedido")
    for codigo, nombre, orden in ESTADOS:
        EstadoPedido.objects.get_or_create(
            codigo=codigo, defaults={"nombre": nombre, "orden": orden}
        )


def borrar_estados(apps, schema_editor):
    EstadoPedido = apps.get_model("pedidos", "EstadoPedido")
    EstadoPedido.objects.filter(codigo__in=[c for c, _, _ in ESTADOS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0002_initial'),
    ]

    operations = [
        migrations.RunPython(cargar_estados, borrar_estados),
    ]

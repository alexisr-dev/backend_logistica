from django.db import migrations

# La VIEW usa sintaxis específica de PostgreSQL (FILTER, EXTRACT EPOCH, ||).
# Solo se crea cuando el motor es PostgreSQL; en SQLite (tests) se omite.
SQL_CREAR = """
CREATE OR REPLACE VIEW vista_rendimiento_repartidor AS
SELECT
    u.id AS repartidor_id,
    u.nombre || ' ' || u.apellido AS repartidor,
    COUNT(p.id) AS total_entregas,
    COUNT(p.id) FILTER (WHERE p.fecha_entrega_real <= p.fecha_estimada_entrega) AS entregas_a_tiempo,
    COUNT(p.id) FILTER (WHERE p.fecha_entrega_real > p.fecha_estimada_entrega) AS entregas_tardias,
    AVG(EXTRACT(EPOCH FROM (p.fecha_entrega_real - p.fecha_creacion)) / 60) AS tiempo_promedio_min,
    AVG(c.puntuacion) AS calificacion_promedio
FROM usuarios u
JOIN perfiles_repartidor pr ON pr.usuario_id = u.id
LEFT JOIN pedidos p ON p.repartidor_id = u.id
    AND p.estado_id = (SELECT id FROM estados_pedido WHERE codigo = 'entregado')
LEFT JOIN calificaciones c ON c.repartidor_id = u.id
GROUP BY u.id, u.nombre, u.apellido;
"""

SQL_BORRAR = "DROP VIEW IF EXISTS vista_rendimiento_repartidor;"


def crear_vista(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL_CREAR)


def borrar_vista(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL_BORRAR)


class Migration(migrations.Migration):

    dependencies = [
        ('reportes', '0001_initial'),
        ('pedidos', '0003_seed_estados'),
        ('usuarios', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_vista, borrar_vista),
    ]

"""
Corrige un fan-out en `vista_rendimiento_repartidor`.

La versión anterior unía las calificaciones al repartidor en vez de al pedido:

    LEFT JOIN calificaciones c ON c.repartidor_id = u.id

Como esa condición no está atada a `p.id`, cada pedido entregado se multiplicaba
por cada calificación del repartidor. Con 3 entregas y 2 calificaciones la
consulta devolvía 6 filas, así que `total_entregas`, `entregas_a_tiempo` y
`entregas_tardias` salían inflados y `tiempo_promedio_min` quedaba sesgado.

La calificación es 1:1 con el pedido (`calificaciones.pedido_id` es UNIQUE), así
que unir por `c.pedido_id = p.id` elimina la duplicación sin perder datos.
"""
from django.db import migrations

SQL_CORREGIDA = """
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
LEFT JOIN calificaciones c ON c.pedido_id = p.id
GROUP BY u.id, u.nombre, u.apellido;
"""

SQL_ANTERIOR = """
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


def aplicar(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL_CORREGIDA)


def revertir(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL_ANTERIOR)


class Migration(migrations.Migration):

    dependencies = [
        ('reportes', '0002_crear_vista_rendimiento'),
    ]

    operations = [
        migrations.RunPython(aplicar, revertir),
    ]

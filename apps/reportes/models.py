from django.db import models


class RendimientoRepartidor(models.Model):

    repartidor_id = models.BigIntegerField(primary_key=True)
    repartidor = models.CharField(max_length=201)
    total_entregas = models.IntegerField()
    entregas_a_tiempo = models.IntegerField()
    entregas_tardias = models.IntegerField()
    tiempo_promedio_min = models.FloatField(null=True)
    calificacion_promedio = models.FloatField(null=True)

    class Meta:
        managed = False
        db_table = "vista_rendimiento_repartidor"

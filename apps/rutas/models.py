from django.conf import settings
from django.db import models


class Ruta(models.Model):
    class Estado(models.TextChoices):
        PLANIFICADA = "planificada", "Planificada"
        EN_CURSO = "en_curso", "En curso"
        FINALIZADA = "finalizada", "Finalizada"
        CANCELADA = "cancelada", "Cancelada"

    repartidor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="rutas"
    )
    fecha = models.DateField()
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PLANIFICADA)
    distancia_total_km = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    tiempo_estimado_min = models.IntegerField(blank=True, null=True)
    geometria_ruta = models.TextField(blank=True, null=True)  # polyline codificado de OSRM
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rutas"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Ruta {self.id} - {self.repartidor} ({self.fecha})"


class RutaPedido(models.Model):
    class EstadoParada(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        ENTREGADO = "entregado", "Entregado"
        FALLIDO = "fallido", "Fallido"

    ruta = models.ForeignKey(Ruta, on_delete=models.CASCADE, related_name="paradas")
    pedido = models.ForeignKey("pedidos.Pedido", on_delete=models.PROTECT, related_name="paradas")
    orden_parada = models.SmallIntegerField()
    hora_estimada = models.DateTimeField(blank=True, null=True)
    hora_real = models.DateTimeField(blank=True, null=True)
    estado_parada = models.CharField(
        max_length=20, choices=EstadoParada.choices, default=EstadoParada.PENDIENTE
    )

    class Meta:
        db_table = "ruta_pedidos"
        ordering = ["orden_parada"]
        unique_together = ("ruta", "pedido")

    def __str__(self):
        return f"Ruta {self.ruta_id} · parada {self.orden_parada} · pedido {self.pedido_id}"

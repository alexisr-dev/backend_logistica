from django.conf import settings
from django.db import models


class UbicacionTiempoReal(models.Model):
    repartidor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ubicaciones"
    )
    pedido = models.ForeignKey(
        "pedidos.Pedido", on_delete=models.CASCADE, related_name="ubicaciones",
        null=True, blank=True,
    )
    latitud = models.FloatField()
    longitud = models.FloatField()
    velocidad_kmh = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ubicaciones_tiempo_real"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["repartidor", "-timestamp"], name="idx_ubic_repartidor_tiempo"),
        ]

    def __str__(self):
        return f"{self.repartidor} @ ({self.latitud}, {self.longitud})"

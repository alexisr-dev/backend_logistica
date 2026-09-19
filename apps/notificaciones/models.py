from django.conf import settings
from django.db import models


class Notificacion(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notificaciones"
    )
    pedido = models.ForeignKey(
        "pedidos.Pedido", on_delete=models.CASCADE, related_name="notificaciones",
        null=True, blank=True,
    )
    tipo = models.CharField(max_length=50, blank=True, null=True)
    titulo = models.CharField(max_length=150, blank=True, null=True)
    mensaje = models.CharField(max_length=255, blank=True, null=True)
    leido = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notificaciones"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"{self.titulo} → {self.usuario}"

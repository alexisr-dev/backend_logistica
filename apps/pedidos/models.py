from django.conf import settings
from django.db import models

from core.utils import generar_codigo_seguimiento


class EstadoPedido(models.Model):
    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=50)
    orden = models.SmallIntegerField()

    class Meta:
        db_table = "estados_pedido"
        ordering = ["orden"]
        verbose_name = "estado de pedido"
        verbose_name_plural = "estados de pedido"

    def __str__(self):
        return self.nombre


class Pedido(models.Model):
    codigo_seguimiento = models.CharField(max_length=20, unique=True, editable=False)
    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="pedidos_cliente"
    )
    repartidor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name="pedidos_repartidor", null=True, blank=True,
    )
    direccion_origen = models.ForeignKey(
        "usuarios.Direccion", on_delete=models.PROTECT, related_name="pedidos_origen"
    )
    direccion_destino = models.ForeignKey(
        "usuarios.Direccion", on_delete=models.PROTECT, related_name="pedidos_destino"
    )
    estado = models.ForeignKey(EstadoPedido, on_delete=models.PROTECT, related_name="pedidos")
    descripcion = models.CharField(max_length=255, blank=True, null=True)
    peso_kg = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    costo_envio = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_estimada_entrega = models.DateTimeField(blank=True, null=True)
    fecha_entrega_real = models.DateTimeField(blank=True, null=True)

    # Recorrido origen -> destino, cacheado tras pedírselo a OSRM.
    ruta_geometria = models.TextField(blank=True, null=True)
    ruta_distancia_km = models.DecimalField(
        max_digits=6, decimal_places=2, blank=True, null=True)
    ruta_duracion_min = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = "pedidos"
        ordering = ["-fecha_creacion"]
        indexes = [
            models.Index(fields=["cliente"]),
            models.Index(fields=["repartidor"]),
            models.Index(fields=["estado"]),
        ]

    def save(self, *args, **kwargs):
        if not self.codigo_seguimiento:
            codigo = generar_codigo_seguimiento()
            while Pedido.objects.filter(codigo_seguimiento=codigo).exists():
                codigo = generar_codigo_seguimiento()
            self.codigo_seguimiento = codigo
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo_seguimiento} - {self.estado}"


class HistorialEstadoPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="historial")
    estado = models.ForeignKey(EstadoPedido, on_delete=models.PROTECT)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    comentario = models.CharField(max_length=255, blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "historial_estados_pedido"
        ordering = ["fecha"]
        indexes = [models.Index(fields=["pedido"])]

    def __str__(self):
        return f"{self.pedido.codigo_seguimiento} → {self.estado} ({self.fecha:%Y-%m-%d %H:%M})"


class Calificacion(models.Model):
    pedido = models.OneToOneField(Pedido, on_delete=models.CASCADE, related_name="calificacion")
    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calificaciones_dadas"
    )
    repartidor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calificaciones_recibidas"
    )
    puntuacion = models.SmallIntegerField()
    comentario = models.CharField(max_length=255, blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "calificaciones"

    def __str__(self):
        return f"{self.pedido.codigo_seguimiento}: {self.puntuacion}★"

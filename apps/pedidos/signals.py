from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.notificaciones.services import notificar

from .models import Pedido, HistorialEstadoPedido


@receiver(post_save, sender=HistorialEstadoPedido)
def notificar_cambio_estado(sender, instance, created, **kwargs):
    if not created:
        return

    pedido = instance.pedido
    estado = instance.estado.nombre

    notificar(
        pedido.cliente,
        pedido=pedido,
        tipo="cambio_estado",
        titulo=f"Tu pedido {pedido.codigo_seguimiento} cambió de estado",
        mensaje=f"Nuevo estado: {estado}.",
    )

    # El repartidor se entera también, salvo de sus propios movimientos.
    if pedido.repartidor_id and pedido.repartidor_id != instance.usuario_id:
        notificar(
            pedido.repartidor,
            pedido=pedido,
            tipo="cambio_estado",
            titulo=f"El pedido {pedido.codigo_seguimiento} cambió de estado",
            mensaje=f"Nuevo estado: {estado}.",
        )


@receiver(pre_save, sender=Pedido)
def notificar_asignacion(sender, instance, **kwargs):
    if instance.repartidor_id is None:
        return

    if instance.pk is None:
        anterior = None
    else:
        anterior = (
            Pedido.objects.filter(pk=instance.pk)
            .values_list("repartidor_id", flat=True)
            .first()
        )

    if anterior == instance.repartidor_id:
        return

    # En un alta, `codigo_seguimiento` todavía no existe.
    referencia = instance.codigo_seguimiento or "nuevo"

    notificar(
        instance.repartidor,
        pedido=None if instance.pk is None else instance,
        tipo="asignacion",
        titulo="Nuevo pedido asignado",
        mensaje=f"Se te asignó el pedido {referencia}. Revísalo en Mis entregas.",
    )

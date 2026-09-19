from django.db import transaction
from django.utils import timezone

from core.exceptions import TransicionEstadoInvalida
from .models import Pedido, EstadoPedido, HistorialEstadoPedido

# Máquina de estados: desde -> [estados permitidos]
TRANSICIONES = {
    "pendiente": ["confirmado", "cancelado"],
    "confirmado": ["en_preparacion", "cancelado"],
    "en_preparacion": ["en_camino", "cancelado"],
    "en_camino": ["entregado", "devuelto"],
    "entregado": [],
    "cancelado": [],
    "devuelto": [],
}


@transaction.atomic
def cambiar_estado(pedido: Pedido, codigo_nuevo: str, usuario=None, comentario: str = "") -> Pedido:
    actual = pedido.estado.codigo
    permitidos = TRANSICIONES.get(actual, [])
    if codigo_nuevo not in permitidos:
        raise TransicionEstadoInvalida(
            detail=f"No se puede pasar de '{actual}' a '{codigo_nuevo}'. "
                   f"Permitidos: {permitidos or 'ninguno (estado final)'}."
        )

    nuevo_estado = EstadoPedido.objects.get(codigo=codigo_nuevo)
    pedido.estado = nuevo_estado

    if codigo_nuevo == "entregado":
        pedido.fecha_entrega_real = timezone.now()

    pedido.save(update_fields=["estado", "fecha_entrega_real"])

    HistorialEstadoPedido.objects.create(
        pedido=pedido, estado=nuevo_estado, usuario=usuario, comentario=comentario
    )
    return pedido

import pytest
from django.contrib.auth import get_user_model

from apps.usuarios.models import Direccion
from apps.pedidos.models import Pedido, EstadoPedido
from apps.pedidos.services import cambiar_estado
from core.exceptions import TransicionEstadoInvalida

Usuario = get_user_model()


@pytest.fixture
def estados(db):
    # get_or_create evita colisiones con el seed de la migración 0003.
    datos = [
        ("pendiente", "Pendiente", 1),
        ("confirmado", "Confirmado", 2),
        ("en_preparacion", "En preparación", 3),
        ("en_camino", "En camino", 4),
        ("entregado", "Entregado", 5),
        ("cancelado", "Cancelado", 6),
    ]
    for c, n, o in datos:
        EstadoPedido.objects.get_or_create(codigo=c, defaults={"nombre": n, "orden": o})


@pytest.fixture
def pedido(db, estados):
    cliente = Usuario.objects.create_user(email="c@t.com", password="x", nombre="C", apellido="L")
    dir1 = Direccion.objects.create(usuario=cliente, calle="A", latitud=0, longitud=0)
    dir2 = Direccion.objects.create(usuario=cliente, calle="B", latitud=1, longitud=1)
    return Pedido.objects.create(
        cliente=cliente, direccion_origen=dir1, direccion_destino=dir2,
        estado=EstadoPedido.objects.get(codigo="pendiente"),
    )


@pytest.mark.django_db
def test_transicion_valida(pedido):
    cambiar_estado(pedido, "confirmado")
    assert pedido.estado.codigo == "confirmado"
    assert pedido.historial.count() == 1


@pytest.mark.django_db
def test_transicion_invalida(pedido):
    with pytest.raises(TransicionEstadoInvalida):
        cambiar_estado(pedido, "entregado")  # no se puede saltar directo


@pytest.mark.django_db
def test_codigo_seguimiento_autogenerado(pedido):
    assert pedido.codigo_seguimiento.startswith("LOG-")

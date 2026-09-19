import pytest

ESTADOS = [
    ("pendiente", "Pendiente", 1),
    ("confirmado", "Confirmado", 2),
    ("en_preparacion", "En preparación", 3),
    ("en_camino", "En camino", 4),
    ("entregado", "Entregado", 5),
    ("cancelado", "Cancelado", 6),
    ("devuelto", "Devuelto", 7),
]


@pytest.fixture
def estados_pedido(db):
    from apps.pedidos.models import EstadoPedido

    for codigo, nombre, orden in ESTADOS:
        EstadoPedido.objects.get_or_create(
            codigo=codigo, defaults={"nombre": nombre, "orden": orden}
        )


@pytest.fixture(autouse=True)
def limpiar_cache_de_throttling():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()

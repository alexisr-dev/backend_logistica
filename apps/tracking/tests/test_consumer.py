import asyncio

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

from config.asgi import application
from apps.pedidos.models import Pedido, EstadoPedido
from apps.tracking.models import UbicacionTiempoReal
from apps.usuarios.models import Direccion, PerfilRepartidor

Usuario = get_user_model()

# `transaction=True`: el consumer lee la BD desde otro hilo y la transacción
# por defecto de pytest-django la bloquearía ("database table is locked").
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def escenario(db, estados_pedido):
    cliente = Usuario.objects.create_user(
        email="cliente@ws.com", password="x", nombre="C", apellido="L", rol="cliente")
    repartidor = Usuario.objects.create_user(
        email="rep@ws.com", password="x", nombre="R", apellido="P", rol="repartidor")
    ajeno = Usuario.objects.create_user(
        email="ajeno@ws.com", password="x", nombre="X", apellido="Z", rol="cliente")
    # El perfil lo crea solo el signal de apps.usuarios al asignar rol repartidor.

    origen = Direccion.objects.create(usuario=cliente, calle="O", latitud=0, longitud=0)
    destino = Direccion.objects.create(usuario=cliente, calle="D", latitud=1, longitud=1)
    pedido = Pedido.objects.create(
        cliente=cliente, repartidor=repartidor,
        direccion_origen=origen, direccion_destino=destino,
        estado=EstadoPedido.objects.get(codigo="pendiente"),
    )
    return pedido, cliente, repartidor, ajeno


def ruta(pedido, usuario=None):
    sufijo = f"?token={AccessToken.for_user(usuario)}" if usuario else ""
    return f"/ws/tracking/{pedido.id}/{sufijo}"


def conectar(pedido, usuario=None):
    async def intento():
        comunicador = WebsocketCommunicator(application, ruta(pedido, usuario))
        aceptado, codigo = await comunicador.connect()
        await comunicador.disconnect()
        return aceptado, codigo

    return asyncio.run(intento())


def test_sin_token_se_rechaza(escenario):
    pedido, *_ = escenario
    aceptado, codigo = conectar(pedido)
    assert not aceptado
    assert codigo == 4401


def test_token_invalido_se_rechaza(escenario):
    pedido, *_ = escenario

    async def intento():
        comunicador = WebsocketCommunicator(
            application, f"/ws/tracking/{pedido.id}/?token=basura")
        aceptado, codigo = await comunicador.connect()
        await comunicador.disconnect()
        return aceptado, codigo

    aceptado, codigo = asyncio.run(intento())
    assert not aceptado
    assert codigo == 4401


def test_usuario_sin_relacion_con_el_pedido_se_rechaza(escenario):
    pedido, _cliente, _repartidor, ajeno = escenario
    aceptado, codigo = conectar(pedido, ajeno)
    assert not aceptado
    assert codigo == 4403


def test_cliente_y_repartidor_del_pedido_pueden_conectarse(escenario):
    pedido, cliente, repartidor, _ = escenario
    assert conectar(pedido, cliente)[0]
    assert conectar(pedido, repartidor)[0]


def test_el_repartidor_emite_y_el_cliente_lo_recibe(escenario):
    pedido, cliente, repartidor, _ = escenario

    @database_sync_to_async
    def ultimo_punto():
        return UbicacionTiempoReal.objects.order_by("-id").first()

    @database_sync_to_async
    def perfil():
        pr = PerfilRepartidor.objects.get(usuario=repartidor)
        return pr.ultima_lat, pr.ultima_lng

    async def flujo():
        emisor = WebsocketCommunicator(application, ruta(pedido, repartidor))
        receptor = WebsocketCommunicator(application, ruta(pedido, cliente))
        assert (await emisor.connect())[0]
        assert (await receptor.connect())[0]

        await emisor.send_json_to({"lat": -12.09, "lng": -77.04, "velocidad": 22})
        recibido = await receptor.receive_json_from(timeout=5)

        guardado = await ultimo_punto()
        coordenadas = await perfil()

        await emisor.disconnect()
        await receptor.disconnect()
        return recibido, guardado, coordenadas

    recibido, guardado, (lat_perfil, lng_perfil) = asyncio.run(flujo())

    assert recibido == {"lat": -12.09, "lng": -77.04, "velocidad": 22}
    # El histórico se persiste: antes el consumer lo descartaba en silencio.
    assert guardado is not None
    assert guardado.latitud == pytest.approx(-12.09)
    # Y el último punto queda cacheado en el perfil del repartidor.
    assert lat_perfil == pytest.approx(-12.09)
    assert lng_perfil == pytest.approx(-77.04)


def test_el_cliente_no_puede_inyectar_posiciones(escenario):
    pedido, cliente, _repartidor, _ = escenario

    @database_sync_to_async
    def total():
        return UbicacionTiempoReal.objects.count()

    async def flujo():
        espia = WebsocketCommunicator(application, ruta(pedido, cliente))
        assert (await espia.connect())[0]

        await espia.send_json_to({"lat": 0.0, "lng": 0.0, "velocidad": 999})
        await asyncio.sleep(0.3)

        contador = await total()
        await espia.disconnect()
        return contador

    assert asyncio.run(flujo()) == 0


def test_se_descartan_coordenadas_fuera_de_rango(escenario):
    pedido, _cliente, repartidor, _ = escenario

    @database_sync_to_async
    def total():
        return UbicacionTiempoReal.objects.count()

    async def flujo():
        emisor = WebsocketCommunicator(application, ruta(pedido, repartidor))
        assert (await emisor.connect())[0]

        await emisor.send_json_to({"lat": 120.0, "lng": -77.04})   # latitud imposible
        await emisor.send_json_to({"lat": "x", "lng": "y"})        # no numérico
        await asyncio.sleep(0.3)

        contador = await total()
        await emisor.disconnect()
        return contador

    assert asyncio.run(flujo()) == 0

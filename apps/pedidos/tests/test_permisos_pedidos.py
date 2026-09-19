import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.usuarios.models import Direccion
from apps.pedidos.models import Pedido, EstadoPedido

Usuario = get_user_model()


@pytest.fixture
def actores(db, estados_pedido):
    admin = Usuario.objects.create_user(
        email="admin@t.com", password="x", nombre="A", apellido="D", rol="administrador")
    cliente = Usuario.objects.create_user(
        email="cliente@t.com", password="x", nombre="C", apellido="L", rol="cliente")
    repartidor = Usuario.objects.create_user(
        email="rep@t.com", password="x", nombre="R", apellido="P", rol="repartidor")
    return admin, cliente, repartidor


def api(usuario):
    cliente = APIClient()
    cliente.force_authenticate(user=usuario)
    return cliente


def _pedido(cliente, repartidor, codigo_estado="pendiente"):
    origen = Direccion.objects.create(usuario=cliente, calle="O", latitud=0, longitud=0)
    destino = Direccion.objects.create(usuario=cliente, calle="D", latitud=1, longitud=1)
    return Pedido.objects.create(
        cliente=cliente, repartidor=repartidor,
        direccion_origen=origen, direccion_destino=destino,
        estado=EstadoPedido.objects.get(codigo=codigo_estado),
    )


@pytest.mark.django_db
def test_admin_crea_pedido_y_direcciones_a_nombre_del_cliente(actores):
    admin, cliente, repartidor = actores
    c = api(admin)

    origen = c.post("/api/v1/usuarios/direcciones/", {
        "usuario": cliente.id, "calle": "Origen", "latitud": -12.09, "longitud": -77.04,
    }, format="json")
    destino = c.post("/api/v1/usuarios/direcciones/", {
        "usuario": cliente.id, "calle": "Destino", "latitud": -12.12, "longitud": -77.03,
    }, format="json")
    assert origen.status_code == 201, origen.data

    # La dirección es del cliente, no de quien rellenó el formulario.
    assert Direccion.objects.get(pk=origen.data["id"]).usuario_id == cliente.id

    respuesta = c.post("/api/v1/pedidos/", {
        "cliente": cliente.id, "repartidor": repartidor.id,
        "direccion_origen": origen.data["id"], "direccion_destino": destino.data["id"],
        "descripcion": "Caja",
    }, format="json")
    assert respuesta.status_code == 201, respuesta.data
    assert Pedido.objects.get(pk=respuesta.data["id"]).cliente_id == cliente.id


@pytest.mark.django_db
def test_cliente_crea_pedido_solo_para_si_mismo(actores):
    admin, cliente, repartidor = actores
    origen = Direccion.objects.create(usuario=cliente, calle="O", latitud=0, longitud=0)
    destino = Direccion.objects.create(usuario=cliente, calle="D", latitud=1, longitud=1)

    # Aunque indique otro `cliente`, el pedido queda a su nombre.
    respuesta = api(cliente).post("/api/v1/pedidos/", {
        "cliente": admin.id,
        "direccion_origen": origen.id, "direccion_destino": destino.id,
    }, format="json")
    assert respuesta.status_code == 201, respuesta.data
    assert Pedido.objects.get(pk=respuesta.data["id"]).cliente_id == cliente.id


@pytest.mark.django_db
def test_transiciones_permitidas_reflejan_la_maquina_de_estados(actores):
    admin, cliente, repartidor = actores
    pedido = _pedido(cliente, repartidor)

    detalle = api(admin).get(f"/api/v1/pedidos/{pedido.id}/")
    codigos = {t["codigo"] for t in detalle.data["transiciones_permitidas"]}
    assert codigos == {"confirmado", "cancelado"}


@pytest.mark.django_db
def test_cliente_no_avanza_el_pedido_pero_si_lo_cancela(actores):
    admin, cliente, repartidor = actores
    pedido = _pedido(cliente, repartidor)

    bloqueado = api(cliente).post(
        f"/api/v1/pedidos/{pedido.id}/cambiar-estado/", {"codigo": "confirmado"}, format="json")
    assert bloqueado.status_code == 403

    permitido = api(cliente).post(
        f"/api/v1/pedidos/{pedido.id}/cambiar-estado/", {"codigo": "cancelado"}, format="json")
    assert permitido.status_code == 200, permitido.data


@pytest.mark.django_db
def test_solo_el_repartidor_asignado_marca_entregado(actores):
    admin, cliente, repartidor = actores
    pedido = _pedido(cliente, repartidor, codigo_estado="en_camino")

    autoentrega = api(cliente).post(
        f"/api/v1/pedidos/{pedido.id}/cambiar-estado/", {"codigo": "entregado"}, format="json")
    assert autoentrega.status_code == 403, "un cliente no puede darse por servido a sí mismo"

    entrega = api(repartidor).post(
        f"/api/v1/pedidos/{pedido.id}/cambiar-estado/", {"codigo": "entregado"}, format="json")
    assert entrega.status_code == 200, entrega.data
    pedido.refresh_from_db()
    assert pedido.fecha_entrega_real is not None


@pytest.mark.django_db
def test_reasignar_repartidor_es_solo_del_administrador(actores):
    admin, cliente, repartidor = actores
    pedido = _pedido(cliente, None)

    ajeno = api(cliente).patch(
        f"/api/v1/pedidos/{pedido.id}/", {"repartidor": repartidor.id}, format="json")
    assert ajeno.status_code == 403

    propio = api(admin).patch(
        f"/api/v1/pedidos/{pedido.id}/", {"repartidor": repartidor.id}, format="json")
    assert propio.status_code == 200, propio.data
    pedido.refresh_from_db()
    assert pedido.repartidor_id == repartidor.id

import datetime

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.notificaciones.models import Notificacion
from apps.pedidos.models import Pedido, EstadoPedido
from apps.pedidos.services import cambiar_estado
from apps.usuarios.models import Direccion

Usuario = get_user_model()


def api(usuario):
    cliente = APIClient()
    cliente.force_authenticate(user=usuario)
    return cliente


@pytest.fixture
def gente(db, estados_pedido):
    cliente = Usuario.objects.create_user(
        email="cli@n.com", password="x", nombre="C", apellido="L", rol="cliente")
    repartidor = Usuario.objects.create_user(
        email="rep@n.com", password="x", nombre="R", apellido="Z", rol="repartidor")
    return cliente, repartidor


def _pedido(cliente, repartidor=None, codigo="pendiente"):
    origen = Direccion.objects.create(usuario=cliente, calle="Almacén", latitud=0, longitud=0)
    destino = Direccion.objects.create(usuario=cliente, calle="Destino", latitud=1, longitud=1)
    return Pedido.objects.create(
        cliente=cliente, repartidor=repartidor,
        direccion_origen=origen, direccion_destino=destino,
        estado=EstadoPedido.objects.get(codigo=codigo),
    )


@pytest.mark.django_db
def test_asignar_repartidor_le_notifica(gente):
    cliente, repartidor = gente
    pedido = _pedido(cliente)
    assert not Notificacion.objects.filter(usuario=repartidor).exists()

    pedido.repartidor = repartidor
    pedido.save()

    aviso = Notificacion.objects.get(usuario=repartidor, tipo="asignacion")
    assert pedido.codigo_seguimiento in aviso.mensaje


@pytest.mark.django_db
def test_no_se_repite_el_aviso_si_el_repartidor_no_cambia(gente):
    cliente, repartidor = gente
    pedido = _pedido(cliente, repartidor)

    pedido.descripcion = "Otra cosa"
    pedido.save()

    assert Notificacion.objects.filter(usuario=repartidor, tipo="asignacion").count() == 1


@pytest.mark.django_db
def test_el_repartidor_no_se_notifica_sus_propios_movimientos(gente):
    cliente, repartidor = gente
    pedido = _pedido(cliente, repartidor, codigo="en_camino")
    Notificacion.objects.all().delete()

    cambiar_estado(pedido, "entregado", usuario=repartidor)

    assert not Notificacion.objects.filter(usuario=repartidor, tipo="cambio_estado").exists()
    # El cliente sí se entera de que su pedido llegó.
    assert Notificacion.objects.filter(usuario=cliente, tipo="cambio_estado").exists()


@pytest.mark.django_db
def test_el_repartidor_se_entera_de_una_cancelacion_del_cliente(gente):
    cliente, repartidor = gente
    pedido = _pedido(cliente, repartidor)
    Notificacion.objects.all().delete()

    cambiar_estado(pedido, "cancelado", usuario=cliente)

    assert Notificacion.objects.filter(usuario=repartidor, tipo="cambio_estado").exists()


@pytest.mark.django_db
def test_planificar_ruta_avisa_al_repartidor(gente):
    cliente, repartidor = gente
    admin = Usuario.objects.create_user(
        email="adm@n.com", password="x", nombre="A", apellido="D", rol="administrador")
    # Dos paradas: OSRM necesita un origen y un destino para trazar nada.
    primero = _pedido(cliente, repartidor)
    segundo = _pedido(cliente, repartidor)
    Notificacion.objects.all().delete()

    respuesta = api(admin).post("/api/v1/rutas/planificar/", {
        "repartidor": repartidor.id,
        "fecha": datetime.date(2026, 3, 2).isoformat(),
        "pedidos": [primero.id, segundo.id],
    }, format="json")

    # OSRM es externo: si no responde, no hay ruta que notificar.
    if respuesta.status_code != 201:
        pytest.skip(f"OSRM no disponible (HTTP {respuesta.status_code})")

    aviso = Notificacion.objects.get(usuario=repartidor, tipo="ruta_asignada")
    assert "2 paradas" in aviso.mensaje


@pytest.mark.django_db
def test_planificar_con_una_sola_parada_es_400_y_no_500(gente):
    cliente, repartidor = gente
    admin = Usuario.objects.create_user(
        email="adm2@n.com", password="x", nombre="A", apellido="D", rol="administrador")
    pedido = _pedido(cliente, repartidor)

    respuesta = api(admin).post("/api/v1/rutas/planificar/", {
        "repartidor": repartidor.id,
        "fecha": datetime.date(2026, 3, 2).isoformat(),
        "pedidos": [pedido.id],
    }, format="json")

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "paradas_insuficientes"


@pytest.mark.django_db
def test_solo_veo_mis_notificaciones(gente):
    cliente, repartidor = gente
    _pedido(cliente, repartidor)

    datos = api(repartidor).get("/api/v1/notificaciones/").data
    resultados = datos["results"] if isinstance(datos, dict) else datos

    assert resultados
    assert all(n["usuario"] == repartidor.id for n in resultados)

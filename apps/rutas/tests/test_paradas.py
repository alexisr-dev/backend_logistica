import datetime

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.pedidos.models import Pedido, EstadoPedido
from apps.rutas.models import Ruta, RutaPedido
from apps.usuarios.models import Direccion

Usuario = get_user_model()


def api(usuario):
    cliente = APIClient()
    cliente.force_authenticate(user=usuario)
    return cliente


def _pedido(cliente, repartidor, codigo_estado="en_camino"):
    origen = Direccion.objects.create(usuario=cliente, calle="Almacén", latitud=0, longitud=0)
    destino = Direccion.objects.create(
        usuario=cliente, calle="Av. Arequipa", distrito="Lince", latitud=-12.09, longitud=-77.04
    )
    return Pedido.objects.create(
        cliente=cliente, repartidor=repartidor,
        direccion_origen=origen, direccion_destino=destino,
        estado=EstadoPedido.objects.get(codigo=codigo_estado),
    )


@pytest.fixture
def escenario(db, estados_pedido):
    ana = Usuario.objects.create_user(
        email="ana@p.com", password="x", nombre="Ana", apellido="P", rol="cliente")
    repartidor = Usuario.objects.create_user(
        email="rep@p.com", password="x", nombre="R", apellido="Z", rol="repartidor")
    otro = Usuario.objects.create_user(
        email="otro@p.com", password="x", nombre="O", apellido="T", rol="repartidor")

    ruta = Ruta.objects.create(repartidor=repartidor, fecha=datetime.date(2026, 3, 2))
    parada = RutaPedido.objects.create(
        ruta=ruta, pedido=_pedido(ana, repartidor), orden_parada=1)

    return ana, repartidor, otro, ruta, parada


@pytest.mark.django_db
def test_marcar_entregado_cierra_parada_y_pedido(escenario):
    _ana, repartidor, _otro, _ruta, parada = escenario

    respuesta = api(repartidor).post(
        f"/api/v1/rutas/paradas/{parada.id}/marcar/", {"resultado": "entregado"}, format="json")

    assert respuesta.status_code == 200
    assert respuesta.data["pedido_actualizado"] is True
    assert respuesta.data["estado_pedido"] == "entregado"

    parada.refresh_from_db()
    assert parada.estado_parada == "entregado"
    # `hora_real` es lo que distingue una parada cerrada de una planificada.
    assert parada.hora_real is not None
    assert parada.pedido.fecha_entrega_real is not None


@pytest.mark.django_db
def test_marcar_fallido_devuelve_el_pedido_y_guarda_el_motivo(escenario):
    _ana, repartidor, _otro, _ruta, parada = escenario

    respuesta = api(repartidor).post(
        f"/api/v1/rutas/paradas/{parada.id}/marcar/",
        {"resultado": "fallido", "comentario": "Nadie en el domicilio"},
        format="json",
    )

    assert respuesta.status_code == 200
    assert respuesta.data["estado_pedido"] == "devuelto"

    parada.refresh_from_db()
    assert parada.estado_parada == "fallido"
    # El motivo viaja en el comentario del historial.
    historial = parada.pedido.historial.order_by("-fecha").first()
    assert historial.comentario == "Nadie en el domicilio"


@pytest.mark.django_db
def test_parada_se_cierra_aunque_el_pedido_no_pueda_avanzar(db, estados_pedido):
    ana = Usuario.objects.create_user(
        email="ana2@p.com", password="x", nombre="Ana", apellido="P", rol="cliente")
    repartidor = Usuario.objects.create_user(
        email="rep2@p.com", password="x", nombre="R", apellido="Z", rol="repartidor")
    ruta = Ruta.objects.create(repartidor=repartidor, fecha=datetime.date(2026, 3, 2))
    parada = RutaPedido.objects.create(
        ruta=ruta, pedido=_pedido(ana, repartidor, codigo_estado="pendiente"), orden_parada=1)

    respuesta = api(repartidor).post(
        f"/api/v1/rutas/paradas/{parada.id}/marcar/", {"resultado": "entregado"}, format="json")

    assert respuesta.status_code == 200
    assert respuesta.data["pedido_actualizado"] is False
    assert respuesta.data["estado_pedido"] == "pendiente"
    assert respuesta.data["motivo"]

    parada.refresh_from_db()
    assert parada.estado_parada == "entregado"


@pytest.mark.django_db
def test_el_cliente_no_puede_cerrar_su_propia_parada(escenario):
    ana, _repartidor, _otro, _ruta, parada = escenario

    respuesta = api(ana).post(
        f"/api/v1/rutas/paradas/{parada.id}/marcar/", {"resultado": "entregado"}, format="json")

    assert respuesta.status_code == 403
    parada.refresh_from_db()
    assert parada.estado_parada == "pendiente"


@pytest.mark.django_db
def test_otro_repartidor_ni_siquiera_ve_la_parada(escenario):
    _ana, _repartidor, otro, _ruta, parada = escenario

    respuesta = api(otro).post(
        f"/api/v1/rutas/paradas/{parada.id}/marcar/", {"resultado": "entregado"}, format="json")

    # 404 y no 403: el queryset ya filtra por rol, así que para él no existe.
    assert respuesta.status_code == 404


@pytest.mark.django_db
def test_resultado_pendiente_no_es_un_resultado(escenario):
    _ana, repartidor, _otro, _ruta, parada = escenario

    respuesta = api(repartidor).post(
        f"/api/v1/rutas/paradas/{parada.id}/marcar/", {"resultado": "pendiente"}, format="json")

    assert respuesta.status_code == 400


@pytest.mark.django_db
def test_iniciar_y_finalizar_ruta(escenario):
    _ana, repartidor, _otro, ruta, _parada = escenario
    assert ruta.estado == "planificada"

    assert api(repartidor).post(f"/api/v1/rutas/{ruta.id}/iniciar/").status_code == 200
    ruta.refresh_from_db()
    assert ruta.estado == "en_curso"

    # Idempotente: el móvil reintenta al recuperar la conexión.
    assert api(repartidor).post(f"/api/v1/rutas/{ruta.id}/iniciar/").status_code == 200

    assert api(repartidor).post(f"/api/v1/rutas/{ruta.id}/finalizar/").status_code == 200
    ruta.refresh_from_db()
    assert ruta.estado == "finalizada"

    # Ya finalizada, no se puede volver a arrancar.
    assert api(repartidor).post(f"/api/v1/rutas/{ruta.id}/iniciar/").status_code == 409


@pytest.mark.django_db
def test_un_cliente_no_puede_modificar_la_ruta_de_su_pedido(escenario):
    ana, _repartidor, _otro, ruta, _parada = escenario

    assert api(ana).patch(
        f"/api/v1/rutas/{ruta.id}/", {"estado": "cancelada"}, format="json").status_code == 403
    assert api(ana).delete(f"/api/v1/rutas/{ruta.id}/").status_code == 403
    assert api(ana).post(f"/api/v1/rutas/{ruta.id}/iniciar/").status_code == 403

    ruta.refresh_from_db()
    assert ruta.estado == "planificada"

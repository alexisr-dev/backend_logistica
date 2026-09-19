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


def _crear_pedido(cliente, repartidor, lat, lng):
    origen = Direccion.objects.create(usuario=cliente, calle="Almacén", latitud=0, longitud=0)
    destino = Direccion.objects.create(
        usuario=cliente, calle="Av. Arequipa", distrito="Miraflores",
        latitud=lat, longitud=lng,
    )
    return Pedido.objects.create(
        cliente=cliente, repartidor=repartidor,
        direccion_origen=origen, direccion_destino=destino,
        estado=EstadoPedido.objects.get(codigo="pendiente"),
    )


@pytest.fixture
def escenario(db, estados_pedido):
    admin = Usuario.objects.create_user(
        email="admin@r.com", password="x", nombre="A", apellido="D", rol="administrador")
    ana = Usuario.objects.create_user(
        email="ana@r.com", password="x", nombre="Ana", apellido="P", rol="cliente")
    beto = Usuario.objects.create_user(
        email="beto@r.com", password="x", nombre="Beto", apellido="Q", rol="cliente")
    repartidor = Usuario.objects.create_user(
        email="rep@r.com", password="x", nombre="R", apellido="Z", rol="repartidor")
    otro = Usuario.objects.create_user(
        email="otro@r.com", password="x", nombre="O", apellido="T", rol="repartidor")

    ruta_ana = Ruta.objects.create(
        repartidor=repartidor, fecha=datetime.date(2026, 1, 15), geometria_ruta="abc")
    RutaPedido.objects.create(
        ruta=ruta_ana, pedido=_crear_pedido(ana, repartidor, -12.09, -77.04), orden_parada=1)
    RutaPedido.objects.create(
        ruta=ruta_ana, pedido=_crear_pedido(ana, repartidor, -12.12, -77.03), orden_parada=2)

    ruta_beto = Ruta.objects.create(repartidor=otro, fecha=datetime.date(2026, 1, 15))
    RutaPedido.objects.create(
        ruta=ruta_beto, pedido=_crear_pedido(beto, otro, -12.05, -77.05), orden_parada=1)

    return admin, ana, beto, repartidor, otro, ruta_ana, ruta_beto


@pytest.mark.django_db
def test_cada_parada_trae_las_coordenadas_de_su_destino(escenario):
    admin, ana, _beto, _repartidor, _otro, ruta_ana, _ = escenario

    respuesta = api(admin).get(f"/api/v1/rutas/{ruta_ana.id}/")
    assert respuesta.status_code == 200

    paradas = sorted(respuesta.data["paradas"], key=lambda p: p["orden_parada"])
    assert len(paradas) == 2

    primera = paradas[0]
    assert primera["latitud"] == pytest.approx(-12.09)
    assert primera["longitud"] == pytest.approx(-77.04)
    assert primera["direccion"] == "Av. Arequipa"
    assert primera["distrito"] == "Miraflores"


@pytest.mark.django_db
def test_el_repartidor_solo_ve_sus_rutas(escenario):
    _admin, _ana, _beto, repartidor, _otro, ruta_ana, ruta_beto = escenario

    respuesta = api(repartidor).get("/api/v1/rutas/")
    ids = {r["id"] for r in respuesta.data["results"]}
    assert ids == {ruta_ana.id}


@pytest.mark.django_db
def test_el_cliente_solo_ve_rutas_con_sus_pedidos(escenario):
    _admin, ana, beto, _repartidor, _otro, ruta_ana, ruta_beto = escenario

    de_ana = {r["id"] for r in api(ana).get("/api/v1/rutas/").data["results"]}
    assert de_ana == {ruta_ana.id}
    assert ruta_beto.id not in de_ana

    de_beto = {r["id"] for r in api(beto).get("/api/v1/rutas/").data["results"]}
    assert de_beto == {ruta_beto.id}


@pytest.mark.django_db
def test_el_administrador_ve_todas(escenario):
    admin, _ana, _beto, _repartidor, _otro, ruta_ana, ruta_beto = escenario

    ids = {r["id"] for r in api(admin).get("/api/v1/rutas/").data["results"]}
    assert ids == {ruta_ana.id, ruta_beto.id}


@pytest.mark.django_db
def test_las_paradas_no_provocan_una_consulta_por_fila(escenario, django_assert_max_num_queries):
    admin, *_ = escenario

    # Sin el prefetch completo, cada parada añadiría su propia consulta.
    with django_assert_max_num_queries(8):
        respuesta = api(admin).get("/api/v1/rutas/")
        assert respuesta.status_code == 200
        assert respuesta.data["results"][0]["paradas"][0]["latitud"] is not None


@pytest.mark.django_db
def test_filtrar_por_pedido_devuelve_su_ruta(escenario):
    _admin, ana, _beto, _repartidor, _otro, ruta_ana, _ = escenario
    pedido_id = ruta_ana.paradas.first().pedido_id

    respuesta = api(ana).get("/api/v1/rutas/", {"pedido": pedido_id})
    assert respuesta.status_code == 200
    assert [r["id"] for r in respuesta.data["results"]] == [ruta_ana.id]


@pytest.mark.django_db
def test_el_filtro_no_salta_el_aislamiento_por_rol(escenario):
    _admin, ana, _beto, _repartidor, _otro, _ruta_ana, ruta_beto = escenario
    pedido_ajeno = ruta_beto.paradas.first().pedido_id

    respuesta = api(ana).get("/api/v1/rutas/", {"pedido": pedido_ajeno})
    assert respuesta.status_code == 200
    assert respuesta.data["results"] == []


@pytest.mark.django_db
def test_planificar_es_solo_del_administrador(escenario):
    _admin, _ana, _beto, repartidor, _otro, _ruta_ana, _ = escenario

    respuesta = api(repartidor).post("/api/v1/rutas/planificar/", {
        "repartidor": repartidor.id, "fecha": "2026-01-20", "pedidos": [1, 2],
    }, format="json")
    assert respuesta.status_code == 403

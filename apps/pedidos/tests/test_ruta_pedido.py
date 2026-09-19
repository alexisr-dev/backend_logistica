import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.pedidos.models import Pedido, EstadoPedido
from apps.usuarios.models import Direccion
from core.exceptions import ServicioExternoNoDisponible

Usuario = get_user_model()

GEOMETRIA = "izpxlA~||`Ea@bBc@fB"


class OsrmFalso:

    def __init__(self, falla=False):
        self.falla = falla
        self.llamadas = []

    def __call__(self, coordenadas):
        self.llamadas.append(coordenadas)
        if self.falla:
            raise ServicioExternoNoDisponible(detail="OSRM no respondió")
        return {"geometria": GEOMETRIA, "distancia_km": 4.2, "duracion_min": 11.0}


@pytest.fixture
def actores(db, estados_pedido):
    admin = Usuario.objects.create_user(
        email="admin@rp.com", password="x", nombre="A", apellido="D", rol="administrador")
    cliente = Usuario.objects.create_user(
        email="cli@rp.com", password="x", nombre="C", apellido="L", rol="cliente")
    ajeno = Usuario.objects.create_user(
        email="aje@rp.com", password="x", nombre="X", apellido="Z", rol="cliente")
    return admin, cliente, ajeno


@pytest.fixture
def pedido(actores):
    _admin, cliente, _ajeno = actores
    origen = Direccion.objects.create(
        usuario=cliente, calle="Av. Javier Prado", distrito="San Isidro",
        latitud=-12.0931, longitud=-77.0465)
    destino = Direccion.objects.create(
        usuario=cliente, calle="Av. Arequipa", distrito="Miraflores",
        latitud=-12.1211, longitud=-77.0300)
    return Pedido.objects.create(
        cliente=cliente, direccion_origen=origen, direccion_destino=destino,
        estado=EstadoPedido.objects.get(codigo="pendiente"),
    )


def api(usuario):
    c = APIClient()
    c.force_authenticate(user=usuario)
    return c


def _instalar_osrm(monkeypatch, doble):
    # Se parchea donde se usa, no donde se define.
    monkeypatch.setattr("apps.pedidos.views.calcular_ruta", doble)


@pytest.mark.django_db
def test_devuelve_el_trazado_sin_ruta_planificada(monkeypatch, actores, pedido):
    _admin, cliente, _ajeno = actores
    osrm = OsrmFalso()
    _instalar_osrm(monkeypatch, osrm)

    respuesta = api(cliente).get(f"/api/v1/pedidos/{pedido.id}/ruta/")
    assert respuesta.status_code == 200
    assert respuesta.data["geometria"] == GEOMETRIA
    assert respuesta.data["origen"]["latitud"] == pytest.approx(-12.0931)
    assert respuesta.data["destino"]["latitud"] == pytest.approx(-12.1211)
    assert respuesta.data["destino"]["direccion"] == "Av. Arequipa"

    # Se pide a OSRM en el orden correcto: primero origen, después destino.
    assert osrm.llamadas == [[(-12.0931, -77.0465), (-12.1211, -77.0300)]]


@pytest.mark.django_db
def test_la_segunda_consulta_usa_la_cache(monkeypatch, actores, pedido):
    _admin, cliente, _ajeno = actores
    osrm = OsrmFalso()
    _instalar_osrm(monkeypatch, osrm)

    api(cliente).get(f"/api/v1/pedidos/{pedido.id}/ruta/")
    api(cliente).get(f"/api/v1/pedidos/{pedido.id}/ruta/")

    assert len(osrm.llamadas) == 1, "el trazado no cambia: no debe recalcularse"
    pedido.refresh_from_db()
    assert pedido.ruta_geometria == GEOMETRIA
    assert pedido.ruta_duracion_min == 11


@pytest.mark.django_db
def test_si_osrm_falla_devuelve_los_extremos_igualmente(monkeypatch, actores, pedido):
    _admin, cliente, _ajeno = actores
    _instalar_osrm(monkeypatch, OsrmFalso(falla=True))

    respuesta = api(cliente).get(f"/api/v1/pedidos/{pedido.id}/ruta/")
    assert respuesta.status_code == 200
    assert respuesta.data["geometria"] is None
    assert respuesta.data["origen"]["longitud"] == pytest.approx(-77.0465)
    assert respuesta.data["destino"]["longitud"] == pytest.approx(-77.0300)


@pytest.mark.django_db
def test_un_cliente_ajeno_no_alcanza_el_pedido(monkeypatch, actores, pedido):
    _admin, _cliente, ajeno = actores
    _instalar_osrm(monkeypatch, OsrmFalso())

    respuesta = api(ajeno).get(f"/api/v1/pedidos/{pedido.id}/ruta/")
    assert respuesta.status_code == 404


@pytest.mark.django_db
def test_cambiar_el_destino_invalida_la_cache(monkeypatch, actores, pedido):
    admin, cliente, _ajeno = actores
    osrm = OsrmFalso()
    _instalar_osrm(monkeypatch, osrm)

    api(cliente).get(f"/api/v1/pedidos/{pedido.id}/ruta/")
    assert len(osrm.llamadas) == 1

    otro_destino = Direccion.objects.create(
        usuario=cliente, calle="Av. Brasil", latitud=-12.07, longitud=-77.05)
    respuesta = api(admin).patch(
        f"/api/v1/pedidos/{pedido.id}/",
        {"direccion_destino": otro_destino.id}, format="json")
    assert respuesta.status_code == 200

    pedido.refresh_from_db()
    assert pedido.ruta_geometria is None, "el trazado antiguo ya no corresponde"

    api(cliente).get(f"/api/v1/pedidos/{pedido.id}/ruta/")
    assert len(osrm.llamadas) == 2
    assert osrm.llamadas[-1][-1] == (-12.07, -77.05)

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.usuarios.models import Direccion

Usuario = get_user_model()


@pytest.fixture
def actores(db, estados_pedido):
    admin = Usuario.objects.create_user(
        email="admin@r.com", password="x", nombre="A", apellido="D", rol="administrador")
    cliente = Usuario.objects.create_user(
        email="cliente@r.com", password="x", nombre="C", apellido="L", rol="cliente")
    repartidor = Usuario.objects.create_user(
        email="rep@r.com", password="x", nombre="R", apellido="P", rol="repartidor")
    return admin, cliente, repartidor


def api(usuario):
    c = APIClient()
    c.force_authenticate(user=usuario)
    return c


def _direcciones(cliente):
    origen = Direccion.objects.create(
        usuario=cliente, calle="Av. Grau", numero="450", distrito="Piura",
        ciudad="Piura", latitud=-5.19, longitud=-80.63)
    destino = Direccion.objects.create(
        usuario=cliente, calle="Los Educadores", distrito="Piura",
        ciudad="Piura", latitud=-5.17, longitud=-80.65)
    return origen, destino


@pytest.mark.django_db
def test_crear_devuelve_el_pedido_completo_y_no_los_ids(actores):
    _, cliente, _ = actores
    origen, destino = _direcciones(cliente)

    respuesta = api(cliente).post("/api/v1/pedidos/", {
        "direccion_origen": origen.id,
        "direccion_destino": destino.id,
        "descripcion": "Paquete",
        "peso_kg": "2.5",
    }, format="json")

    assert respuesta.status_code == 201, respuesta.data
    datos = respuesta.data

    # Lo que la app necesita para pintar «¡Pedido creado!» y su detalle.
    assert datos["codigo_seguimiento"]
    assert datos["estado"]["codigo"] == "pendiente"
    assert datos["fecha_creacion"]
    assert isinstance(datos["historial"], list)
    assert isinstance(datos["transiciones_permitidas"], list)

    # Las direcciones expandidas, no un entero suelto.
    assert datos["direccion_origen"]["calle"] == "Av. Grau"
    assert datos["direccion_destino"]["calle"] == "Los Educadores"

    # Y el cliente, que antes venía como id.
    assert datos["cliente"]["email"] == cliente.email


@pytest.mark.django_db
def test_crear_sigue_fijando_el_cliente_autenticado(actores):
    admin, cliente, _ = actores
    origen, destino = _direcciones(cliente)

    respuesta = api(cliente).post("/api/v1/pedidos/", {
        # Aunque pida el pedido a nombre del administrador...
        "cliente": admin.id,
        "direccion_origen": origen.id,
        "direccion_destino": destino.id,
    }, format="json")

    assert respuesta.status_code == 201, respuesta.data
    # ...queda a nombre de quien lo creó, y la respuesta lo confirma.
    assert respuesta.data["cliente"]["email"] == cliente.email


@pytest.mark.django_db
def test_asignar_repartidor_devuelve_el_estado_expandido(actores):
    admin, cliente, repartidor = actores
    origen, destino = _direcciones(cliente)
    creado = api(cliente).post("/api/v1/pedidos/", {
        "direccion_origen": origen.id, "direccion_destino": destino.id,
    }, format="json")

    respuesta = api(admin).patch(
        f"/api/v1/pedidos/{creado.data['id']}/",
        {"repartidor": repartidor.id},
        format="json",
    )

    assert respuesta.status_code == 200, respuesta.data
    assert respuesta.data["estado"]["codigo"] == "pendiente"
    assert respuesta.data["repartidor"]["email"] == repartidor.email
    assert respuesta.data["codigo_seguimiento"] == creado.data["codigo_seguimiento"]


@pytest.mark.django_db
def test_cambiar_las_direcciones_limpia_la_geometria_cacheada(actores):
    from apps.pedidos.models import Pedido

    admin, cliente, _ = actores
    origen, destino = _direcciones(cliente)
    creado = api(cliente).post("/api/v1/pedidos/", {
        "direccion_origen": origen.id, "direccion_destino": destino.id,
    }, format="json")

    pedido = Pedido.objects.get(pk=creado.data["id"])
    Pedido.objects.filter(pk=pedido.pk).update(
        ruta_geometria="abc", ruta_distancia_km=10, ruta_duracion_min=20)

    otro = Direccion.objects.create(
        usuario=cliente, calle="Otra", latitud=-5.20, longitud=-80.60)
    respuesta = api(admin).patch(
        f"/api/v1/pedidos/{pedido.pk}/", {"direccion_destino": otro.id},
        format="json")

    assert respuesta.status_code == 200, respuesta.data
    pedido.refresh_from_db()
    assert pedido.ruta_geometria is None
    assert pedido.ruta_distancia_km is None

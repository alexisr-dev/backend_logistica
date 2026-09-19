import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.pedidos.models import Pedido, EstadoPedido
from apps.usuarios.models import Direccion, PerfilRepartidor

Usuario = get_user_model()

URL = "/api/v1/usuarios/mi-perfil-repartidor/"


def api(usuario):
    cliente = APIClient()
    cliente.force_authenticate(user=usuario)
    return cliente


@pytest.fixture
def repartidor(db):
    usuario = Usuario.objects.create_user(
        email="rep@d.com", password="x", nombre="R", apellido="Z", rol="repartidor")
    PerfilRepartidor.objects.get_or_create(usuario=usuario)
    return usuario


@pytest.mark.django_db
def test_el_repartidor_cambia_su_disponibilidad(repartidor):
    respuesta = api(repartidor).patch(URL, {"disponible": False}, format="json")

    assert respuesta.status_code == 200
    assert respuesta.data["disponible"] is False
    assert PerfilRepartidor.objects.get(usuario=repartidor).disponible is False


@pytest.mark.django_db
def test_no_puede_inflarse_la_calificacion(repartidor):
    perfil = PerfilRepartidor.objects.get(usuario=repartidor)
    perfil.calificacion_promedio = 3
    perfil.save()

    respuesta = api(repartidor).patch(
        URL, {"disponible": True, "calificacion_promedio": "5.00"}, format="json")

    assert respuesta.status_code == 200
    perfil.refresh_from_db()
    assert float(perfil.calificacion_promedio) == 3.0


@pytest.mark.django_db
def test_un_cliente_no_tiene_perfil_de_repartidor(db):
    cliente = Usuario.objects.create_user(
        email="cli@d.com", password="x", nombre="C", apellido="L", rol="cliente")

    assert api(cliente).get(URL).status_code == 403
    assert api(cliente).patch(URL, {"disponible": True}, format="json").status_code == 403


@pytest.mark.django_db
def test_perfil_ausente_no_rompe_la_pantalla(db):
    usuario = Usuario.objects.create_user(
        email="viejo@d.com", password="x", nombre="V", apellido="J", rol="repartidor")
    PerfilRepartidor.objects.filter(usuario=usuario).delete()

    respuesta = api(usuario).get(URL)

    assert respuesta.status_code == 200
    assert PerfilRepartidor.objects.filter(usuario=usuario).exists()


@pytest.mark.django_db
def test_borrar_direccion_en_uso_responde_409_y_no_500(db, estados_pedido):
    cliente = Usuario.objects.create_user(
        email="cli2@d.com", password="x", nombre="C", apellido="L", rol="cliente")
    origen = Direccion.objects.create(usuario=cliente, calle="Almacén", latitud=0, longitud=0)
    destino = Direccion.objects.create(usuario=cliente, calle="Destino", latitud=1, longitud=1)
    Pedido.objects.create(
        cliente=cliente, direccion_origen=origen, direccion_destino=destino,
        estado=EstadoPedido.objects.get(codigo="pendiente"),
    )

    respuesta = api(cliente).delete(f"/api/v1/usuarios/direcciones/{destino.id}/")

    assert respuesta.status_code == 409
    assert respuesta.data["codigo"] == "direccion_en_uso"
    assert Direccion.objects.filter(pk=destino.pk).exists()


@pytest.mark.django_db
def test_borrar_direccion_libre_funciona(db):
    cliente = Usuario.objects.create_user(
        email="cli3@d.com", password="x", nombre="C", apellido="L", rol="cliente")
    suelta = Direccion.objects.create(usuario=cliente, calle="Sin uso", latitud=0, longitud=0)

    respuesta = api(cliente).delete(f"/api/v1/usuarios/direcciones/{suelta.id}/")

    assert respuesta.status_code == 204
    assert not Direccion.objects.filter(pk=suelta.pk).exists()

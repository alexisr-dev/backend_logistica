import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

Usuario = get_user_model()


@pytest.fixture
def repartidor(db):
    return Usuario.objects.create_user(
        email="rep@t.com", password="x", nombre="R", apellido="P", rol="repartidor")


def api(usuario):
    cliente = APIClient()
    cliente.force_authenticate(user=usuario)
    return cliente


@pytest.mark.django_db
def test_repartidor_consulta_su_propio_rendimiento(repartidor):
    respuesta = api(repartidor).get("/api/v1/reportes/mi-rendimiento/")
    assert respuesta.status_code == 200
    assert respuesta.data["repartidor_id"] == repartidor.id
    # Sin entregas todavía: responde ceros en vez de fallar.
    assert respuesta.data["total_entregas"] == 0


@pytest.mark.django_db
def test_listado_general_sigue_siendo_de_administradores(repartidor):
    respuesta = api(repartidor).get("/api/v1/reportes/rendimiento-repartidores/")
    assert respuesta.status_code == 403

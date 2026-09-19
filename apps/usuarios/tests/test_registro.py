import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.usuarios.models import PerfilRepartidor

Usuario = get_user_model()

REGISTRO = "/api/v1/usuarios/registro/"
CLAVE = "Trufa#Naranja7"


def datos(**extra):
    base = {
        "email": "nuevo@correo.com",
        "password": CLAVE,
        "nombre": "Nuevo",
        "apellido": "Cliente",
        "telefono": "999888777",
    }
    base.update(extra)
    return base


@pytest.mark.django_db
def test_registro_publico_fuerza_rol_cliente():
    # `rol` es read_only en el registro público.
    respuesta = APIClient().post(REGISTRO, datos(rol="administrador"), format="json")

    assert respuesta.status_code == 201, respuesta.data
    assert respuesta.data["usuario"]["rol"] == "cliente"
    assert Usuario.objects.get(email="nuevo@correo.com").rol == "cliente"


@pytest.mark.django_db
def test_registro_devuelve_tokens_utilizables():
    respuesta = APIClient().post(REGISTRO, datos(), format="json")

    assert respuesta.status_code == 201, respuesta.data
    assert "access" in respuesta.data and "refresh" in respuesta.data

    autenticado = APIClient()
    autenticado.credentials(HTTP_AUTHORIZATION=f"Bearer {respuesta.data['access']}")
    perfil = autenticado.get("/api/v1/usuarios/yo/")

    assert perfil.status_code == 200, perfil.data
    assert perfil.data["email"] == "nuevo@correo.com"


@pytest.mark.django_db
def test_registro_rechaza_contrasena_debil():
    respuesta = APIClient().post(REGISTRO, datos(password="12345678"), format="json")

    assert respuesta.status_code == 400
    assert "password" in respuesta.data
    assert not Usuario.objects.filter(email="nuevo@correo.com").exists()


@pytest.mark.django_db
def test_registro_rechaza_email_duplicado_ignorando_mayusculas():
    assert APIClient().post(REGISTRO, datos(), format="json").status_code == 201

    respuesta = APIClient().post(
        REGISTRO, datos(email="Nuevo@Correo.com"), format="json"
    )

    assert respuesta.status_code == 400
    assert "email" in respuesta.data
    assert Usuario.objects.filter(email="nuevo@correo.com").count() == 1


@pytest.mark.django_db
def test_registro_no_crea_perfil_repartidor():
    APIClient().post(REGISTRO, datos(rol="repartidor"), format="json")

    assert PerfilRepartidor.objects.count() == 0

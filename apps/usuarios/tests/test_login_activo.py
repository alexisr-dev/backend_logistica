import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

Usuario = get_user_model()

LOGIN = "/api/v1/auth/login/"
YO = "/api/v1/usuarios/yo/"
CLAVE = "Trufa#Naranja7"


@pytest.fixture
def usuario(db):
    return Usuario.objects.create_user(
        email="baja@x.com", password=CLAVE, nombre="Bea", apellido="Baja",
    )


@pytest.mark.django_db
def test_usuario_desactivado_no_puede_iniciar_sesion(usuario):
    usuario.activo = False
    usuario.save()

    respuesta = APIClient().post(
        LOGIN, {"email": "baja@x.com", "password": CLAVE}, format="json"
    )

    assert respuesta.status_code == 401


@pytest.mark.django_db
def test_token_emitido_antes_de_desactivar_deja_de_servir(usuario):
    login = APIClient().post(
        LOGIN, {"email": "baja@x.com", "password": CLAVE}, format="json"
    )
    assert login.status_code == 200
    token = login.data["access"]

    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert cliente.get(YO).status_code == 200

    usuario.activo = False
    usuario.save()

    # Sin el espejo de is_active, este token seguiría valiendo hasta una hora.
    assert cliente.get(YO).status_code == 401


@pytest.mark.django_db
def test_reactivar_al_usuario_restaura_el_acceso(usuario):
    usuario.activo = False
    usuario.save()
    usuario.activo = True
    usuario.save()

    respuesta = APIClient().post(
        LOGIN, {"email": "baja@x.com", "password": CLAVE}, format="json"
    )

    assert respuesta.status_code == 200


@pytest.mark.django_db
def test_desactivar_sincroniza_is_active(usuario):
    usuario.activo = False
    usuario.save(update_fields=["activo"])

    usuario.refresh_from_db()
    assert usuario.is_active is False


@pytest.mark.django_db
def test_cambiar_la_contrasena_invalida_las_sesiones_abiertas(usuario):
    login = APIClient().post(
        LOGIN, {"email": "baja@x.com", "password": CLAVE}, format="json"
    )
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    assert cliente.get(YO).status_code == 200

    usuario.set_password("OtraClave#2026")
    usuario.save()

    # CHECK_REVOKE_TOKEN: es lo que se espera tras recuperar una cuenta robada.
    assert cliente.get(YO).status_code == 401

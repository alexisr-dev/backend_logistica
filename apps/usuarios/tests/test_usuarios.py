import pytest
from django.contrib.auth import get_user_model

Usuario = get_user_model()


@pytest.mark.django_db
def test_crear_usuario_cliente():
    u = Usuario.objects.create_user(
        email="cliente@test.com", password="clave1234", nombre="Ana", apellido="Pérez"
    )
    assert u.rol == "cliente"
    assert u.check_password("clave1234")
    assert str(u) == "Ana Pérez (cliente)"


@pytest.mark.django_db
def test_crear_superusuario():
    admin = Usuario.objects.create_superuser(
        email="admin@test.com", password="clave1234", nombre="Root", apellido="Admin"
    )
    assert admin.rol == "administrador"
    assert admin.is_staff and admin.is_superuser

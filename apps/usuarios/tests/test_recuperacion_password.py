import re
from datetime import timedelta
from smtplib import SMTPException
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.usuarios.models import CodigoRecuperacion
from apps.usuarios.services import _hash_codigo

Usuario = get_user_model()

SOLICITAR = "/api/v1/auth/password-reset/"
CONFIRMAR = "/api/v1/auth/password-reset/confirmar/"
LOGIN = "/api/v1/auth/login/"
CLAVE_NUEVA = "Trufa#Naranja7"


@pytest.fixture
def cliente_registrado(db):
    return Usuario.objects.create_user(
        email="ana@correo.com", password="ClaveVieja#4", nombre="Ana", apellido="Pérez",
    )


def api():
    return APIClient()


def codigo_del_correo():
    assert len(mail.outbox) == 1, f"se esperaba 1 correo, hay {len(mail.outbox)}"
    encontrados = re.findall(r"\b\d{6}\b", mail.outbox[0].body)
    assert encontrados, f"no hay código en el cuerpo: {mail.outbox[0].body!r}"
    return encontrados[0]


@pytest.mark.django_db
def test_flujo_completo_de_recuperacion_cambia_la_contrasena(cliente_registrado):
    respuesta = api().post(SOLICITAR, {"email": "ana@correo.com"}, format="json")
    assert respuesta.status_code == 200, respuesta.data
    assert respuesta.data["expira_en_minutos"] == 15

    codigo = codigo_del_correo()
    assert mail.outbox[0].to == ["ana@correo.com"]

    respuesta = api().post(
        CONFIRMAR,
        {"email": "ana@correo.com", "codigo": codigo, "password_nueva": CLAVE_NUEVA},
        format="json",
    )
    assert respuesta.status_code == 200, respuesta.data

    cliente_registrado.refresh_from_db()
    assert cliente_registrado.check_password(CLAVE_NUEVA)

    login = api().post(
        LOGIN, {"email": "ana@correo.com", "password": CLAVE_NUEVA}, format="json"
    )
    assert login.status_code == 200, login.data


@pytest.mark.django_db
def test_email_inexistente_responde_200_sin_crear_codigo_ni_enviar_correo(cliente_registrado):
    respuesta = api().post(SOLICITAR, {"email": "nadie@correo.com"}, format="json")

    # Misma respuesta que con un correo real.
    assert respuesta.status_code == 200
    assert "Si el correo está registrado" in respuesta.data["detail"]
    assert CodigoRecuperacion.objects.count() == 0
    assert mail.outbox == []


@pytest.mark.django_db
def test_usuario_desactivado_no_recibe_codigo(cliente_registrado):
    cliente_registrado.activo = False
    cliente_registrado.save()

    respuesta = api().post(SOLICITAR, {"email": "ana@correo.com"}, format="json")

    assert respuesta.status_code == 200
    assert CodigoRecuperacion.objects.count() == 0
    assert mail.outbox == []


@pytest.mark.django_db
def test_codigo_expirado_no_cambia_la_contrasena(cliente_registrado):
    api().post(SOLICITAR, {"email": "ana@correo.com"}, format="json")
    codigo = codigo_del_correo()

    registro = CodigoRecuperacion.objects.get()
    registro.expira_en = timezone.now() - timedelta(minutes=1)
    registro.save(update_fields=["expira_en"])

    respuesta = api().post(
        CONFIRMAR,
        {"email": "ana@correo.com", "codigo": codigo, "password_nueva": CLAVE_NUEVA},
        format="json",
    )

    assert respuesta.status_code == 400
    assert respuesta.data["detail"].code == "codigo_invalido"
    cliente_registrado.refresh_from_db()
    assert cliente_registrado.check_password("ClaveVieja#4")


@pytest.mark.django_db
def test_codigo_incorrecto_suma_intentos_y_se_agota_al_quinto(cliente_registrado):
    api().post(SOLICITAR, {"email": "ana@correo.com"}, format="json")
    correcto = codigo_del_correo()
    incorrecto = "000000" if correcto != "000000" else "111111"

    for _ in range(4):
        respuesta = api().post(
            CONFIRMAR,
            {"email": "ana@correo.com", "codigo": incorrecto, "password_nueva": CLAVE_NUEVA},
            format="json",
        )
        assert respuesta.status_code == 400

    registro = CodigoRecuperacion.objects.get()
    assert registro.intentos_fallidos == 4
    assert registro.usado_en is None

    # El quinto fallo quema el código: hay que pedir uno nuevo.
    api().post(
        CONFIRMAR,
        {"email": "ana@correo.com", "codigo": incorrecto, "password_nueva": CLAVE_NUEVA},
        format="json",
    )
    registro.refresh_from_db()
    assert registro.intentos_fallidos == 5
    assert registro.usado_en is not None

    respuesta = api().post(
        CONFIRMAR,
        {"email": "ana@correo.com", "codigo": correcto, "password_nueva": CLAVE_NUEVA},
        format="json",
    )
    assert respuesta.status_code == 400
    cliente_registrado.refresh_from_db()
    assert cliente_registrado.check_password("ClaveVieja#4")


@pytest.mark.django_db
def test_el_codigo_no_se_puede_reutilizar(cliente_registrado):
    api().post(SOLICITAR, {"email": "ana@correo.com"}, format="json")
    codigo = codigo_del_correo()

    cuerpo = {"email": "ana@correo.com", "codigo": codigo, "password_nueva": CLAVE_NUEVA}
    assert api().post(CONFIRMAR, cuerpo, format="json").status_code == 200

    otra = {**cuerpo, "password_nueva": "OtraClave#9"}
    assert api().post(CONFIRMAR, otra, format="json").status_code == 400

    cliente_registrado.refresh_from_db()
    assert cliente_registrado.check_password(CLAVE_NUEVA)


@pytest.mark.django_db
def test_solicitar_un_codigo_nuevo_invalida_el_anterior(cliente_registrado):
    api().post(SOLICITAR, {"email": "ana@correo.com"}, format="json")
    primero = codigo_del_correo()
    mail.outbox.clear()

    api().post(SOLICITAR, {"email": "ana@correo.com"}, format="json")
    segundo = codigo_del_correo()

    respuesta = api().post(
        CONFIRMAR,
        {"email": "ana@correo.com", "codigo": primero, "password_nueva": CLAVE_NUEVA},
        format="json",
    )
    assert respuesta.status_code == 400

    respuesta = api().post(
        CONFIRMAR,
        {"email": "ana@correo.com", "codigo": segundo, "password_nueva": CLAVE_NUEVA},
        format="json",
    )
    assert respuesta.status_code == 200, respuesta.data


@pytest.mark.django_db
def test_contrasena_debil_no_consume_el_codigo(cliente_registrado):
    api().post(SOLICITAR, {"email": "ana@correo.com"}, format="json")
    codigo = codigo_del_correo()

    respuesta = api().post(
        CONFIRMAR,
        {"email": "ana@correo.com", "codigo": codigo, "password_nueva": "12345678"},
        format="json",
    )
    assert respuesta.status_code == 400
    assert "password_nueva" in respuesta.data

    # El código sigue vivo: el usuario corrige la contraseña sin pedir otro.
    assert CodigoRecuperacion.objects.get().usado_en is None

    respuesta = api().post(
        CONFIRMAR,
        {"email": "ana@correo.com", "codigo": codigo, "password_nueva": CLAVE_NUEVA},
        format="json",
    )
    assert respuesta.status_code == 200, respuesta.data


@pytest.mark.django_db
def test_el_codigo_se_guarda_hasheado(cliente_registrado):
    api().post(SOLICITAR, {"email": "ana@correo.com"}, format="json")
    codigo = codigo_del_correo()

    registro = CodigoRecuperacion.objects.get()
    assert registro.codigo_hash != codigo
    assert len(registro.codigo_hash) == 64
    assert registro.codigo_hash == _hash_codigo(codigo)


@pytest.mark.django_db
def test_demasiadas_solicitudes_por_ip_devuelven_429(cliente_registrado):
    cliente = api()
    # Variando el correo se aísla el límite por IP (10/hora).
    respuestas = [
        cliente.post(SOLICITAR, {"email": f"otro{i}@correo.com"}, format="json").status_code
        for i in range(11)
    ]
    assert respuestas[-1] == 429, respuestas


@pytest.mark.django_db
def test_demasiadas_solicitudes_para_el_mismo_email_devuelven_429(cliente_registrado):
    cliente = api()
    respuestas = [
        cliente.post(SOLICITAR, {"email": "ana@correo.com"}, format="json").status_code
        for i in range(6)
    ]
    assert respuestas[-1] == 429, respuestas


@pytest.mark.django_db
def test_el_fallo_del_envio_no_rompe_la_peticion(cliente_registrado):
    # Un 500 aquí delataría qué correos existen.
    with patch(
        "apps.usuarios.emails.enviar_codigo_recuperacion",
        side_effect=SMTPException("smtp caído"),
    ):
        respuesta = api().post(SOLICITAR, {"email": "ana@correo.com"}, format="json")

    assert respuesta.status_code == 200
    assert CodigoRecuperacion.objects.count() == 1

import secrets
import string

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as ValidationErrorDjango
from rest_framework import serializers


def generar_codigo_seguimiento(prefijo: str = "LOG") -> str:
    alfabeto = string.ascii_uppercase + string.digits
    sufijo = "".join(secrets.choice(alfabeto) for _ in range(8))
    return f"{prefijo}-{sufijo}"


def generar_codigo_numerico(longitud: int = 6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(longitud))


def validar_fortaleza_password(password: str, usuario=None) -> str:
    try:
        validate_password(password, user=usuario)
    except ValidationErrorDjango as exc:
        raise serializers.ValidationError(list(exc.messages)) from exc
    return password

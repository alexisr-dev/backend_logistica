import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework import serializers

from core.exceptions import CodigoRecuperacionInvalido
from core.utils import generar_codigo_numerico, validar_fortaleza_password

from .models import CodigoRecuperacion

logger = logging.getLogger(__name__)

Usuario = get_user_model()

# Sal fija del HMAC, propia de este uso.
_SAL_RECUPERACION = "usuarios.recuperacion"


def _hash_codigo(codigo: str) -> str:
    return salted_hmac(_SAL_RECUPERACION, codigo, algorithm="sha256").hexdigest()


def _despachar_email(usuario, codigo: str) -> None:
    if getattr(settings, "CELERY_ENABLED", False):
        try:
            from .tasks import enviar_codigo_recuperacion_async

            enviar_codigo_recuperacion_async.delay(usuario.pk, codigo)
            return
        except Exception:
            logger.exception("No se pudo encolar el código de recuperación en Celery.")
            return

    try:
        from .emails import enviar_codigo_recuperacion

        enviar_codigo_recuperacion(usuario, codigo)
    except Exception:
        logger.exception("Fallo al enviar el código de recuperación a %s.", usuario.pk)


def solicitar_recuperacion(email: str, ip: str | None = None) -> None:
    usuario = Usuario.objects.filter(email__iexact=email.strip(), activo=True).first()
    if usuario is None:
        return

    # Invalida los códigos anteriores, que quede solo uno activo.
    usuario.codigos_recuperacion.filter(usado_en__isnull=True).update(usado_en=timezone.now())

    codigo = generar_codigo_numerico(settings.PASSWORD_RESET_LONGITUD_CODIGO)
    CodigoRecuperacion.objects.create(
        usuario=usuario,
        codigo_hash=_hash_codigo(codigo),
        expira_en=timezone.now() + timedelta(minutes=settings.PASSWORD_RESET_CODIGO_MINUTOS),
        ip_solicitante=ip,
    )
    _despachar_email(usuario, codigo)


def confirmar_recuperacion(email: str, codigo: str, password_nueva: str):
    usuario = Usuario.objects.filter(email__iexact=email.strip(), activo=True).first()
    if usuario is None:
        raise CodigoRecuperacionInvalido()

    registro = (
        usuario.codigos_recuperacion.filter(usado_en__isnull=True)
        .order_by("-fecha_creacion")
        .first()
    )
    if registro is None:
        raise CodigoRecuperacionInvalido()

    if registro.expira_en <= timezone.now():
        registro.usado_en = timezone.now()
        registro.save(update_fields=["usado_en"])
        raise CodigoRecuperacionInvalido()

    if not constant_time_compare(_hash_codigo(codigo), registro.codigo_hash):
        # Comparación en tiempo constante para evitar timing attacks.
        registro.intentos_fallidos += 1
        campos = ["intentos_fallidos"]
        if registro.intentos_fallidos >= settings.PASSWORD_RESET_MAX_INTENTOS:
            registro.usado_en = timezone.now()
            campos.append("usado_en")
        registro.save(update_fields=campos)
        raise CodigoRecuperacionInvalido()

    # Validamos la fortaleza antes de consumir el código, para poder reintentar.
    try:
        validar_fortaleza_password(password_nueva, usuario)
    except serializers.ValidationError as exc:
        # Re-lanzamos con la clave del campo para mostrarlo en el input.
        raise serializers.ValidationError({"password_nueva": exc.detail}) from exc

    usuario.set_password(password_nueva)
    usuario.save(update_fields=["password", "fecha_actualizacion"])

    registro.usado_en = timezone.now()
    registro.save(update_fields=["usado_en"])
    # Por si quedara alguno vivo de una carrera entre dos solicitudes.
    usuario.codigos_recuperacion.filter(usado_en__isnull=True).update(usado_en=timezone.now())

    return usuario


def contar_referencias_protegidas(usuario) -> dict:
    from apps.pedidos.models import Pedido
    from apps.rutas.models import Ruta

    referencias = {
        "pedidos": Pedido.objects.filter(cliente=usuario).count(),
        "rutas": Ruta.objects.filter(repartidor=usuario).count(),
    }
    return {clave: total for clave, total in referencias.items() if total}


def eliminar_o_desactivar(usuario) -> tuple:
    referencias = contar_referencias_protegidas(usuario)
    if not referencias:
        try:
            with transaction.atomic():
                usuario.delete()
            return "eliminado", {}
        except ProtectedError:
            # Por si hay otra relación PROTECT que no contamos arriba.
            referencias = contar_referencias_protegidas(usuario)

    usuario.activo = False
    usuario.save(update_fields=["activo", "is_active", "fecha_actualizacion"])
    return "desactivado", referencias

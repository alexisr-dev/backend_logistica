import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def notificar(usuario, *, tipo, titulo, mensaje, pedido=None, push=True):
    if usuario is None:
        return None

    # Import perezoso para evitar un ciclo entre apps.
    from .models import Notificacion

    notificacion = Notificacion.objects.create(
        usuario=usuario, pedido=pedido, tipo=tipo, titulo=titulo, mensaje=mensaje
    )

    if push:
        _encolar_push(usuario, mensaje, pedido)

    return notificacion


def _encolar_push(usuario, mensaje, pedido):
    if not getattr(settings, "CELERY_ENABLED", False):
        return

    try:
        from .tasks import enviar_notificacion_async

        enviar_notificacion_async.delay(
            usuario.id,
            mensaje,
            pedido.codigo_seguimiento if pedido else "",
        )
    except Exception:
        # No se re-lanza: un broker caído no debe frenar el pedido.
        logger.warning("No se pudo encolar la notificación push", exc_info=True)

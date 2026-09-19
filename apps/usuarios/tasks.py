import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def enviar_codigo_recuperacion_async(usuario_id: int, codigo: str):
    from django.contrib.auth import get_user_model

    from .emails import enviar_codigo_recuperacion

    usuario = get_user_model().objects.filter(pk=usuario_id).first()
    if usuario is None:
        logger.warning("Usuario %s ya no existe; no se envía el código.", usuario_id)
        return
    enviar_codigo_recuperacion(usuario, codigo)

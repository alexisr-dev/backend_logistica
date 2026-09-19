from celery import shared_task


@shared_task
def enviar_notificacion_async(usuario_id: int, estado: str, codigo_seguimiento: str):
    # Placeholder: sustituir por FCM/SMTP real.
    print(
        f"[NOTIFICACIÓN] Usuario {usuario_id}: tu pedido {codigo_seguimiento} "
        f"ahora está '{estado}'."
    )
    return {"usuario_id": usuario_id, "codigo": codigo_seguimiento, "estado": estado}


@shared_task
def refrescar_reportes():
    return "ok"

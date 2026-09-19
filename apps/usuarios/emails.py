from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def enviar_codigo_recuperacion(usuario, codigo: str) -> None:
    contexto = {
        "nombre": usuario.nombre,
        "codigo": codigo,
        "minutos": settings.PASSWORD_RESET_CODIGO_MINUTOS,
    }
    texto = render_to_string("emails/codigo_recuperacion.txt", contexto)
    html = render_to_string("emails/codigo_recuperacion.html", contexto)

    mensaje = EmailMultiAlternatives(
        subject="Tu código para restablecer la contraseña",
        body=texto,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[usuario.email],
    )
    mensaje.attach_alternative(html, "text/html")
    mensaje.send(fail_silently=False)

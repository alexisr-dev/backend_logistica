from .base import *  # noqa

DEBUG = True

# El móvil llega por la IP de LAN, que cambia según la red.
ALLOWED_HOSTS = ["*"]

# Capa en memoria: evita depender de un Redis corriendo en desarrollo.
# Solo sirve dentro de un mismo proceso (un daphne). Para probar con
# Redis real: comentar esta línea y `docker compose up -d redis`.
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

INTERNAL_IPS = ["127.0.0.1"]

# Sin credenciales SMTP en .env, el correo se lee en la consola de daphne.

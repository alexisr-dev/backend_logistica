from .base import *  # noqa

DEBUG = False

# Base de datos rápida en memoria para tests
DATABASES["default"] = {  # noqa
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": ":memory:",
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
CELERY_TASK_ALWAYS_EAGER = True

# Forzado: si hay credenciales SMTP reales en el .env, base.py elegiría
# ese backend y los tests intentarían enviar correo de verdad.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

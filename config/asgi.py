import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

# La app HTTP debe inicializarse antes de importar consumers/routing
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from apps.tracking.routing import websocket_urlpatterns  # noqa: E402
from core.ws_auth import JWTAuthMiddleware  # noqa: E402

# JWT y no AuthMiddlewareStack: web y móvil usan tokens Bearer, no cookies.
application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
    }
)

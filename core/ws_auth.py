from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

Usuario = get_user_model()


@database_sync_to_async
def _usuario_desde_token(token_crudo: str):
    try:
        token = AccessToken(token_crudo)
        return Usuario.objects.get(pk=token["user_id"], activo=True)
    except (TokenError, KeyError, Usuario.DoesNotExist):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):

    async def __call__(self, scope, receive, send):
        params = parse_qs(scope.get("query_string", b"").decode())
        token = (params.get("token") or [None])[0]

        scope["user"] = await _usuario_desde_token(token) if token else AnonymousUser()

        return await super().__call__(scope, receive, send)

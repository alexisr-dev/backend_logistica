import hashlib

from rest_framework.throttling import SimpleRateThrottle


class ThrottlePorIP(SimpleRateThrottle):

    scope = None

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class ThrottlePorEmail(SimpleRateThrottle):

    scope = None

    def get_cache_key(self, request, view):
        email = (request.data or {}).get("email") if hasattr(request, "data") else None
        if not email or not isinstance(email, str):
            # Sin email no hay nada que limitar.
            return None
        normalizado = email.strip().lower().encode("utf-8")
        return self.cache_format % {
            "scope": self.scope,
            "ident": hashlib.sha256(normalizado).hexdigest(),
        }


class SolicitudRecuperacionPorIP(ThrottlePorIP):
    scope = "recuperacion_ip"


class SolicitudRecuperacionPorEmail(ThrottlePorEmail):
    scope = "recuperacion_email"


class ConfirmacionRecuperacionPorIP(ThrottlePorIP):
    scope = "recuperacion_confirmar_ip"


class RegistroPorIP(ThrottlePorIP):
    scope = "registro_ip"

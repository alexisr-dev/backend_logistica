from rest_framework.permissions import BasePermission


class EsAdministrador(BasePermission):
    message = "Solo administradores pueden realizar esta acción."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol == "administrador")


class EsRepartidor(BasePermission):
    message = "Solo repartidores pueden realizar esta acción."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol == "repartidor")


class EsCliente(BasePermission):
    message = "Solo clientes pueden realizar esta acción."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol == "cliente")


class EsPropietarioOAdmin(BasePermission):

    def has_object_permission(self, request, view, obj):
        if request.user.rol == "administrador":
            return True
        propietario = getattr(obj, "usuario", None) or getattr(obj, "cliente", None)
        return propietario == request.user


class EsElMismoUsuarioOAdmin(BasePermission):

    message = "Solo puedes consultar tu propia ficha de usuario."

    def has_object_permission(self, request, view, obj):
        if request.user.rol == "administrador":
            return True
        return obj.pk == request.user.pk

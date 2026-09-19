from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q, ProtectedError
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from . import services
from .models import Direccion, PerfilRepartidor
from .serializers import (
    ConfirmarRecuperacionSerializer,
    MiPerfilRepartidorSerializer,
    UsuarioSerializer,
    UsuarioActualizarSerializer,
    UsuarioCrearSerializer,
    RegistroSerializer,
    DireccionSerializer,
    SolicitarRecuperacionSerializer,
)
from core.permissions import EsAdministrador, EsElMismoUsuarioOAdmin, EsRepartidor
from core.throttling import (
    ConfirmacionRecuperacionPorIP,
    RegistroPorIP,
    SolicitudRecuperacionPorEmail,
    SolicitudRecuperacionPorIP,
)

Usuario = get_user_model()


class RegistroView(viewsets.GenericViewSet):

    serializer_class = RegistroSerializer
    permission_classes = [permissions.AllowAny]
    # Sin autenticación: quien se registra no tiene sesión aún.
    authentication_classes = []
    throttle_classes = [RegistroPorIP]
    queryset = Usuario.objects.all()

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = serializer.save()

        # Devolvemos los tokens para que la app entre directa tras el alta.
        refresh = RefreshToken.for_user(usuario)
        return Response(
            {
                "usuario": UsuarioSerializer(usuario).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class RecuperacionPasswordViewSet(viewsets.GenericViewSet):

    permission_classes = [permissions.AllowAny]
    # Sin autenticación: el caso típico es justo una sesión perdida.
    authentication_classes = []
    queryset = Usuario.objects.none()

    def get_serializer_class(self):
        if self.action == "confirmar":
            return ConfirmarRecuperacionSerializer
        return SolicitarRecuperacionSerializer

    def get_throttles(self):
        if self.action == "confirmar":
            return [ConfirmacionRecuperacionPorIP()]
        # Doble límite: por IP y por email.
        return [SolicitudRecuperacionPorIP(), SolicitudRecuperacionPorEmail()]

    def _ip_de(self, request):
        reenviada = request.META.get("HTTP_X_FORWARDED_FOR")
        if reenviada:
            return reenviada.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.solicitar_recuperacion(
            serializer.validated_data["email"], ip=self._ip_de(request)
        )
        # Misma respuesta exista o no el correo.
        return Response(
            {
                "detail": (
                    "Si el correo está registrado, recibirás un código de 6 dígitos "
                    "en los próximos minutos."
                ),
                "expira_en_minutos": settings.PASSWORD_RESET_CODIGO_MINUTOS,
            }
        )

    @action(detail=False, methods=["post"], url_path="confirmar")
    def confirmar(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        services.confirmar_recuperacion(
            datos["email"], datos["codigo"], datos["password_nueva"]
        )
        return Response(
            {"detail": "Tu contraseña se actualizó correctamente. Ya puedes iniciar sesión."}
        )


class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all().select_related("perfil_repartidor")
    serializer_class = UsuarioSerializer
    filterset_fields = ["rol", "activo"]
    search_fields = ["nombre", "apellido", "email", "telefono"]
    ordering_fields = ["nombre", "apellido", "email", "rol", "fecha_creacion", "activo"]
    # Orden por defecto, necesario para paginar de forma estable.
    ordering = ["-fecha_creacion"]

    def get_serializer_class(self):
        if self.action == "create":
            return UsuarioCrearSerializer
        if self.action in ["update", "partial_update"]:
            return UsuarioActualizarSerializer
        return UsuarioSerializer

    def get_permissions(self):
        # `yo` es como la app móvil recupera su propio perfil tras el login.
        if self.action == "yo":
            return [permissions.IsAuthenticated()]
        # Cada quien ve su propia ficha; el resto es del administrador.
        if self.action == "retrieve":
            return [permissions.IsAuthenticated(), EsElMismoUsuarioOAdmin()]
        if self.action in ["list", "create", "update", "partial_update", "destroy"]:
            return [EsAdministrador()]
        # Las demás acciones declaran su propio permission_classes.
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = serializer.save()
        # Serializer de lectura, para incluir nombre_completo y el perfil.
        return Response(UsuarioSerializer(usuario).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        parcial = kwargs.pop("partial", False)
        instancia = self.get_object()
        serializer = self.get_serializer(instancia, data=request.data, partial=parcial)
        serializer.is_valid(raise_exception=True)
        usuario = serializer.save()
        return Response(UsuarioSerializer(usuario).data)

    def destroy(self, request, *args, **kwargs):
        usuario = self.get_object()

        if usuario.pk == request.user.pk:
            return Response(
                {"detail": "No puedes eliminar tu propia cuenta.", "codigo": "autoeliminacion"},
                status=status.HTTP_409_CONFLICT,
            )

        if usuario.rol == Usuario.Rol.ADMINISTRADOR and not (
            Usuario.objects.filter(rol=Usuario.Rol.ADMINISTRADOR, activo=True)
            .exclude(pk=usuario.pk)
            .exists()
        ):
            return Response(
                {
                    "detail": "No puedes eliminar al último administrador activo.",
                    "codigo": "ultimo_administrador",
                },
                status=status.HTTP_409_CONFLICT,
            )

        datos_previos = {"id": usuario.pk, "email": usuario.email}
        resultado, referencias = services.eliminar_o_desactivar(usuario)

        if resultado == "eliminado":
            return Response(
                {
                    "resultado": "eliminado",
                    "detail": "Usuario eliminado definitivamente.",
                    "usuario": datos_previos,
                }
            )

        detalle = ", ".join(f"{total} {nombre}" for nombre, total in referencias.items())
        return Response(
            {
                "resultado": "desactivado",
                "detail": (
                    f"El usuario tiene historial asociado ({detalle}) y no puede eliminarse "
                    "sin perderlo. Se ha desactivado: ya no podrá iniciar sesión."
                ),
                "motivo": "referencias_protegidas",
                "referencias": referencias,
                "usuario": UsuarioSerializer(usuario).data,
            }
        )

    @action(detail=False, methods=["get"])
    def yo(self, request):
        return Response(UsuarioSerializer(request.user).data)

    @action(detail=False, methods=["get"], permission_classes=[EsAdministrador])
    def repartidores(self, request):
        qs = self.queryset.filter(rol=Usuario.Rol.REPARTIDOR)
        return Response(UsuarioSerializer(qs, many=True).data)

    @action(
        detail=False, methods=["get", "patch"], url_path="mi-perfil-repartidor",
        permission_classes=[EsRepartidor], serializer_class=MiPerfilRepartidorSerializer,
    )
    def mi_perfil_repartidor(self, request):
        # get_or_create por si el usuario es de antes de la signal.
        perfil, _ = PerfilRepartidor.objects.get_or_create(usuario=request.user)

        if request.method == "GET":
            return Response(MiPerfilRepartidorSerializer(perfil).data)

        serializer = MiPerfilRepartidorSerializer(perfil, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class DireccionViewSet(viewsets.ModelViewSet):
    serializer_class = DireccionSerializer
    filterset_fields = ["usuario"]

    def get_queryset(self):
        # El usuario solo ve sus propias direcciones (el admin ve todas).
        if self.request.user.rol == Usuario.Rol.ADMINISTRADOR:
            return Direccion.objects.all()
        return Direccion.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        # El administrador puede crear a nombre de otro; el resto, solo las suyas.
        usuario = serializer.validated_data.get("usuario")
        if self.request.user.rol != Usuario.Rol.ADMINISTRADOR or usuario is None:
            usuario = self.request.user
        serializer.save(usuario=usuario)

    def destroy(self, request, *args, **kwargs):
        direccion = self.get_object()
        try:
            direccion.delete()
        except ProtectedError:
            # Import perezoso para evitar un ciclo entre las apps.
            from apps.pedidos.models import Pedido

            usados = Pedido.objects.filter(
                Q(direccion_origen=direccion) | Q(direccion_destino=direccion)
            ).count()
            return Response(
                {
                    "detail": (
                        f"Esta dirección se usa en {usados} "
                        f"{'pedido' if usados == 1 else 'pedidos'} y no puede "
                        "eliminarse sin perder ese historial."
                    ),
                    "codigo": "direccion_en_uso",
                    "pedidos": usados,
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

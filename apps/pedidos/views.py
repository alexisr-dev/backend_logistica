from django.db.models import Avg
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.rutas.services.osrm_client import calcular_ruta
from apps.usuarios.models import PerfilRepartidor
from core.exceptions import ServicioExternoNoDisponible
from core.permissions import EsAdministrador
from .models import Pedido, EstadoPedido, Calificacion
from .serializers import (
    PedidoSerializer,
    PedidoCrearSerializer,
    EstadoPedidoSerializer,
    CambiarEstadoSerializer,
    CalificacionSerializer,
)
from .services import cambiar_estado


class EstadoPedidoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EstadoPedido.objects.all()
    serializer_class = EstadoPedidoSerializer


# drf-spectacular inspecciona cada método aparte, así que el PATCH necesita
# su propio @extend_schema aunque delegue en `update`.
@extend_schema_view(partial_update=extend_schema(responses=PedidoSerializer))
class PedidoViewSet(viewsets.ModelViewSet):
    serializer_class = PedidoSerializer
    filterset_fields = ["estado", "repartidor", "cliente"]
    search_fields = ["codigo_seguimiento", "descripcion"]

    def get_queryset(self):
        qs = Pedido.objects.select_related(
            "cliente", "repartidor", "estado", "direccion_origen", "direccion_destino"
        ).prefetch_related("historial__estado")
        user = self.request.user
        if user.rol == "cliente":
            return qs.filter(cliente=user)
        if user.rol == "repartidor":
            return qs.filter(repartidor=user)
        return qs  # administrador ve todo

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return PedidoCrearSerializer
        return PedidoSerializer

    def get_permissions(self):
        # Editar un pedido ya creado es tarea del administrador.
        if self.action in ["update", "partial_update", "destroy"]:
            return [EsAdministrador()]
        return [permissions.IsAuthenticated()]

    # ------------------------------------------------------------------
    # Respuesta de las escrituras
    # ------------------------------------------------------------------
    # `PedidoCrearSerializer` es de entrada (recibe IDs); se responde con
    # `PedidoSerializer` para devolver el pedido completo, no el eco de lo
    # que se mandó. `@extend_schema` corrige lo que drf-spectacular deduce.

    def _representacion(self, pedido):
        return PedidoSerializer(pedido, context=self.get_serializer_context()).data

    @extend_schema(responses=PedidoSerializer)
    def create(self, request, *args, **kwargs):
        entrada = self.get_serializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        self.perform_create(entrada)
        salida = self._representacion(entrada.instance)
        return Response(
            salida,
            status=status.HTTP_201_CREATED,
            headers=self.get_success_headers(salida),
        )

    @extend_schema(responses=PedidoSerializer)
    def update(self, request, *args, **kwargs):
        # `partial_update` delega en este método.
        parcial = kwargs.pop("partial", False)
        pedido = self.get_object()
        entrada = self.get_serializer(pedido, data=request.data, partial=parcial)
        entrada.is_valid(raise_exception=True)
        self.perform_update(entrada)

        # El prefetch del historial queda obsoleto tras escribir.
        if getattr(pedido, "_prefetched_objects_cache", None):
            pedido._prefetched_objects_cache = {}

        return Response(self._representacion(entrada.instance))

    def perform_create(self, serializer):
        estado_inicial = EstadoPedido.objects.get(codigo="pendiente")
        # El administrador puede registrar a nombre de otro cliente.
        cliente = serializer.validated_data.get("cliente")
        if self.request.user.rol != "administrador" or cliente is None:
            cliente = self.request.user
        serializer.save(cliente=cliente, estado=estado_inicial)

    def perform_update(self, serializer):
        pedido = serializer.instance
        cambia_recorrido = any(
            campo in serializer.validated_data
            and serializer.validated_data[campo] != getattr(pedido, campo)
            for campo in ("direccion_origen", "direccion_destino")
        )
        # Si cambia la dirección, se limpia la geometría cacheada.
        if cambia_recorrido:
            serializer.save(
                ruta_geometria=None, ruta_distancia_km=None, ruta_duracion_min=None)
        else:
            serializer.save()

    @action(detail=True, methods=["post"], url_path="cambiar-estado")
    def cambiar_estado(self, request, pk=None):
        pedido = self.get_object()
        serializer = CambiarEstadoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        codigo = serializer.validated_data["codigo"]

        self._verificar_puede_cambiar(pedido, request.user, codigo)

        pedido = cambiar_estado(
            pedido,
            codigo,
            usuario=request.user,
            comentario=serializer.validated_data.get("comentario", ""),
        )
        return Response(PedidoSerializer(pedido).data)

    @staticmethod
    def _verificar_puede_cambiar(pedido, usuario, codigo):
        if usuario.rol == "administrador" or pedido.repartidor_id == usuario.id:
            return
        if pedido.cliente_id == usuario.id and codigo == "cancelado":
            return
        raise PermissionDenied(
            "Solo el repartidor asignado o un administrador pueden avanzar el pedido. "
            "Como cliente únicamente puedes cancelarlo."
        )

    @action(detail=True, methods=["get"], url_path="seguimiento")
    def seguimiento(self, request, pk=None):
        pedido = self.get_object()
        return Response(PedidoSerializer(pedido).data["historial"])

    @action(detail=True, methods=["get"])
    def ruta(self, request, pk=None):
        pedido = self.get_object()
        origen = pedido.direccion_origen
        destino = pedido.direccion_destino

        if not pedido.ruta_geometria:
            self._calcular_y_cachear(pedido, origen, destino)

        return Response({
            "geometria": pedido.ruta_geometria,
            "distancia_km": pedido.ruta_distancia_km,
            "duracion_min": pedido.ruta_duracion_min,
            "origen": self._punto(origen),
            "destino": self._punto(destino),
        })

    @staticmethod
    def _punto(direccion):
        return {
            "latitud": direccion.latitud,
            "longitud": direccion.longitud,
            "direccion": direccion.calle,
            "distrito": direccion.distrito,
        }

    @staticmethod
    def _calcular_y_cachear(pedido, origen, destino):
        try:
            resultado = calcular_ruta([
                (origen.latitud, origen.longitud),
                (destino.latitud, destino.longitud),
            ])
        except (ServicioExternoNoDisponible, ValueError):
            return

        pedido.ruta_geometria = resultado["geometria"]
        pedido.ruta_distancia_km = resultado["distancia_km"]
        pedido.ruta_duracion_min = int(resultado["duracion_min"])
        pedido.save(update_fields=[
            "ruta_geometria", "ruta_distancia_km", "ruta_duracion_min",
        ])

    @action(detail=True, methods=["post"])
    def calificar(self, request, pk=None):
        pedido = self.get_object()
        # Solo el cliente que lo recibió puede puntuarlo.
        if pedido.cliente_id != request.user.id:
            raise PermissionDenied("Solo el cliente del pedido puede calificarlo.")
        if not hasattr(pedido, "calificacion"):
            serializer = CalificacionSerializer(data={**request.data, "pedido": pedido.id})
            serializer.is_valid(raise_exception=True)
            calif = serializer.save(cliente=pedido.cliente, repartidor=pedido.repartidor)
            self._actualizar_promedio(pedido.repartidor)
            return Response(CalificacionSerializer(calif).data, status=status.HTTP_201_CREATED)
        return Response(
            {"detail": "Este pedido ya fue calificado."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @staticmethod
    def _actualizar_promedio(repartidor):
        if repartidor is None:
            return
        promedio = Calificacion.objects.filter(repartidor=repartidor).aggregate(
            p=Avg("puntuacion")
        )["p"] or 0
        PerfilRepartidor.objects.filter(usuario=repartidor).update(
            calificacion_promedio=round(promedio, 2)
        )

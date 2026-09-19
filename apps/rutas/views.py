import django_filters
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, status, mixins, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.notificaciones.services import notificar
from apps.pedidos.models import Pedido
from apps.pedidos.services import TRANSICIONES, cambiar_estado
from core.permissions import EsAdministrador
from .models import Ruta, RutaPedido
from .serializers import (
    RutaSerializer,
    CrearRutaSerializer,
    RutaPedidoSerializer,
    MarcarParadaSerializer,
)
from .services.osrm_client import calcular_ruta

# Traduce el resultado de una parada al estado del pedido.
ESTADO_PEDIDO_POR_RESULTADO = {
    RutaPedido.EstadoParada.ENTREGADO: "entregado",
    RutaPedido.EstadoParada.FALLIDO: "devuelto",
}


class RutaFilter(django_filters.FilterSet):

    pedido = django_filters.NumberFilter(field_name="paradas__pedido")

    class Meta:
        model = Ruta
        fields = ["repartidor", "estado", "fecha", "pedido"]


class RutaViewSet(viewsets.ModelViewSet):
    serializer_class = RutaSerializer
    filterset_class = RutaFilter

    def get_queryset(self):
        # Precarga hasta la dirección de destino, para las coordenadas de cada parada.
        qs = Ruta.objects.prefetch_related("paradas__pedido__direccion_destino")
        user = self.request.user
        if user.rol == "repartidor":
            return qs.filter(repartidor=user)
        if user.rol == "cliente":
            # Solo las rutas donde va alguno de sus pedidos.
            return qs.filter(paradas__pedido__cliente=user).distinct()
        return qs  # administrador

    def get_permissions(self):
        # Editar rutas es tarea del administrador.
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [EsAdministrador()]
        # `super()` respeta el permission_classes que declara cada @action.
        return super().get_permissions()

    def _exigir_conductor(self, ruta):
        usuario = self.request.user
        if usuario.rol == "administrador" or ruta.repartidor_id == usuario.id:
            return
        raise PermissionDenied(
            "Solo el repartidor asignado a esta ruta puede cambiar su estado."
        )

    @action(
        detail=False, methods=["post"], url_path="planificar",
        permission_classes=[EsAdministrador],
    )
    def planificar(self, request):
        serializer = CrearRutaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        pedidos = list(
            Pedido.objects.filter(id__in=data["pedidos"]).select_related("direccion_destino")
        )
        # Respetar el orden enviado por el cliente
        pedidos.sort(key=lambda p: data["pedidos"].index(p.id))
        if not pedidos:
            return Response({"detail": "No se encontraron pedidos."}, status=400)

        coordenadas = [
            (p.direccion_destino.latitud, p.direccion_destino.longitud) for p in pedidos
        ]
        # OSRM necesita al menos origen y destino.
        if len(coordenadas) < 2:
            return Response(
                {
                    "detail": "Una ruta necesita al menos dos paradas para calcularse.",
                    "codigo": "paradas_insuficientes",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        resultado = calcular_ruta(coordenadas)

        with transaction.atomic():
            ruta = Ruta.objects.create(
                repartidor_id=data["repartidor"],
                fecha=data["fecha"],
                distancia_total_km=resultado["distancia_km"],
                tiempo_estimado_min=int(resultado["duracion_min"]),
                geometria_ruta=resultado["geometria"],
            )
            RutaPedido.objects.bulk_create(
                [
                    RutaPedido(ruta=ruta, pedido=p, orden_parada=i + 1)
                    for i, p in enumerate(pedidos)
                ]
            )

        # Aviso explícito, aquí se sabe que la ruta es nueva.
        paradas_texto = "parada" if len(pedidos) == 1 else "paradas"
        notificar(
            ruta.repartidor,
            tipo="ruta_asignada",
            titulo="Nueva ruta asignada",
            mensaje=(
                f"Tienes una ruta para el {ruta.fecha} con "
                f"{len(pedidos)} {paradas_texto}."
            ),
        )

        return Response(RutaSerializer(ruta).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True, methods=["post"], url_path="recalcular",
        permission_classes=[EsAdministrador],
    )
    def recalcular(self, request, pk=None):
        ruta = self.get_object()
        paradas = ruta.paradas.select_related("pedido__direccion_destino").order_by("orden_parada")
        coordenadas = [
            (pp.pedido.direccion_destino.latitud, pp.pedido.direccion_destino.longitud)
            for pp in paradas
        ]
        resultado = calcular_ruta(coordenadas)
        ruta.geometria_ruta = resultado["geometria"]
        ruta.distancia_total_km = resultado["distancia_km"]
        ruta.tiempo_estimado_min = int(resultado["duracion_min"])
        ruta.save(update_fields=["geometria_ruta", "distancia_total_km", "tiempo_estimado_min"])

        notificar(
            ruta.repartidor,
            tipo="ruta_actualizada",
            titulo="Tu ruta cambió",
            mensaje=f"Se actualizó el recorrido de tu ruta del {ruta.fecha}.",
        )

        return Response(RutaSerializer(ruta).data)

    @action(detail=True, methods=["post"])
    def iniciar(self, request, pk=None):
        ruta = self.get_object()
        self._exigir_conductor(ruta)

        # Idempotente: el móvil puede reintentar sin que parezca un error.
        if ruta.estado == Ruta.Estado.EN_CURSO:
            return Response(RutaSerializer(ruta).data)
        if ruta.estado != Ruta.Estado.PLANIFICADA:
            return Response(
                {
                    "detail": (
                        f"Una ruta {ruta.get_estado_display().lower()} "
                        "ya no puede iniciarse."
                    ),
                    "codigo": "estado_invalido",
                },
                status=status.HTTP_409_CONFLICT,
            )

        ruta.estado = Ruta.Estado.EN_CURSO
        ruta.save(update_fields=["estado"])
        return Response(RutaSerializer(ruta).data)

    @action(detail=True, methods=["post"])
    def finalizar(self, request, pk=None):
        ruta = self.get_object()
        self._exigir_conductor(ruta)

        if ruta.estado == Ruta.Estado.FINALIZADA:
            return Response(RutaSerializer(ruta).data)
        if ruta.estado == Ruta.Estado.CANCELADA:
            return Response(
                {
                    "detail": "Una ruta cancelada no puede finalizarse.",
                    "codigo": "estado_invalido",
                },
                status=status.HTTP_409_CONFLICT,
            )

        ruta.estado = Ruta.Estado.FINALIZADA
        ruta.save(update_fields=["estado"])
        return Response(RutaSerializer(ruta).data)


class RutaPedidoViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):

    serializer_class = RutaPedidoSerializer

    def get_queryset(self):
        qs = RutaPedido.objects.select_related(
            "ruta", "pedido", "pedido__estado", "pedido__direccion_destino"
        )
        user = self.request.user
        if user.rol == "repartidor":
            return qs.filter(ruta__repartidor=user)
        if user.rol == "cliente":
            return qs.filter(pedido__cliente=user)
        return qs  # administrador

    @action(detail=True, methods=["post"])
    def marcar(self, request, pk=None):
        parada = self.get_object()

        # Un cliente puede ver sus paradas pero no cerrarlas.
        usuario = request.user
        if usuario.rol != "administrador" and parada.ruta.repartidor_id != usuario.id:
            raise PermissionDenied(
                "Solo el repartidor de la ruta puede marcar el resultado de una parada."
            )

        serializer = MarcarParadaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resultado = serializer.validated_data["resultado"]
        comentario = serializer.validated_data.get("comentario", "")

        codigo_destino = ESTADO_PEDIDO_POR_RESULTADO[resultado]
        pedido = parada.pedido
        actual = pedido.estado.codigo

        with transaction.atomic():
            parada.estado_parada = resultado
            parada.hora_real = timezone.now()
            parada.save(update_fields=["estado_parada", "hora_real"])

            if actual == codigo_destino:
                # El pedido ya estaba donde toca (reintento, o lo movió el panel).
                actualizado, motivo = True, None
            elif codigo_destino in TRANSICIONES.get(actual, []):
                cambiar_estado(pedido, codigo_destino, usuario=usuario, comentario=comentario)
                actualizado, motivo = True, None
            else:
                actualizado = False
                motivo = (
                    f"La parada quedó como {resultado}, pero el pedido sigue en "
                    f"{actual}: no se puede pasar de {actual} a {codigo_destino}."
                )

        # Se relee para devolver el estado ya actualizado del pedido.
        parada.refresh_from_db()
        return Response(
            {
                "parada": RutaPedidoSerializer(parada).data,
                "pedido_actualizado": actualizado,
                "estado_pedido": parada.pedido.estado.codigo,
                "motivo": motivo,
            }
        )

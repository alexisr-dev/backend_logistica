from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import UbicacionTiempoReal
from .serializers import UbicacionTiempoRealSerializer


class UbicacionViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):

    serializer_class = UbicacionTiempoRealSerializer
    filterset_fields = ["repartidor", "pedido"]

    def get_queryset(self):
        qs = UbicacionTiempoReal.objects.select_related("repartidor", "pedido")
        user = self.request.user
        # Mismo criterio que el consumer WebSocket: cada quien ve lo suyo.
        if user.rol == "cliente":
            return qs.filter(pedido__cliente=user)
        if user.rol == "repartidor":
            return qs.filter(repartidor=user)
        return qs

    def perform_create(self, serializer):
        serializer.save(repartidor=self.request.user)

    @action(detail=False, methods=["get"], url_path="ultimo/(?P<pedido_id>[^/.]+)")
    def ultimo(self, request, pedido_id=None):
        # get_queryset() para heredar el filtro por rol.
        ubic = self.get_queryset().filter(pedido_id=pedido_id).order_by("-timestamp").first()
        if not ubic:
            return Response({"detail": "Sin ubicaciones registradas."}, status=404)
        return Response(UbicacionTiempoRealSerializer(ubic).data)

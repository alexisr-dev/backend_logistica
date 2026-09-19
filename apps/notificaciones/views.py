from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notificacion
from .serializers import NotificacionSerializer


class NotificacionViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = NotificacionSerializer

    def get_queryset(self):
        return Notificacion.objects.filter(usuario=self.request.user)

    @action(detail=True, methods=["post"], url_path="marcar-leida")
    def marcar_leida(self, request, pk=None):
        notif = self.get_object()
        notif.leido = True
        notif.save(update_fields=["leido"])
        return Response(NotificacionSerializer(notif).data)

    @action(detail=False, methods=["get"], url_path="no-leidas")
    def no_leidas(self, request):
        qs = self.get_queryset().filter(leido=False)
        return Response({"count": qs.count(), "resultados": NotificacionSerializer(qs, many=True).data})

from django.db import connection, DatabaseError
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import EsAdministrador
from .models import RendimientoRepartidor
from .serializers import RendimientoRepartidorSerializer


class ReporteViewSet(viewsets.ViewSet):
    permission_classes = [EsAdministrador]

    @action(detail=False, methods=["get"], url_path="rendimiento-repartidores")
    def rendimiento_repartidores(self, request):
        qs = RendimientoRepartidor.objects.all()
        return Response(RendimientoRepartidorSerializer(qs, many=True).data)

    @action(
        detail=False, methods=["get"], url_path="mi-rendimiento",
        permission_classes=[permissions.IsAuthenticated],
    )
    def mi_rendimiento(self, request):
        try:
            fila = RendimientoRepartidor.objects.filter(repartidor_id=request.user.id).first()
        except DatabaseError:
            # La VIEW solo existe en PostgreSQL, no en SQLite (tests).
            fila = None

        if fila is None:
            # Un repartidor recién creado aún no aparece en la vista.
            return Response({
                "repartidor_id": request.user.id,
                "repartidor": request.user.nombre_completo,
                "total_entregas": 0,
                "entregas_a_tiempo": 0,
                "entregas_tardias": 0,
                "tiempo_promedio_min": None,
                "calificacion_promedio": None,
            })
        return Response(RendimientoRepartidorSerializer(fila).data)

    @action(detail=False, methods=["get"], url_path="resumen")
    def resumen(self, request):
        with connection.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) AS total_pedidos,
                    COUNT(*) FILTER (WHERE ep.codigo = 'entregado') AS entregados,
                    COUNT(*) FILTER (WHERE ep.codigo = 'en_camino') AS en_camino,
                    COUNT(*) FILTER (WHERE ep.codigo = 'cancelado') AS cancelados
                FROM pedidos p
                JOIN estados_pedido ep ON ep.id = p.estado_id
            """)
            row = cur.fetchone()
        return Response({
            "total_pedidos": row[0],
            "entregados": row[1],
            "en_camino": row[2],
            "cancelados": row[3],
        })

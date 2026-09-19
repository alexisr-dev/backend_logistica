from rest_framework import serializers

from .models import RendimientoRepartidor


class RendimientoRepartidorSerializer(serializers.ModelSerializer):
    class Meta:
        model = RendimientoRepartidor
        fields = [
            "repartidor_id", "repartidor", "total_entregas",
            "entregas_a_tiempo", "entregas_tardias",
            "tiempo_promedio_min", "calificacion_promedio",
        ]

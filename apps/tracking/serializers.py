from rest_framework import serializers

from .models import UbicacionTiempoReal


class UbicacionTiempoRealSerializer(serializers.ModelSerializer):
    class Meta:
        model = UbicacionTiempoReal
        fields = ["id", "repartidor", "pedido", "latitud", "longitud", "velocidad_kmh", "timestamp"]
        read_only_fields = ["repartidor", "timestamp"]

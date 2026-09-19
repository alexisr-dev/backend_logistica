from rest_framework import serializers

from .models import Ruta, RutaPedido


class RutaPedidoSerializer(serializers.ModelSerializer):
    codigo_seguimiento = serializers.CharField(source="pedido.codigo_seguimiento", read_only=True)

    # Coordenadas del destino, para dibujar cada parada en el mapa.
    direccion = serializers.CharField(source="pedido.direccion_destino.calle", read_only=True)
    distrito = serializers.CharField(
        source="pedido.direccion_destino.distrito", read_only=True)
    latitud = serializers.FloatField(source="pedido.direccion_destino.latitud", read_only=True)
    longitud = serializers.FloatField(source="pedido.direccion_destino.longitud", read_only=True)

    class Meta:
        model = RutaPedido
        fields = [
            "id", "pedido", "codigo_seguimiento", "orden_parada",
            "hora_estimada", "hora_real", "estado_parada",
            "direccion", "distrito", "latitud", "longitud",
        ]


class RutaSerializer(serializers.ModelSerializer):
    paradas = RutaPedidoSerializer(many=True, read_only=True)

    class Meta:
        model = Ruta
        fields = [
            "id", "repartidor", "fecha", "estado", "distancia_total_km",
            "tiempo_estimado_min", "geometria_ruta", "fecha_creacion", "paradas",
        ]
        read_only_fields = ["distancia_total_km", "tiempo_estimado_min", "geometria_ruta"]


class CrearRutaSerializer(serializers.Serializer):

    repartidor = serializers.IntegerField()
    fecha = serializers.DateField()
    pedidos = serializers.ListField(child=serializers.IntegerField(), min_length=1)


class MarcarParadaSerializer(serializers.Serializer):

    resultado = serializers.ChoiceField(
        choices=[
            RutaPedido.EstadoParada.ENTREGADO,
            RutaPedido.EstadoParada.FALLIDO,
        ]
    )
    # Se guarda en el `comentario` del historial del pedido, que es de 255.
    comentario = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=255
    )

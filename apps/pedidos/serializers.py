from rest_framework import serializers

from apps.usuarios.serializers import UsuarioSerializer, DireccionSerializer
from .models import Pedido, EstadoPedido, HistorialEstadoPedido, Calificacion


class EstadoPedidoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoPedido
        fields = ["id", "codigo", "nombre", "orden"]


class HistorialEstadoPedidoSerializer(serializers.ModelSerializer):
    estado = EstadoPedidoSerializer(read_only=True)

    class Meta:
        model = HistorialEstadoPedido
        fields = ["id", "estado", "usuario", "comentario", "fecha"]


class CalificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Calificacion
        fields = ["id", "pedido", "cliente", "repartidor", "puntuacion", "comentario", "fecha"]
        read_only_fields = ["cliente", "repartidor"]

    def validate_puntuacion(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("La puntuación debe estar entre 1 y 5.")
        return value


class PedidoSerializer(serializers.ModelSerializer):

    cliente = UsuarioSerializer(read_only=True)
    repartidor = UsuarioSerializer(read_only=True)
    estado = EstadoPedidoSerializer(read_only=True)
    direccion_origen = DireccionSerializer(read_only=True)
    direccion_destino = DireccionSerializer(read_only=True)
    historial = HistorialEstadoPedidoSerializer(many=True, read_only=True)
    transiciones_permitidas = serializers.SerializerMethodField()
    # `null` mientras no haya calificación: así la app sabe si mostrar el botón.
    calificacion = CalificacionSerializer(read_only=True)

    class Meta:
        model = Pedido
        fields = [
            "id", "codigo_seguimiento", "cliente", "repartidor",
            "direccion_origen", "direccion_destino", "estado",
            "descripcion", "peso_kg", "costo_envio",
            "fecha_creacion", "fecha_estimada_entrega", "fecha_entrega_real",
            "historial", "transiciones_permitidas", "calificacion",
        ]
        read_only_fields = ["codigo_seguimiento", "fecha_creacion", "fecha_entrega_real"]

    def get_transiciones_permitidas(self, obj):
        from .services import TRANSICIONES

        codigos = TRANSICIONES.get(obj.estado.codigo, [])
        estados = EstadoPedido.objects.filter(codigo__in=codigos)
        return EstadoPedidoSerializer(estados, many=True).data


class PedidoCrearSerializer(serializers.ModelSerializer):

    class Meta:
        model = Pedido
        fields = [
            "id", "cliente", "repartidor", "direccion_origen", "direccion_destino",
            "descripcion", "peso_kg", "costo_envio", "fecha_estimada_entrega",
        ]
        extra_kwargs = {
            # Un cliente crea para sí mismo; el administrador, para cualquiera.
            "cliente": {"required": False},
        }


class CambiarEstadoSerializer(serializers.Serializer):
    codigo = serializers.CharField()
    comentario = serializers.CharField(required=False, allow_blank=True, default="")

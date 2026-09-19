from rest_framework import serializers

from .models import Notificacion


class NotificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacion
        fields = ["id", "usuario", "pedido", "tipo", "titulo", "mensaje", "leido", "fecha_creacion"]
        read_only_fields = ["usuario", "fecha_creacion"]

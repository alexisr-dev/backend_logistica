import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)


class TrackingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.pedido_id = self.scope["url_route"]["kwargs"]["pedido_id"]
        usuario = self.scope.get("user")

        if usuario is None or not usuario.is_authenticated:
            await self.close(code=4401)
            return

        acceso = await self._resolver_acceso(usuario)
        if acceso is None:
            await self.close(code=4404)
            return

        puede_ver, self.puede_emitir = acceso
        if not puede_ver:
            await self.close(code=4403)
            return

        grupo = f"tracking_pedido_{self.pedido_id}"
        try:
            await self.channel_layer.group_add(grupo, self.channel_name)
        except Exception:
            # Sin channel layer no hay retransmisión posible.
            logger.exception("No se pudo suscribir al grupo de tracking %s", grupo)
            await self.close(code=4503)
            return

        # Solo a partir de aquí hay grupo que abandonar en disconnect().
        self.grupo = grupo
        await self.accept()

    async def disconnect(self, close_code):
        # Si se rechazó la conexión en connect(), nunca hubo grupo que abandonar.
        if hasattr(self, "grupo"):
            await self.channel_layer.group_discard(self.grupo, self.channel_name)

    async def receive(self, text_data):
        # Suscribirse y emitir son permisos distintos.
        if not self.puede_emitir:
            return

        try:
            data = json.loads(text_data)
        except (TypeError, ValueError):
            return

        lat = self._coordenada(data.get("lat"), limite=90)
        lng = self._coordenada(data.get("lng"), limite=180)
        if lat is None or lng is None:
            return

        velocidad = data.get("velocidad")
        if velocidad is not None and not isinstance(velocidad, (int, float)):
            velocidad = None

        # Persistir el punto (histórico) sin bloquear el loop asíncrono.
        await self._guardar_ubicacion(lat, lng, velocidad)

        await self.channel_layer.group_send(
            self.grupo,
            {
                "type": "ubicacion_actualizada",
                "lat": lat,
                "lng": lng,
                "velocidad": velocidad,
            },
        )

    async def ubicacion_actualizada(self, event):
        await self.send(text_data=json.dumps({
            "lat": event["lat"],
            "lng": event["lng"],
            "velocidad": event.get("velocidad"),
        }))

    @staticmethod
    def _coordenada(valor, limite):
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return None
        return float(valor) if -limite <= valor <= limite else None

    @database_sync_to_async
    def _resolver_acceso(self, usuario):
        from apps.pedidos.models import Pedido

        try:
            pedido = Pedido.objects.only("cliente_id", "repartidor_id").get(pk=self.pedido_id)
        except Pedido.DoesNotExist:
            return None

        es_admin = usuario.rol == "administrador"
        es_repartidor = pedido.repartidor_id == usuario.id
        es_cliente = pedido.cliente_id == usuario.id

        return (es_admin or es_repartidor or es_cliente, es_admin or es_repartidor)

    @database_sync_to_async
    def _guardar_ubicacion(self, lat, lng, velocidad):
        from apps.usuarios.models import PerfilRepartidor
        from .models import UbicacionTiempoReal

        usuario = self.scope["user"]
        UbicacionTiempoReal.objects.create(
            repartidor=usuario, pedido_id=self.pedido_id,
            latitud=lat, longitud=lng, velocidad_kmh=velocidad,
        )
        # Cachea el último punto en el perfil.
        PerfilRepartidor.objects.filter(usuario=usuario).update(
            ultima_lat=lat, ultima_lng=lng
        )

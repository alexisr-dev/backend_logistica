from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.usuarios.models import PerfilRepartidor, Direccion
from apps.pedidos.models import Pedido, EstadoPedido
from apps.pedidos.services import cambiar_estado

Usuario = get_user_model()


class Command(BaseCommand):
    help = "Carga datos de demostración del sistema de logística."

    def handle(self, *args, **options):
        # --- Administrador ---
        admin, creado = Usuario.objects.get_or_create(
            email="admin@logistica.com",
            defaults=dict(nombre="Admin", apellido="Logística", rol="administrador",
                          is_staff=True, is_superuser=True),
        )
        if creado:
            admin.set_password("admin1234")
            admin.save()
            self.stdout.write(self.style.SUCCESS("Admin creado: admin@logistica.com / admin1234"))

        # --- Repartidor ---
        repartidor, creado = Usuario.objects.get_or_create(
            email="repartidor@logistica.com",
            defaults=dict(nombre="Carlos", apellido="Ruiz", rol="repartidor", telefono="999888777"),
        )
        if creado:
            repartidor.set_password("clave1234")
            repartidor.save()
            PerfilRepartidor.objects.get_or_create(
                usuario=repartidor,
                defaults=dict(tipo_vehiculo="Moto", placa="ABC-123", disponible=True),
            )
            self.stdout.write(self.style.SUCCESS("Repartidor creado: repartidor@logistica.com / clave1234"))

        # --- Cliente ---
        cliente, creado = Usuario.objects.get_or_create(
            email="cliente@logistica.com",
            defaults=dict(nombre="María", apellido="Gómez", rol="cliente", telefono="911222333"),
        )
        if creado:
            cliente.set_password("clave1234")
            cliente.save()
            self.stdout.write(self.style.SUCCESS("Cliente creado: cliente@logistica.com / clave1234"))

        # --- Direcciones (Lima) ---
        origen, _ = Direccion.objects.get_or_create(
            usuario=cliente, alias="Almacén central",
            defaults=dict(calle="Av. Javier Prado", numero="123", distrito="San Isidro",
                          ciudad="Lima", latitud=-12.0931, longitud=-77.0465, es_default=True),
        )
        destino, _ = Direccion.objects.get_or_create(
            usuario=cliente, alias="Casa",
            defaults=dict(calle="Av. Arequipa", numero="456", distrito="Miraflores",
                          ciudad="Lima", latitud=-12.1211, longitud=-77.0300),
        )

        # --- Pedido demo ---
        pendiente = EstadoPedido.objects.get(codigo="pendiente")
        pedido, creado = Pedido.objects.get_or_create(
            cliente=cliente,
            descripcion="Paquete demo — documentos",
            defaults=dict(
                repartidor=repartidor, direccion_origen=origen, direccion_destino=destino,
                estado=pendiente, peso_kg=1.5, costo_envio=15.00,
                fecha_estimada_entrega=timezone.now() + timezone.timedelta(hours=2),
            ),
        )
        if creado:
            # Avanza el pedido por algunos estados para poblar el historial.
            cambiar_estado(pedido, "confirmado", usuario=admin, comentario="Confirmado automáticamente")
            cambiar_estado(pedido, "en_preparacion", usuario=repartidor)
            cambiar_estado(pedido, "en_camino", usuario=repartidor, comentario="En ruta")
            self.stdout.write(self.style.SUCCESS(f"Pedido demo creado: {pedido.codigo_seguimiento}"))

        self.stdout.write(self.style.SUCCESS("Seed de demo completado."))

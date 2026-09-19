from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PerfilRepartidor

Usuario = get_user_model()


@receiver(post_save, sender=Usuario)
def sincronizar_perfil_repartidor(sender, instance, **kwargs):
    campos = kwargs.get("update_fields")
    if campos is not None and "rol" not in campos:
        # Evita una consulta extra en cada login (update_fields=["last_login"]).
        return

    if instance.rol == Usuario.Rol.REPARTIDOR:
        PerfilRepartidor.objects.get_or_create(usuario=instance)
    else:
        # Descarta placa, licencia y calificación.
        PerfilRepartidor.objects.filter(usuario=instance).delete()

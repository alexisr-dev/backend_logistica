from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario, PerfilRepartidor, Direccion


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    ordering = ["email"]
    list_display = ["email", "nombre", "apellido", "rol", "activo", "is_staff"]
    list_filter = ["rol", "activo", "is_staff"]
    search_fields = ["email", "nombre", "apellido"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("nombre", "apellido", "telefono", "foto_url")}),
        ("Rol y estado", {"fields": ("rol", "activo", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Fechas", {"fields": ("last_login",)}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "nombre", "apellido", "rol", "password1", "password2"),
        }),
    )


admin.site.register(PerfilRepartidor)
admin.site.register(Direccion)

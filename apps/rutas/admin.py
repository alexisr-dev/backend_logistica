from django.contrib import admin

from .models import Ruta, RutaPedido


class RutaPedidoInline(admin.TabularInline):
    model = RutaPedido
    extra = 0


@admin.register(Ruta)
class RutaAdmin(admin.ModelAdmin):
    list_display = ["id", "repartidor", "fecha", "estado", "distancia_total_km"]
    list_filter = ["estado", "fecha"]
    inlines = [RutaPedidoInline]

from django.contrib import admin

from .models import EstadoPedido, Pedido, HistorialEstadoPedido, Calificacion


@admin.register(EstadoPedido)
class EstadoPedidoAdmin(admin.ModelAdmin):
    list_display = ["orden", "codigo", "nombre"]
    ordering = ["orden"]


class HistorialInline(admin.TabularInline):
    model = HistorialEstadoPedido
    extra = 0
    readonly_fields = ["estado", "usuario", "comentario", "fecha"]


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ["codigo_seguimiento", "cliente", "repartidor", "estado", "fecha_creacion"]
    list_filter = ["estado"]
    search_fields = ["codigo_seguimiento"]
    inlines = [HistorialInline]


admin.site.register(Calificacion)

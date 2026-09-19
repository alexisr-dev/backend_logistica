from rest_framework.routers import DefaultRouter

from .views import RutaViewSet, RutaPedidoViewSet

router = DefaultRouter()
# `paradas` va antes del prefijo vacío, si no lo captura la ruta con pk de RutaViewSet.
router.register("paradas", RutaPedidoViewSet, basename="ruta-parada")
router.register("", RutaViewSet, basename="ruta")

urlpatterns = router.urls

from rest_framework.routers import DefaultRouter

from .views import PedidoViewSet, EstadoPedidoViewSet

router = DefaultRouter()
router.register("estados", EstadoPedidoViewSet, basename="estado-pedido")
router.register("", PedidoViewSet, basename="pedido")

urlpatterns = router.urls

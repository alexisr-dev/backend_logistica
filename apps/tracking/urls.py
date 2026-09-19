from rest_framework.routers import DefaultRouter

from .views import UbicacionViewSet

router = DefaultRouter()
router.register("ubicaciones", UbicacionViewSet, basename="ubicacion")

urlpatterns = router.urls

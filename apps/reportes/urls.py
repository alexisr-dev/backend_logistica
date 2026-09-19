from rest_framework.routers import DefaultRouter

from .views import ReporteViewSet

router = DefaultRouter()
router.register("", ReporteViewSet, basename="reporte")

urlpatterns = router.urls

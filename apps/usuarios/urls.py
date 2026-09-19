from rest_framework.routers import DefaultRouter

from .views import RegistroView, UsuarioViewSet, DireccionViewSet

router = DefaultRouter()
router.register("registro", RegistroView, basename="registro")
router.register("direcciones", DireccionViewSet, basename="direccion")
router.register("", UsuarioViewSet, basename="usuario")

urlpatterns = router.urls

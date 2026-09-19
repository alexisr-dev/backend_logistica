from rest_framework.routers import DefaultRouter

from .views import RecuperacionPasswordViewSet

router = DefaultRouter()
router.register("password-reset", RecuperacionPasswordViewSet, basename="password-reset")

urlpatterns = router.urls

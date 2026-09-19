from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

api_v1 = [
    path("auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # Va aparte de apps.usuarios.urls porque ese router usa prefijo vacío
    # y se tragaría "password-reset" como un pk.
    path("auth/", include("apps.usuarios.urls_auth")),
    path("usuarios/", include("apps.usuarios.urls")),
    path("pedidos/", include("apps.pedidos.urls")),
    path("rutas/", include("apps.rutas.urls")),
    path("tracking/", include("apps.tracking.urls")),
    path("reportes/", include("apps.reportes.urls")),
    path("notificaciones/", include("apps.notificaciones.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1, "api"))),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

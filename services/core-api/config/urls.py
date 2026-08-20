from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/", include("apps.portal.urls")),
    path("api/v1/", include("apps.citizens.urls")),
    path("api/v1/", include("apps.access.urls")),
    path("api/v1/", include("apps.billing.urls")),
    path("api/v1/", include("apps.promotions.urls")),
    path("api/v1/", include("apps.support.urls")),
    path("api/v1/", include("apps.messaging.urls")),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/v1/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]

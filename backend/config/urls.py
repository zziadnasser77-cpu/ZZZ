from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

api_v1 = [
    path("auth/", include("apps.identity_access.urls_auth")),
    path("", include("apps.identity_access.urls")),
    path("", include("apps.audit.urls")),
    path("", include("apps.organization_settings.urls")),
    path("", include("apps.crm.urls")),
    path("", include("apps.catalog.urls")),
    path("", include("apps.pricing.urls")),
    path("", include("apps.quotations.urls")),
    path("", include("apps.sales_orders.urls")),
    path("", include("apps.procurement.urls")),
    path("", include("apps.shipments.urls")),
    path("", include("apps.inventory.urls")),
    path("accounting/", include("apps.accounting.urls")),
    path("payments/", include("apps.payments.urls")),
    path("biomedical/", include("apps.biomedical.urls")),
    path("documents/", include("apps.documents_ai.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("reporting/", include("apps.reporting.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]

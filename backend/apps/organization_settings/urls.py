from django.urls import path

from .api import OrganizationView
from .api import urlpatterns as router_urls

urlpatterns = [path("organization/", OrganizationView.as_view()), *router_urls]

from rest_framework.routers import DefaultRouter

from apps.notifications.views import NotificationTemplateViewSet, NotificationViewSet

router = DefaultRouter()
router.register(r"items", NotificationViewSet, basename="notification")
router.register(r"templates", NotificationTemplateViewSet, basename="notification-template")

urlpatterns = router.urls

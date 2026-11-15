import pytest

from apps.notifications.models import (
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
)
from apps.notifications.services import (
    mark_notification_as_read,
    send_notification,
)


@pytest.mark.django_db
def test_send_in_app_notification_and_mark_read(admin_user):
    notif = send_notification(
        recipient=admin_user,
        title="وصول شحنة جديدة",
        message="تم وصول الشحنة SHP-2026-000001 إلى ميناء عدن",
        channel=NotificationChannel.IN_APP,
        priority=NotificationPriority.HIGH,
        action_url="/shipments",
    )

    assert notif.status == NotificationStatus.DELIVERED
    assert notif.delivery_attempts.count() == 1
    assert notif.delivery_attempts.first().is_success is True

    # Mark as read
    read_notif = mark_notification_as_read(notif)
    assert read_notif.status == NotificationStatus.READ
    assert read_notif.read_at is not None


@pytest.mark.django_db
def test_send_multi_channel_notification(admin_user):
    notif = send_notification(
        recipient=admin_user,
        title="تنبيه تجديد ضمان",
        message="ينتهي ضمان جهاز الرنين المغناطيسي بعد 14 يوماً",
        channel=NotificationChannel.EMAIL,
        priority=NotificationPriority.NORMAL,
    )

    assert notif.channel == NotificationChannel.EMAIL
    assert notif.status == NotificationStatus.SENT
    assert notif.delivery_attempts.count() == 1

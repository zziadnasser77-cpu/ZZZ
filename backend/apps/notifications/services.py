from django.db import transaction
from django.utils import timezone

from apps.notifications.models import (
    DeliveryAttempt,
    Notification,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
)


@transaction.atomic
def send_notification(
    recipient,
    title: str,
    message: str,
    channel: str = NotificationChannel.IN_APP,
    priority: str = NotificationPriority.NORMAL,
    action_url: str = "",
) -> Notification:
    notification = Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        channel=channel,
        priority=priority,
        status=NotificationStatus.PENDING,
        action_url=action_url,
    )

    # Deliver attempt
    is_success = True
    response_msg = "Delivered to in-app notification center"

    DeliveryAttempt.objects.create(
        notification=notification,
        channel=channel,
        is_success=is_success,
        response_payload=response_msg,
    )

    notification.status = (
        NotificationStatus.DELIVERED if channel == NotificationChannel.IN_APP else NotificationStatus.SENT
    )
    notification.save(update_fields=["status", "updated_at"])
    return notification


@transaction.atomic
def mark_notification_as_read(notification: Notification) -> Notification:
    notification.status = NotificationStatus.READ
    notification.read_at = timezone.now()
    notification.save(update_fields=["status", "read_at", "updated_at"])
    return notification

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel


class NotificationChannel(models.TextChoices):
    IN_APP = "IN_APP", _("داخل النظام - In App")
    EMAIL = "EMAIL", _("بريد إلكتروني - Email")
    SMS = "SMS", _("رسالة نصية - SMS")
    WHATSAPP = "WHATSAPP", _("واتساب - WhatsApp")


class NotificationPriority(models.TextChoices):
    LOW = "LOW", _("منخفضة")
    NORMAL = "NORMAL", _("عادية")
    HIGH = "HIGH", _("عالية")
    URGENT = "URGENT", _("عاجلة وفورية")


class NotificationStatus(models.TextChoices):
    PENDING = "PENDING", _("قيد الانتظار")
    SENT = "SENT", _("تم الإرسال")
    DELIVERED = "DELIVERED", _("تم التسليم")
    FAILED = "FAILED", _("فشل الإرسال")
    READ = "READ", _("مقروءة")


class NotificationTemplate(BaseModel):
    code = models.CharField(max_length=60, unique=True)
    name_ar = models.CharField(max_length=150)
    name_en = models.CharField(max_length=150)
    channel = models.CharField(
        max_length=20,
        choices=NotificationChannel.choices,
        default=NotificationChannel.IN_APP,
    )
    subject_template = models.CharField(max_length=255, blank=True)
    body_template = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = _("قالب إشعار")
        verbose_name_plural = _("قوالب الإشعارات")

    def __str__(self):
        return f"{self.code} - {self.name_ar}"


class Notification(BaseModel):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    channel = models.CharField(
        max_length=20,
        choices=NotificationChannel.choices,
        default=NotificationChannel.IN_APP,
    )
    priority = models.CharField(
        max_length=20,
        choices=NotificationPriority.choices,
        default=NotificationPriority.NORMAL,
    )
    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING,
    )
    read_at = models.DateTimeField(null=True, blank=True)
    action_url = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("إشعار")
        verbose_name_plural = _("الإشعارات")

    def __str__(self):
        return f"{self.recipient.email}: {self.title} ({self.status})"


class DeliveryAttempt(BaseModel):
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name="delivery_attempts",
    )
    channel = models.CharField(max_length=20, choices=NotificationChannel.choices)
    is_success = models.BooleanField(default=False)
    response_payload = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("محاولة تسليم إشعار")
        verbose_name_plural = _("سجل محاولات التسليم")

    def __str__(self):
        return f"Attempt {self.id} for {self.notification_id}: {'Success' if self.is_success else 'Fail'}"

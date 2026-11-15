from rest_framework import serializers

from apps.notifications.models import (
    DeliveryAttempt,
    Notification,
    NotificationTemplate,
)


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = [
            "id",
            "code",
            "name_ar",
            "name_en",
            "channel",
            "subject_template",
            "body_template",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class DeliveryAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryAttempt
        fields = [
            "id",
            "notification",
            "channel",
            "is_success",
            "response_payload",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class NotificationSerializer(serializers.ModelSerializer):
    attempts = DeliveryAttemptSerializer(many=True, read_only=True, source="delivery_attempts")

    class Meta:
        model = Notification
        fields = [
            "id",
            "recipient",
            "title",
            "message",
            "channel",
            "priority",
            "status",
            "read_at",
            "action_url",
            "attempts",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "recipient",
            "status",
            "read_at",
            "created_at",
            "updated_at",
        ]

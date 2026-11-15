from rest_framework import serializers

from .models import Activity, Contact, Customer, Opportunity


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = [
            "id",
            "customer",
            "name",
            "job_title",
            "role",
            "phone",
            "mobile",
            "email",
            "is_primary",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CustomerSerializer(serializers.ModelSerializer):
    assigned_sales_rep_email = serializers.EmailField(
        source="assigned_sales_rep.email", read_only=True, default=None
    )
    primary_contact = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id",
            "customer_number",
            "customer_type",
            "legal_name_ar",
            "legal_name_en",
            "trade_name",
            "governorate",
            "district",
            "address",
            "phone",
            "email",
            "website",
            "commercial_register_no",
            "tax_no",
            "status",
            "assigned_sales_rep",
            "assigned_sales_rep_email",
            "primary_contact",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "customer_number", "created_at", "updated_at"]

    def get_primary_contact(self, obj):
        c = obj.contacts.filter(is_primary=True).first() or obj.contacts.first()
        if c:
            return {
                "id": str(c.id),
                "name": c.name,
                "phone": c.phone or c.mobile,
                "email": c.email,
                "role": c.role,
            }
        return None


class OpportunitySerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.legal_name_ar", read_only=True)
    primary_contact_name = serializers.CharField(source="primary_contact.name", read_only=True, default=None)
    assigned_to_email = serializers.EmailField(source="assigned_to.email", read_only=True, default=None)

    class Meta:
        model = Opportunity
        fields = [
            "id",
            "opportunity_number",
            "title",
            "customer",
            "customer_name",
            "primary_contact",
            "primary_contact_name",
            "stage",
            "expected_value",
            "currency",
            "probability_pct",
            "expected_close_date",
            "source",
            "close_reason",
            "assigned_to",
            "assigned_to_email",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "opportunity_number", "created_at", "updated_at"]

    def validate_probability_pct(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Probability must be between 0 and 100.")
        return value


class ActivitySerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.legal_name_ar", read_only=True, default=None)
    performed_by_email = serializers.EmailField(source="performed_by.email", read_only=True, default=None)

    class Meta:
        model = Activity
        fields = [
            "id",
            "activity_type",
            "status",
            "subject",
            "description",
            "customer",
            "customer_name",
            "contact",
            "opportunity",
            "scheduled_at",
            "completed_at",
            "location",
            "performed_by",
            "performed_by_email",
            "outcome",
            "next_action",
            "next_action_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

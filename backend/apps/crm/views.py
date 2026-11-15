from rest_framework import viewsets

from apps.audit.services import log_event
from apps.identity_access.permissions import HasPermission

from .models import Activity, Contact, Customer, Opportunity
from .serializers import (
    ActivitySerializer,
    ContactSerializer,
    CustomerSerializer,
    OpportunitySerializer,
)


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.prefetch_related("contacts").select_related("assigned_sales_rep")
    serializer_class = CustomerSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "crm.customer.view",
        "retrieve": "crm.customer.view",
        "create": "crm.customer.create",
        "update": "crm.customer.edit",
        "partial_update": "crm.customer.edit",
        "destroy": "crm.customer.manage",
    }
    search_fields = ["customer_number", "legal_name_ar", "legal_name_en", "trade_name", "phone", "email"]
    filterset_fields = ["customer_type", "status", "governorate", "assigned_sales_rep"]
    ordering_fields = ["created_at", "legal_name_ar", "customer_number"]

    def perform_create(self, serializer):
        customer = serializer.save()
        log_event(
            "crm.customer_created", entity=customer, summary=f"Customer {customer.customer_number} created"
        )

    def perform_update(self, serializer):
        before_status = serializer.instance.status
        customer = serializer.save()
        changes = None
        if before_status != customer.status:
            changes = {"status_before": before_status, "status_after": customer.status}
        log_event(
            "crm.customer_updated",
            entity=customer,
            summary=f"Customer {customer.customer_number} updated",
            changes=changes,
        )


class ContactViewSet(viewsets.ModelViewSet):
    queryset = Contact.objects.select_related("customer")
    serializer_class = ContactSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "crm.contact.view",
        "retrieve": "crm.contact.view",
        "create": "crm.contact.create",
        "update": "crm.contact.edit",
        "partial_update": "crm.contact.edit",
        "destroy": "crm.contact.manage",
    }
    search_fields = ["name", "phone", "mobile", "email", "job_title"]
    filterset_fields = ["customer", "role", "is_primary"]

    def perform_create(self, serializer):
        contact = serializer.save()
        log_event(
            "crm.contact_created",
            entity=contact,
            summary=f"Contact {contact.name} for {contact.customer.legal_name_ar}",
        )

    def perform_update(self, serializer):
        contact = serializer.save()
        log_event("crm.contact_updated", entity=contact, summary=f"Contact {contact.name} updated")


class OpportunityViewSet(viewsets.ModelViewSet):
    queryset = Opportunity.objects.select_related("customer", "primary_contact", "assigned_to")
    serializer_class = OpportunitySerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "crm.opportunity.view",
        "retrieve": "crm.opportunity.view",
        "create": "crm.opportunity.create",
        "update": "crm.opportunity.edit",
        "partial_update": "crm.opportunity.edit",
        "destroy": "crm.opportunity.manage",
    }
    search_fields = ["opportunity_number", "title", "customer__legal_name_ar"]
    filterset_fields = ["stage", "source", "customer", "assigned_to", "currency"]
    ordering_fields = ["created_at", "expected_value", "expected_close_date"]

    def perform_create(self, serializer):
        opp = serializer.save()
        log_event(
            "crm.opportunity_created",
            entity=opp,
            summary=f"Opportunity {opp.opportunity_number}: {opp.title}",
        )

    def perform_update(self, serializer):
        before_stage = serializer.instance.stage
        before_value = serializer.instance.expected_value
        opp = serializer.save()
        changes = {}
        if before_stage != opp.stage:
            changes["stage"] = {"before": before_stage, "after": opp.stage}
        if before_value != opp.expected_value:
            changes["expected_value"] = {"before": str(before_value), "after": str(opp.expected_value)}
        sensitive = opp.stage in ("WON", "LOST") or bool(changes)
        log_event(
            "crm.opportunity_updated",
            entity=opp,
            summary=f"Opportunity {opp.opportunity_number} updated",
            changes=changes or None,
            sensitive=sensitive,
        )


class ActivityViewSet(viewsets.ModelViewSet):
    queryset = Activity.objects.select_related("customer", "contact", "opportunity", "performed_by")
    serializer_class = ActivitySerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "crm.activity.view",
        "retrieve": "crm.activity.view",
        "create": "crm.activity.create",
        "update": "crm.activity.edit",
        "partial_update": "crm.activity.edit",
        "destroy": "crm.activity.manage",
    }
    search_fields = ["subject", "description", "customer__legal_name_ar"]
    filterset_fields = ["activity_type", "status", "customer", "opportunity", "performed_by"]
    ordering_fields = ["scheduled_at", "created_at"]

    def perform_create(self, serializer):
        act = serializer.save(performed_by=serializer.validated_data.get("performed_by") or self.request.user)
        log_event("crm.activity_created", entity=act, summary=f"Activity {act.activity_type}: {act.subject}")

    def perform_update(self, serializer):
        act = serializer.save()
        log_event("crm.activity_updated", entity=act, summary=f"Activity {act.activity_type} updated")

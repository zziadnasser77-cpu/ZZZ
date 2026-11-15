from django.db import transaction

from apps.audit.services import log_event
from apps.common.exceptions import BusinessRuleViolation
from apps.quotations.models import Quotation, QuotationVersion

from .models import Deal, SalesOrder, SalesOrderLine


@transaction.atomic
def convert_quotation_to_deal_and_order(quotation: Quotation, user) -> tuple[Deal, SalesOrder]:
    """Convert an accepted/approved Quotation into a Deal and Sales Order without re-entering data. Spec §5.4, §6.1."""
    latest_version = quotation.versions.order_by("-version_number").first()
    if not latest_version:
        raise BusinessRuleViolation("Quotation has no versions.")
    if latest_version.status not in (
        QuotationVersion.Status.ACCEPTED,
        QuotationVersion.Status.APPROVED,
        QuotationVersion.Status.SENT,
    ):
        raise BusinessRuleViolation("Only approved, sent or accepted quotations can be converted to deals.")

    # 1. Create Deal
    deal = Deal.objects.create(
        title=quotation.title,
        customer=quotation.customer,
        quotation=quotation,
        commercial_model=quotation.commercial_model,
        currency=quotation.currency,
        total_value=latest_version.total_amount,
        status=Deal.Status.CONFIRMED,
        notes=f"Converted from quotation {quotation.quotation_number} (v{latest_version.version_number})",
    )

    # 2. Create Sales Order
    so = SalesOrder.objects.create(
        deal=deal,
        customer=quotation.customer,
        status=SalesOrder.Status.CONFIRMED,
        currency=quotation.currency,
        total_amount=latest_version.total_amount,
        delivery_terms=latest_version.delivery_terms,
        payment_terms=latest_version.payment_terms,
        notes=latest_version.notes,
    )

    # 3. Copy lines
    for qline in latest_version.lines.all():
        SalesOrderLine.objects.create(
            order=so,
            model=qline.model,
            description=qline.description,
            quantity=qline.quantity,
            unit_price=qline.unit_price,
            total_price=qline.total_price,
        )

    # 4. Update quotation status
    quotation.status = Quotation.Status.ACCEPTED
    quotation.save(update_fields=["status", "updated_at"])

    log_event(
        "sales_orders.deal_converted",
        entity=deal,
        summary=f"Deal {deal.deal_number} & Order {so.order_number} created from Quotation {quotation.quotation_number}",
        sensitive=True,
    )
    return deal, so

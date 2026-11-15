from decimal import Decimal

from django.utils import timezone

from apps.audit.services import log_event
from apps.common.exceptions import BusinessRuleViolation
from apps.organization_settings.models import OrganizationProfile

from .models import Quotation, QuotationVersion


def recalculate_version_totals(version: QuotationVersion):
    """Calculate subtotal, discounts, and total amount for a quotation version."""
    lines = list(version.lines.all())
    subtotal = sum((line.total_price for line in lines), Decimal("0.00"))
    version.subtotal = subtotal

    discount_amt = Decimal("0.00")
    if version.discount_pct and version.discount_pct > Decimal("0.00"):
        discount_amt = (subtotal * version.discount_pct) / Decimal("100.00")
    version.discount_amount = round(discount_amt, 2)
    tax_amt = Decimal(str(version.tax_amount or "0.00"))
    version.total_amount = round(subtotal - version.discount_amount + tax_amt, 2)
    version.save(update_fields=["subtotal", "discount_amount", "total_amount", "updated_at"])
    return version


def evaluate_version_approval(version: QuotationVersion, user) -> bool:
    """Check if the quotation version exceeds the user's discount or amount limits. Spec §9, ADR-032."""
    reasons = []
    user_discount_limit = user.discount_limit_pct or Decimal("0.00")
    if version.discount_pct > user_discount_limit:
        reasons.append(f"Discount {version.discount_pct}% exceeds user limit of {user_discount_limit}%.")

    if user.approval_limit_amount is not None and version.total_amount > user.approval_limit_amount:
        reasons.append(
            f"Total value {version.total_amount} exceeds user approval limit of {user.approval_limit_amount}."
        )

    if reasons:
        version.requires_approval = True
        version.approval_reason = " | ".join(reasons)
        version.status = QuotationVersion.Status.PENDING_APPROVAL
        version.quotation.status = Quotation.Status.PENDING_APPROVAL
        version.quotation.save(update_fields=["status", "updated_at"])
        version.save(update_fields=["requires_approval", "approval_reason", "status", "updated_at"])
        return True
    else:
        version.requires_approval = False
        version.approval_reason = ""
        version.save(update_fields=["requires_approval", "approval_reason", "updated_at"])
        return False


def build_version_snapshot(version: QuotationVersion) -> dict:
    """Create an immutable full frozen JSON representation of the quotation. Spec §5.4, ADR-021."""
    cust = version.quotation.customer
    org = OrganizationProfile.load()
    lines_data = []
    for line in version.lines.select_related("model__product"):
        lines_data.append(
            {
                "model_id": str(line.model.id),
                "model_code": line.model.model_code,
                "model_name": line.model.model_name,
                "sku": line.model.sku,
                "product_name_ar": line.model.product.name_ar,
                "description": line.description,
                "specifications": line.model.specifications,
                "quantity": line.quantity,
                "unit_price": str(line.unit_price),
                "discount_pct": str(line.discount_pct),
                "total_price": str(line.total_price),
                "warranty_months": line.warranty_months,
            }
        )

    snapshot = {
        "snapshot_created_at": timezone.now().isoformat(),
        "quotation_number": version.quotation.quotation_number,
        "version_number": version.version_number,
        "commercial_model": version.quotation.commercial_model,
        "currency": version.quotation.currency,
        "organization": {
            "legal_name_ar": org.legal_name_ar,
            "trade_name": org.trade_name,
            "tax_no": org.tax_no,
            "commercial_register_no": org.commercial_register_no,
            "address": org.address,
            "phone": org.phone,
        },
        "customer": {
            "customer_id": str(cust.id),
            "customer_number": cust.customer_number,
            "legal_name_ar": cust.legal_name_ar,
            "trade_name": cust.trade_name,
            "governorate": cust.governorate,
            "address": cust.address,
            "tax_no": cust.tax_no,
            "phone": cust.phone,
        },
        "financials": {
            "subtotal": str(version.subtotal),
            "discount_pct": str(version.discount_pct),
            "discount_amount": str(version.discount_amount),
            "tax_amount": str(version.tax_amount),
            "total_amount": str(version.total_amount),
        },
        "terms": {
            "valid_until": str(version.valid_until) if version.valid_until else None,
            "payment_terms": version.payment_terms,
            "delivery_terms": version.delivery_terms,
            "notes": version.notes,
        },
        "lines": lines_data,
    }
    return snapshot


def approve_quotation_version(version: QuotationVersion, approver):
    """Approve a quotation version and lock in the frozen snapshot. Spec §5.4, §9."""
    if version.created_by_id == approver.pk and version.requires_approval:
        raise BusinessRuleViolation(
            "Creator cannot self-approve a quotation that exceeds their personal authority."
        )

    approver_discount_limit = approver.discount_limit_pct
    if approver_discount_limit is not None and version.discount_pct > approver_discount_limit:
        raise BusinessRuleViolation(
            f"Approver limit of {approver_discount_limit}% is insufficient for {version.discount_pct}%."
        )

    if approver.approval_limit_amount is not None and version.total_amount > approver.approval_limit_amount:
        raise BusinessRuleViolation(
            f"Approver financial limit of {approver.approval_limit_amount} is insufficient for total amount {version.total_amount}."
        )

    version.status = QuotationVersion.Status.APPROVED
    version.approved_by = approver
    version.approved_at = timezone.now()
    version.snapshot = build_version_snapshot(version)
    version.save(update_fields=["status", "approved_by", "approved_at", "snapshot", "updated_at"])

    version.quotation.status = Quotation.Status.APPROVED
    version.quotation.save(update_fields=["status", "updated_at"])

    log_event(
        "quotations.version_approved",
        entity=version.quotation,
        summary=f"Quotation {version.quotation.quotation_number} v{version.version_number} approved",
        sensitive=True,
    )
    return version

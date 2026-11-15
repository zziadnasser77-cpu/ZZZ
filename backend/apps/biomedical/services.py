from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.audit.services import log_event
from apps.biomedical.models import (
    InstallationProtocol,
    ServiceTicket,
    ServiceVisit,
    SparePartRequest,
    WarrantyContract,
)
from apps.common.exceptions import BusinessRuleViolation
from apps.inventory.models import SerialAsset


@transaction.atomic
def sign_installation_protocol(
    protocol: InstallationProtocol,
    representative_name: str,
    representative_title: str,
    user=None,
) -> InstallationProtocol:
    """Signs and accepts an installation protocol once safety and training checklists pass."""
    if protocol.status == InstallationProtocol.Status.ACCEPTED:
        raise BusinessRuleViolation(_("محضر التركيب معتمد بالفعل."))

    if not protocol.electrical_safety_passed:
        raise BusinessRuleViolation(_("لا يمكن اعتماد المحضر قبل اجتياز فحص السلامة الكهربائية."))

    if not protocol.performance_verification_passed:
        raise BusinessRuleViolation(_("لا يمكن اعتماد المحضر قبل اجتياز فحص الأداء والمعايرة التشغيلية."))

    if not protocol.user_training_completed:
        raise BusinessRuleViolation(_("لا يمكن اعتماد المحضر قبل إتمام تدريب الكادر الطبي على الجهاز."))

    protocol.status = InstallationProtocol.Status.ACCEPTED
    protocol.customer_representative_name = representative_name
    protocol.customer_representative_title = representative_title
    protocol.customer_signed_at = timezone.now()
    protocol.save(
        update_fields=[
            "status",
            "customer_representative_name",
            "customer_representative_title",
            "customer_signed_at",
            "updated_at",
        ]
    )

    # Update asset operational status
    asset = protocol.asset
    asset.status = SerialAsset.Status.DELIVERED_TO_CUSTOMER
    asset.save(update_fields=["status", "updated_at"])

    # Create customer warranty contract if not already exists
    if not protocol.asset.warranty_contracts.filter(
        warranty_type=WarrantyContract.WarrantyType.CUSTOMER_WARRANTY
    ).exists():
        warranty_months = asset.model.standard_warranty_months or 12
        end_date = protocol.installed_at + timedelta(days=warranty_months * 30)
        WarrantyContract.objects.create(
            asset=asset,
            customer=protocol.customer,
            warranty_type=WarrantyContract.WarrantyType.CUSTOMER_WARRANTY,
            start_date=protocol.installed_at,
            end_date=end_date,
            sla_response_hours=24,
            coverage_details=f"ضمان شامل لمدة {warranty_months} شهراً يبدأ من تاريخ محضر التركيب {protocol.protocol_number}",
        )

    log_event(
        "biomedical.installation_protocol_signed",
        actor=user,
        entity=protocol,
        summary=f"اعتماد محضر التركيب {protocol.protocol_number} للجهاز {asset.serial_number}",
        changes={
            "representative_name": representative_name,
            "representative_title": representative_title,
        },
    )
    return protocol


@transaction.atomic
def assign_service_ticket(ticket: ServiceTicket, engineer, user=None) -> ServiceTicket:
    if ticket.status == ServiceTicket.Status.CLOSED:
        raise BusinessRuleViolation(_("لا يمكن إعادة تعيين تذكرة صيانة مغلقة."))

    ticket.assigned_engineer = engineer
    ticket.status = ServiceTicket.Status.ASSIGNED
    ticket.save(update_fields=["assigned_engineer", "status", "updated_at"])

    log_event(
        "biomedical.service_ticket_assigned",
        actor=user,
        entity=ticket,
        summary=f"تعيين المهندس {engineer.full_name or engineer.email} للتذكرة {ticket.ticket_number}",
        changes={"assigned_engineer_id": str(engineer.id)},
    )
    return ticket


@transaction.atomic
def record_service_visit(
    ticket: ServiceTicket,
    engineer,
    actions_taken: str,
    diagnostic_details: str = "",
    is_resolved: bool = False,
    customer_sign_off_name: str = "",
    user=None,
) -> ServiceVisit:
    visit = ServiceVisit.objects.create(
        ticket=ticket,
        engineer=engineer,
        actions_taken=actions_taken,
        diagnostic_details=diagnostic_details,
        is_resolved=is_resolved,
        customer_sign_off_name=customer_sign_off_name,
        customer_signed_at=timezone.now() if customer_sign_off_name else None,
    )

    if is_resolved:
        ticket.status = ServiceTicket.Status.RESOLVED
        ticket.resolution_summary = actions_taken
        ticket.save(update_fields=["status", "resolution_summary", "updated_at"])
    elif ticket.status == ServiceTicket.Status.ASSIGNED:
        ticket.status = ServiceTicket.Status.IN_PROGRESS
        ticket.save(update_fields=["status", "updated_at"])

    log_event(
        "biomedical.service_visit_recorded",
        actor=user or engineer,
        entity=visit,
        summary=f"تسجيل زيارة صيانة للتذكرة {ticket.ticket_number}",
        changes={"is_resolved": is_resolved},
    )
    return visit


@transaction.atomic
def close_service_ticket(
    ticket: ServiceTicket,
    labor_hours: Decimal = Decimal("0.00"),
    labor_cost: Decimal = Decimal("0.00"),
    resolution: str = "",
    user=None,
) -> ServiceTicket:
    if ticket.status == ServiceTicket.Status.CLOSED:
        raise BusinessRuleViolation(_("التذكرة مغلقة بالفعل."))

    ticket.labor_hours = labor_hours
    ticket.labor_cost = labor_cost
    if resolution:
        ticket.resolution_summary = resolution
    ticket.status = ServiceTicket.Status.CLOSED
    ticket.closed_at = timezone.now()
    ticket.save(
        update_fields=[
            "labor_hours",
            "labor_cost",
            "total_cost",
            "resolution_summary",
            "status",
            "closed_at",
            "updated_at",
        ]
    )

    log_event(
        "biomedical.service_ticket_closed",
        actor=user,
        entity=ticket,
        summary=f"إغلاق واعتماد تذكرة الصيانة {ticket.ticket_number}",
        changes={"total_cost": str(ticket.total_cost)},
    )
    return ticket


@transaction.atomic
def request_spare_part(
    ticket: ServiceTicket,
    part_name: str,
    part_sku: str,
    quantity: int = 1,
    coverage: str = SparePartRequest.Coverage.WARRANTY_FREE,
    user=None,
) -> SparePartRequest:
    req = SparePartRequest.objects.create(
        ticket=ticket,
        part_name=part_name,
        part_sku=part_sku,
        quantity=quantity,
        coverage=coverage,
        status=SparePartRequest.Status.REQUESTED,
    )

    if ticket.status in (ServiceTicket.Status.ASSIGNED, ServiceTicket.Status.IN_PROGRESS):
        ticket.status = ServiceTicket.Status.WAITING_PARTS
        ticket.save(update_fields=["status", "updated_at"])

    log_event(
        "biomedical.spare_part_requested",
        actor=user,
        entity=req,
        summary=f"طلب قطعة غيار {part_name} للتذكرة {ticket.ticket_number}",
        changes={"part_name": part_name, "quantity": quantity, "coverage": coverage},
    )
    return req


@transaction.atomic
def approve_spare_part(
    part_req: SparePartRequest,
    cost_price: Decimal = Decimal("0.00"),
    customer_price: Decimal = Decimal("0.00"),
    user=None,
) -> SparePartRequest:
    part_req.status = SparePartRequest.Status.APPROVED_BY_PARTNER
    part_req.approved_by = user
    if cost_price > Decimal("0.00"):
        part_req.cost_price = cost_price
    if customer_price > Decimal("0.00"):
        part_req.customer_price = customer_price
    part_req.save(update_fields=["status", "approved_by", "cost_price", "customer_price", "updated_at"])

    # Update ticket parts cost
    ticket = part_req.ticket
    ticket.parts_cost += part_req.customer_price * part_req.quantity
    ticket.save(update_fields=["parts_cost", "total_cost", "updated_at"])

    log_event(
        "biomedical.spare_part_approved",
        actor=user,
        entity=part_req,
        summary=f"اعتماد قطعة الغيار {part_req.part_name}",
        changes={"cost_price": str(cost_price), "customer_price": str(customer_price)},
    )
    return part_req

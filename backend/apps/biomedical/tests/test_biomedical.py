from decimal import Decimal

import pytest

from apps.biomedical.models import (
    InstallationProtocol,
    ServiceTicket,
    SparePartRequest,
    WarrantyContract,
)
from apps.biomedical.services import (
    approve_spare_part,
    assign_service_ticket,
    close_service_ticket,
    record_service_visit,
    request_spare_part,
    sign_installation_protocol,
)
from apps.catalog.models import Category, Manufacturer, Product, ProductModel
from apps.common.exceptions import BusinessRuleViolation
from apps.crm.models import Customer
from apps.inventory.models import Location, SerialAsset


@pytest.fixture
def biomed_setup(db, admin_user):
    cat = Category.objects.create(name_ar="أجهزة تصوير", name_en="Imaging", code="IMG")
    mfr = Manufacturer.objects.create(name_ar="الشركة المصنعة", name_en="MedTech Co", country="CN")
    prod = Product.objects.create(
        category=cat,
        manufacturer=mfr,
        name_ar="جهاز رنين",
        name_en="MRI",
        device_class=Product.DeviceClass.CLASS_III,
    )
    model = ProductModel.objects.create(
        product=prod,
        model_code="MRI-3000",
        model_name="MRI-3000",
        sku="SKU-MRI-3000",
        standard_warranty_months=24,
        approval_status=ProductModel.ApprovalStatus.APPROVED,
    )
    loc = Location.objects.create(
        code="LOC-CUST-01", name_ar="مستشفى الثورة - صنعاء", location_type=Location.LocationType.CUSTOMER_SITE
    )
    asset = SerialAsset.objects.create(
        model=model,
        serial_number="SN-MRI-998877",
        current_location=loc,
        status=SerialAsset.Status.IN_STOCK,
    )
    customer = Customer.objects.create(
        legal_name_ar="مستشفى الثورة التعليمي",
        trade_name="الثورة",
        customer_type=Customer.CustomerType.HOSPITAL,
    )

    return {
        "model": model,
        "loc": loc,
        "asset": asset,
        "customer": customer,
    }


@pytest.mark.django_db
def test_installation_protocol_workflow_and_auto_warranty(biomed_setup, admin_user):
    s = biomed_setup
    proto = InstallationProtocol.objects.create(
        asset=s["asset"],
        customer=s["customer"],
        location=s["loc"],
        lead_engineer=admin_user,
    )

    # Attempting to sign without completing checklist should fail
    with pytest.raises(BusinessRuleViolation, match="السلامة الكهربائية"):
        sign_installation_protocol(
            proto, representative_name="د. محمد عبد الله", representative_title="رئيس القسم", user=admin_user
        )

    proto.electrical_safety_passed = True
    proto.performance_verification_passed = True
    proto.user_training_completed = True
    proto.trainees_list = "د. أحمد (رئيس الأطباء)، م. سامي (فني أشعة)"
    proto.save()

    signed_proto = sign_installation_protocol(
        proto,
        representative_name="د. محمد عبد الله",
        representative_title="رئيس القسم",
        user=admin_user,
    )

    assert signed_proto.status == InstallationProtocol.Status.ACCEPTED
    assert signed_proto.customer_representative_name == "د. محمد عبد الله"
    assert signed_proto.customer_signed_at is not None

    # Asset status updated to DELIVERED_TO_CUSTOMER
    s["asset"].refresh_from_db()
    assert s["asset"].status == SerialAsset.Status.DELIVERED_TO_CUSTOMER

    # Customer warranty auto-created for 24 months
    warranties = WarrantyContract.objects.filter(asset=s["asset"], customer=s["customer"])
    assert warranties.exists()
    war = warranties.first()
    assert war.warranty_type == WarrantyContract.WarrantyType.CUSTOMER_WARRANTY
    assert (war.end_date - war.start_date).days >= 700  # 24 months approx 720 days


@pytest.mark.django_db
def test_service_ticket_lifecycle(biomed_setup, admin_user):
    s = biomed_setup
    ticket = ServiceTicket.objects.create(
        ticket_type=ServiceTicket.TicketType.CORRECTIVE,
        priority=ServiceTicket.Priority.HIGH,
        asset=s["asset"],
        customer=s["customer"],
        title="انخفاض كفاءة التبريد",
        reported_issue="الحساس يعطي قراءة حرارة مرتفعة",
        created_by=admin_user,
    )

    assert ticket.ticket_number.startswith("SRV-")
    assert ticket.status == ServiceTicket.Status.OPEN

    # Assign engineer
    assign_service_ticket(ticket, engineer=admin_user, user=admin_user)
    ticket.refresh_from_db()
    assert ticket.status == ServiceTicket.Status.ASSIGNED
    assert ticket.assigned_engineer == admin_user

    # Engineer logs visit
    visit = record_service_visit(
        ticket=ticket,
        engineer=admin_user,
        actions_taken="تم فحص دارة التبريد واستبدال الفلتر وإعادة المعايرة",
        diagnostic_details="انسداد جزئي في الفلتر",
        is_resolved=True,
        customer_sign_off_name="م. علي الشامي",
        user=admin_user,
    )
    assert visit.is_resolved is True
    ticket.refresh_from_db()
    assert ticket.status == ServiceTicket.Status.RESOLVED

    # Close ticket
    close_service_ticket(
        ticket=ticket,
        labor_hours=Decimal("3.5"),
        labor_cost=Decimal("15000.00"),
        resolution="تم تشغيل الجهاز والتحقق من استقرار الحرارة",
        user=admin_user,
    )
    ticket.refresh_from_db()
    assert ticket.status == ServiceTicket.Status.CLOSED
    assert ticket.labor_hours == Decimal("3.5")
    assert ticket.labor_cost == Decimal("15000.00")
    assert ticket.total_cost >= Decimal("15000.00")
    assert ticket.closed_at is not None


@pytest.mark.django_db
def test_spare_part_request_and_approval(biomed_setup, admin_user):
    s = biomed_setup
    ticket = ServiceTicket.objects.create(
        ticket_type=ServiceTicket.TicketType.EMERGENCY,
        priority=ServiceTicket.Priority.CRITICAL,
        asset=s["asset"],
        customer=s["customer"],
        title="عطل في مزود الطاقة",
        reported_issue="الجهاز لا يقلع",
        created_by=admin_user,
    )
    assign_service_ticket(ticket, engineer=admin_user, user=admin_user)

    # Request spare part
    part_req = request_spare_part(
        ticket=ticket,
        part_name="لوحة التغذية الكهربائية PSU-450",
        part_sku="CN-PSU-450",
        quantity=1,
        coverage=SparePartRequest.Coverage.BILLABLE_CUSTOMER,
        user=admin_user,
    )

    ticket.refresh_from_db()
    assert ticket.status == ServiceTicket.Status.WAITING_PARTS

    # Approve spare part
    approved = approve_spare_part(
        part_req,
        cost_price=Decimal("18000.00"),
        customer_price=Decimal("25000.00"),
        user=admin_user,
    )
    assert approved.status == SparePartRequest.Status.APPROVED_BY_PARTNER
    assert approved.customer_price == Decimal("25000.00")

    ticket.refresh_from_db()
    assert ticket.parts_cost == Decimal("25000.00")
    assert ticket.total_cost == Decimal("25000.00")

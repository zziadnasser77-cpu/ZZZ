import csv
import io
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.accounting.models import Account, JournalLine
from apps.audit.models import AuditEvent
from apps.biomedical.models import ServiceTicket, WarrantyContract
from apps.crm.models import Opportunity
from apps.inventory.models import SerialAsset
from apps.payments.models import CustomerInvoice, InvoiceStatus
from apps.procurement.models import SupplierOrder
from apps.sales_orders.models import Deal, SalesOrder, SalesOrderLine
from apps.shipments.models import Shipment


def get_dashboard_summary(user) -> dict[str, Any]:
    """Aggregate high-level KPIs across domains respecting user permissions (Spec §5.1)."""
    today = timezone.now().date()
    can_view_cost = user.has_perm_code("pricing.cost.view") or user.has_perm_code("reporting.financial.view")

    # Commercial stats
    open_opps_qs = Opportunity.objects.exclude(
        stage__in=[Opportunity.Stage.WON, Opportunity.Stage.LOST, Opportunity.Stage.CANCELLED]
    )
    open_opps_count = open_opps_qs.count()
    open_opps_val = open_opps_qs.aggregate(total=Sum("expected_value"))["total"] or Decimal("0.00")

    active_deals_count = Deal.objects.exclude(
        status__in=[Deal.Status.CLOSED, Deal.Status.CANCELLED]
    ).count()

    sales_orders_qs = SalesOrder.objects.exclude(status=SalesOrder.Status.CANCELLED)
    sales_orders_count = sales_orders_qs.count()
    sales_by_currency = list(
        sales_orders_qs.values("currency").annotate(
            total_amount=Sum("total_amount"),
            order_count=Count("id"),
        ).order_by("-total_amount")
    )

    # Receivables & Aging
    unpaid_invoices_qs = CustomerInvoice.objects.filter(
        status__in=[InvoiceStatus.POSTED, InvoiceStatus.PARTIALLY_PAID]
    )
    unpaid_invoices_count = unpaid_invoices_qs.count()
    unpaid_total = Decimal("0.00")
    aging_buckets = {
        "current": Decimal("0.00"),
        "days_1_30": Decimal("0.00"),
        "days_31_60": Decimal("0.00"),
        "days_61_90": Decimal("0.00"),
        "days_90_plus": Decimal("0.00"),
    }

    for inv in unpaid_invoices_qs.iterator():
        remaining = inv.remaining_amount
        unpaid_total += remaining
        ref_date = inv.due_date or inv.invoice_date
        overdue_days = (today - ref_date).days if ref_date else 0
        if overdue_days <= 0:
            aging_buckets["current"] += remaining
        elif overdue_days <= 30:
            aging_buckets["days_1_30"] += remaining
        elif overdue_days <= 60:
            aging_buckets["days_31_60"] += remaining
        elif overdue_days <= 90:
            aging_buckets["days_61_90"] += remaining
        else:
            aging_buckets["days_90_plus"] += remaining

    # Logistics & Inventory
    active_shipments_count = Shipment.objects.filter(
        status__in=["DISPATCHED", "IN_TRANSIT", "CUSTOMS", "ARRIVED"]
    ).count()

    assets_qs = SerialAsset.objects.all()
    assets_total_count = assets_qs.count()
    assets_in_stock = assets_qs.filter(status=SerialAsset.Status.IN_STOCK).count()
    assets_delivered = assets_qs.filter(status=SerialAsset.Status.DELIVERED_TO_CUSTOMER).count()
    assets_in_maintenance = assets_qs.filter(status=SerialAsset.Status.IN_MAINTENANCE).count()

    # Biomedical Engineering
    open_tickets_qs = ServiceTicket.objects.exclude(
        status__in=[ServiceTicket.Status.RESOLVED, ServiceTicket.Status.CLOSED, ServiceTicket.Status.CANCELLED]
    )
    open_tickets_count = open_tickets_qs.count()
    critical_tickets_count = open_tickets_qs.filter(priority=ServiceTicket.Priority.CRITICAL).count()

    warranties_expiring_30d = WarrantyContract.objects.filter(
        is_active=True,
        end_date__gte=today,
        end_date__lte=today + timedelta(days=30),
    ).count()

    # Chinese Supplier Purchase Orders
    active_pos_count = SupplierOrder.objects.exclude(
        status__in=["RECEIVED", "CANCELLED"]
    ).count()

    result = {
        "as_of_date": today.isoformat(),
        "commercial": {
            "open_opportunities_count": open_opps_count,
            "open_opportunities_value": str(open_opps_val),
            "active_deals_count": active_deals_count,
            "sales_orders_count": sales_orders_count,
            "sales_by_currency": [
                {
                    "currency": item["currency"],
                    "total_amount": str(item["total_amount"]),
                    "order_count": item["order_count"],
                }
                for item in sales_by_currency
            ],
        },
        "receivables": {
            "unpaid_invoices_count": unpaid_invoices_count,
            "unpaid_total": str(unpaid_total),
            "aging_buckets": {k: str(v) for k, v in aging_buckets.items()},
        },
        "inventory": {
            "total_assets": assets_total_count,
            "in_stock": assets_in_stock,
            "delivered_to_customer": assets_delivered,
            "in_maintenance": assets_in_maintenance,
        },
        "logistics": {
            "active_shipments_count": active_shipments_count,
            "active_purchase_orders_count": active_pos_count,
        },
        "biomedical": {
            "open_tickets_count": open_tickets_count,
            "critical_tickets_count": critical_tickets_count,
            "warranties_expiring_30d_count": warranties_expiring_30d,
        },
    }

    # Hide cost & profit strictly if user lacks permission (§5.1)
    if can_view_cost:
        result["financial_access"] = True
    else:
        result["financial_access"] = False

    return result


def get_commercial_pipeline_report(date_from=None, date_to=None) -> dict[str, Any]:
    """Commercial pipeline analysis: opportunities, win rate, sales orders, models breakdown."""
    opps_qs = Opportunity.objects.all()
    if date_from:
        opps_qs = opps_qs.filter(created_at__date__gte=date_from)
    if date_to:
        opps_qs = opps_qs.filter(created_at__date__lte=date_to)

    stage_counts = list(opps_qs.values("stage").annotate(
        count=Count("id"),
        total_expected_value=Sum("expected_value"),
    ).order_by("stage"))

    won_count = opps_qs.filter(stage=Opportunity.Stage.WON).count()
    lost_count = opps_qs.filter(stage=Opportunity.Stage.LOST).count()
    completed_opps = won_count + lost_count
    win_rate = round((won_count / completed_opps * 100), 2) if completed_opps > 0 else 0.0

    deals_by_model = list(
        Deal.objects.values("commercial_model").annotate(
            count=Count("id"),
            total_value=Sum("total_value"),
        ).order_by("commercial_model")
    )

    deals_by_status = list(
        Deal.objects.values("status").annotate(
            count=Count("id"),
            total_value=Sum("total_value"),
        ).order_by("status")
    )

    top_customers = list(
        SalesOrder.objects.exclude(status=SalesOrder.Status.CANCELLED)
        .values("customer__customer_number", "customer__legal_name_ar", "currency")
        .annotate(
            orders_count=Count("id"),
            total_revenue=Sum("total_amount"),
        )
        .order_by("-total_revenue")[:10]
    )

    top_models = list(
        SalesOrderLine.objects.values("model__model_code", "model__model_name")
        .annotate(
            units_sold=Sum("quantity"),
            revenue=Sum("total_price"),
        )
        .order_by("-units_sold")[:10]
    )

    return {
        "opportunities_by_stage": [
            {
                "stage": s["stage"],
                "count": s["count"],
                "total_expected_value": str(s["total_expected_value"] or Decimal("0.00")),
            }
            for s in stage_counts
        ],
        "win_rate_percentage": win_rate,
        "deals_by_commercial_model": [
            {
                "commercial_model": d["commercial_model"],
                "count": d["count"],
                "total_value": str(d["total_value"] or Decimal("0.00")),
            }
            for d in deals_by_model
        ],
        "deals_by_status": [
            {
                "status": d["status"],
                "count": d["count"],
                "total_value": str(d["total_value"] or Decimal("0.00")),
            }
            for d in deals_by_status
        ],
        "top_customers": [
            {
                "customer_number": c["customer__customer_number"],
                "customer_name": c["customer__legal_name_ar"],
                "currency": c["currency"],
                "orders_count": c["orders_count"],
                "total_revenue": str(c["total_revenue"] or Decimal("0.00")),
            }
            for c in top_customers
        ],
        "top_models": [
            {
                "model_code": m["model__model_code"],
                "model_name": m["model__model_name"],
                "units_sold": m["units_sold"],
                "revenue": str(m["revenue"] or Decimal("0.00")),
            }
            for m in top_models
        ],
    }


def get_receivables_aging_report(as_of_date=None) -> dict[str, Any]:
    """Customer-by-customer receivables aging breakdown."""
    as_of = as_of_date or timezone.now().date()
    unpaid_invoices = CustomerInvoice.objects.filter(
        status__in=[InvoiceStatus.POSTED, InvoiceStatus.PARTIALLY_PAID]
    ).select_related("customer", "currency").order_by("customer__legal_name_ar")

    customers_map: dict[str, dict] = {}
    total_summary = {
        "current": Decimal("0.00"),
        "days_1_30": Decimal("0.00"),
        "days_31_60": Decimal("0.00"),
        "days_61_90": Decimal("0.00"),
        "days_90_plus": Decimal("0.00"),
        "total_outstanding": Decimal("0.00"),
    }

    for inv in unpaid_invoices:
        cid = str(inv.customer.id)
        if cid not in customers_map:
            customers_map[cid] = {
                "customer_id": cid,
                "customer_number": inv.customer.customer_number,
                "customer_name_ar": inv.customer.legal_name_ar,
                "customer_name_en": inv.customer.legal_name_en or inv.customer.legal_name_ar,
                "currency": inv.currency.code,
                "current": Decimal("0.00"),
                "days_1_30": Decimal("0.00"),
                "days_31_60": Decimal("0.00"),
                "days_61_90": Decimal("0.00"),
                "days_90_plus": Decimal("0.00"),
                "total_outstanding": Decimal("0.00"),
                "invoices_count": 0,
            }

        rem = inv.remaining_amount
        customers_map[cid]["total_outstanding"] += rem
        customers_map[cid]["invoices_count"] += 1
        total_summary["total_outstanding"] += rem

        ref_date = inv.due_date or inv.invoice_date
        overdue_days = (as_of - ref_date).days if ref_date else 0

        if overdue_days <= 0:
            customers_map[cid]["current"] += rem
            total_summary["current"] += rem
        elif overdue_days <= 30:
            customers_map[cid]["days_1_30"] += rem
            total_summary["days_1_30"] += rem
        elif overdue_days <= 60:
            customers_map[cid]["days_31_60"] += rem
            total_summary["days_31_60"] += rem
        elif overdue_days <= 90:
            customers_map[cid]["days_61_90"] += rem
            total_summary["days_61_90"] += rem
        else:
            customers_map[cid]["days_90_plus"] += rem
            total_summary["days_90_plus"] += rem

    customers_list = []
    for c in sorted(customers_map.values(), key=lambda x: x["total_outstanding"], reverse=True):
        customers_list.append({
            "customer_id": c["customer_id"],
            "customer_number": c["customer_number"],
            "customer_name_ar": c["customer_name_ar"],
            "customer_name_en": c["customer_name_en"],
            "currency": c["currency"],
            "current": str(c["current"]),
            "days_1_30": str(c["days_1_30"]),
            "days_31_60": str(c["days_31_60"]),
            "days_61_90": str(c["days_61_90"]),
            "days_90_plus": str(c["days_90_plus"]),
            "total_outstanding": str(c["total_outstanding"]),
            "invoices_count": c["invoices_count"],
        })

    return {
        "as_of_date": as_of.isoformat(),
        "summary": {k: str(v) for k, v in total_summary.items()},
        "customers": customers_list,
    }


def get_warranties_forecast_report(days_horizon=90) -> dict[str, Any]:
    """Warranties forecast categorized by time remaining until expiry."""
    today = timezone.now().date()

    warranties = WarrantyContract.objects.select_related(
        "asset", "asset__model", "customer"
    ).filter(is_active=True).order_by("end_date")

    buckets = {
        "expired": [],
        "expiring_30d": [],
        "expiring_60d": [],
        "expiring_90d": [],
        "active_long_term": [],
    }

    for w in warranties:
        days_rem = (w.end_date - today).days
        item = {
            "contract_number": w.contract_number,
            "warranty_type": w.warranty_type,
            "warranty_type_display": w.get_warranty_type_display(),
            "asset_serial": w.asset.serial_number,
            "model_code": w.asset.model.model_code,
            "model_name": w.asset.model.model_name,
            "customer_name": w.customer.legal_name_ar if w.customer else "—",
            "start_date": w.start_date.isoformat(),
            "end_date": w.end_date.isoformat(),
            "days_remaining": days_rem,
            "sla_response_hours": w.sla_response_hours,
        }
        if days_rem < 0:
            buckets["expired"].append(item)
        elif days_rem <= 30:
            buckets["expiring_30d"].append(item)
        elif days_rem <= 60:
            buckets["expiring_60d"].append(item)
        elif days_rem <= 90:
            buckets["expiring_90d"].append(item)
        else:
            buckets["active_long_term"].append(item)

    return {
        "today": today.isoformat(),
        "horizon_days": days_horizon,
        "counts": {k: len(v) for k, v in buckets.items()},
        "warranties": buckets,
    }


def get_maintenance_performance_report() -> dict[str, Any]:
    """Biomedical engineering maintenance performance KPIs."""
    tickets_qs = ServiceTicket.objects.select_related("assigned_engineer", "asset", "customer").all()

    by_type = list(tickets_qs.values("ticket_type").annotate(count=Count("id")).order_by("ticket_type"))
    by_priority = list(tickets_qs.values("priority").annotate(count=Count("id")).order_by("priority"))
    by_status = list(tickets_qs.values("status").annotate(count=Count("id")).order_by("status"))

    by_engineer = list(
        tickets_qs.filter(assigned_engineer__isnull=False)
        .values("assigned_engineer__email", "assigned_engineer__full_name")
        .annotate(
            total_assigned=Count("id"),
            resolved=Count("id", filter=Q(status__in=[ServiceTicket.Status.RESOLVED, ServiceTicket.Status.CLOSED])),
        )
        .order_by("-total_assigned")
    )

    resolved_count = tickets_qs.filter(
        status__in=[ServiceTicket.Status.RESOLVED, ServiceTicket.Status.CLOSED]
    ).count()

    total_tickets = tickets_qs.count()
    resolution_rate = round((resolved_count / total_tickets * 100), 2) if total_tickets > 0 else 0.0

    return {
        "total_tickets": total_tickets,
        "resolved_tickets": resolved_count,
        "resolution_rate_percentage": resolution_rate,
        "by_type": by_type,
        "by_priority": by_priority,
        "by_status": by_status,
        "by_engineer": [
            {
                "engineer_name": e["assigned_engineer__full_name"] or e["assigned_engineer__email"],
                "engineer_email": e["assigned_engineer__email"],
                "total_assigned": e["total_assigned"],
                "resolved": e["resolved"],
            }
            for e in by_engineer
        ],
    }


def get_procurement_shipments_report() -> dict[str, Any]:
    """Procurement with Chinese supplier & international logistics status."""
    pos = list(SupplierOrder.objects.values("status").annotate(
        count=Count("id"),
        total_value=Sum("total_amount"),
    ).order_by("status"))

    shipments = list(Shipment.objects.values("status").annotate(
        count=Count("id")
    ).order_by("status"))

    active_shipments_detail = list(
        Shipment.objects.filter(
            status__in=["DISPATCHED", "IN_TRANSIT", "CUSTOMS_CLEARANCE", "PORT_ARRIVAL"]
        ).values(
            "shipment_number", "carrier_name", "tracking_number",
            "origin_port", "destination_port", "estimated_arrival", "status"
        ).order_by("estimated_arrival")
    )

    return {
        "purchase_orders_by_status": [
            {
                "status": p["status"],
                "count": p["count"],
                "total_value": str(p["total_value"] or Decimal("0.00")),
            }
            for p in pos
        ],
        "shipments_by_status": shipments,
        "active_shipments": [
            {
                "shipment_number": s["shipment_number"],
                "carrier_name": s["carrier_name"],
                "tracking_number": s["tracking_number"],
                "origin": s["origin_port"],
                "destination": s["destination_port"],
                "eta": s["estimated_arrival"].isoformat() if s["estimated_arrival"] else None,
                "status": s["status"],
            }
            for s in active_shipments_detail
        ],
    }


# CSV EXPORT GENERATORS

def export_receivables_aging_csv(as_of_date=None) -> str:
    """Generate CSV string for customer debt aging."""
    report = get_receivables_aging_report(as_of_date=as_of_date)
    out = io.StringIO()
    writer = csv.writer(out)

    writer.writerow([
        "Customer Number", "Customer Name (AR)", "Customer Name (EN)",
        "Currency", "Current (Not Overdue)", "1-30 Days", "31-60 Days",
        "61-90 Days", "90+ Days", "Total Outstanding", "Unpaid Invoices Count"
    ])

    for c in report["customers"]:
        writer.writerow([
            c["customer_number"],
            c["customer_name_ar"],
            c["customer_name_en"],
            c["currency"],
            c["current"],
            c["days_1_30"],
            c["days_31_60"],
            c["days_61_90"],
            c["days_90_plus"],
            c["total_outstanding"],
            c["invoices_count"],
        ])

    s = report["summary"]
    writer.writerow([])
    writer.writerow([
        "TOTAL", "ALL CUSTOMERS", "", "",
        s["current"], s["days_1_30"], s["days_31_60"],
        s["days_61_90"], s["days_90_plus"], s["total_outstanding"], ""
    ])

    return out.getvalue()


def export_inventory_assets_csv() -> str:
    """Generate CSV string of serial medical assets with ownership & custody separation."""
    out = io.StringIO()
    writer = csv.writer(out)

    writer.writerow([
        "Asset Serial Number", "Model Code", "Model Name", "Category",
        "Status", "Location Code", "Location Name", "Legal Owner",
        "Physical Custodian", "Manufacture Date"
    ])

    assets = SerialAsset.objects.select_related(
        "model", "model__product", "model__product__category", "current_location"
    ).all().order_by("serial_number")

    for a in assets:
        category_name = a.model.product.category.name_ar if a.model.product.category else ""
        writer.writerow([
            a.serial_number,
            a.model.model_code,
            a.model.model_name,
            category_name,
            a.status,
            a.current_location.code if a.current_location else "",
            a.current_location.name_ar if a.current_location else "",
            a.current_owner,
            a.current_custodian,
            a.manufacture_date.isoformat() if a.manufacture_date else "",
        ])

    return out.getvalue()


def export_trial_balance_csv() -> str:
    """Generate CSV string for live balanced General Ledger trial balance."""
    accounts = Account.objects.all().order_by("code")
    lines_agg = JournalLine.objects.filter(entry__status="POSTED").values("account_id").annotate(
        total_debit=Sum("debit"),
        total_credit=Sum("credit"),
    )
    agg_map = {row["account_id"]: row for row in lines_agg}

    out = io.StringIO()
    writer = csv.writer(out)

    writer.writerow([
        "Account Code", "Account Name (AR)", "Account Name (EN)",
        "Type", "Debit Balance", "Credit Balance", "Net Balance"
    ])

    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")

    for acc in accounts:
        row = agg_map.get(acc.id, {"total_debit": Decimal("0.00"), "total_credit": Decimal("0.00")})
        d = row["total_debit"] or Decimal("0.00")
        c = row["total_credit"] or Decimal("0.00")
        total_debit += d
        total_credit += c
        net = d - c

        writer.writerow([
            acc.code,
            acc.name_ar,
            acc.name_en,
            acc.account_type,
            str(d),
            str(c),
            str(net),
        ])

    writer.writerow([])
    writer.writerow(["TOTAL", "", "", "", str(total_debit), str(total_credit), str(total_debit - total_credit)])
    return out.getvalue()


def export_audit_log_csv(date_from=None, date_to=None) -> str:
    """Generate CSV string of tamper-evident audit trail."""
    out = io.StringIO()
    writer = csv.writer(out)

    writer.writerow([
        "Event ID", "Timestamp", "Actor Email", "Action",
        "Entity Type", "Entity ID", "Client IP", "Summary"
    ])

    events = AuditEvent.objects.select_related("actor").all().order_by("-occurred_at")
    if date_from:
        events = events.filter(occurred_at__date__gte=date_from)
    if date_to:
        events = events.filter(occurred_at__date__lte=date_to)

    for ev in events[:2000]:
        writer.writerow([
            str(ev.id),
            ev.occurred_at.isoformat(),
            ev.actor.email if ev.actor else "System",
            ev.action,
            ev.entity_type,
            ev.entity_id,
            ev.ip_address or "",
            ev.summary[:200],
        ])

    return out.getvalue()

from datetime import datetime

from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity_access.permissions import require
from apps.reporting.services import (
    export_audit_log_csv,
    export_inventory_assets_csv,
    export_receivables_aging_csv,
    export_trial_balance_csv,
    get_commercial_pipeline_report,
    get_dashboard_summary,
    get_maintenance_performance_report,
    get_procurement_shipments_report,
    get_receivables_aging_report,
    get_warranties_forecast_report,
)


def _parse_date(val: str | None):
    if not val:
        return None
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


class DashboardSummaryView(APIView):
    permission_classes = [require("reporting.dashboard.view")]

    def get(self, request):
        data = get_dashboard_summary(request.user)
        return Response(data)


class CommercialReportView(APIView):
    permission_classes = [require("reporting.commercial.view")]

    def get(self, request):
        date_from = _parse_date(request.query_params.get("date_from"))
        date_to = _parse_date(request.query_params.get("date_to"))
        data = get_commercial_pipeline_report(date_from=date_from, date_to=date_to)
        return Response(data)


class ReceivablesAgingReportView(APIView):
    permission_classes = [require("reporting.financial.view")]

    def get(self, request):
        as_of = _parse_date(request.query_params.get("as_of_date"))
        data = get_receivables_aging_report(as_of_date=as_of)
        return Response(data)


class WarrantiesForecastReportView(APIView):
    permission_classes = [require("reporting.biomedical.view")]

    def get(self, request):
        horizon = request.query_params.get("horizon_days")
        try:
            horizon_days = int(horizon) if horizon else 90
        except ValueError:
            horizon_days = 90
        data = get_warranties_forecast_report(days_horizon=horizon_days)
        return Response(data)


class MaintenancePerformanceReportView(APIView):
    permission_classes = [require("reporting.biomedical.view")]

    def get(self, request):
        data = get_maintenance_performance_report()
        return Response(data)


class ProcurementShipmentsReportView(APIView):
    permission_classes = [require("reporting.inventory.view")]

    def get(self, request):
        data = get_procurement_shipments_report()
        return Response(data)


# CSV EXPORT VIEWS

class ExportReceivablesCSVView(APIView):
    permission_classes = [require("reporting.financial.export")]

    def get(self, request):
        as_of = _parse_date(request.query_params.get("as_of_date"))
        csv_data = export_receivables_aging_csv(as_of_date=as_of)
        resp = HttpResponse(csv_data, content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="receivables_aging.csv"'
        return resp


class ExportInventoryAssetsCSVView(APIView):
    permission_classes = [require("reporting.inventory.export")]

    def get(self, request):
        csv_data = export_inventory_assets_csv()
        resp = HttpResponse(csv_data, content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="inventory_assets.csv"'
        return resp


class ExportTrialBalanceCSVView(APIView):
    permission_classes = [require("reporting.financial.export")]

    def get(self, request):
        csv_data = export_trial_balance_csv()
        resp = HttpResponse(csv_data, content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="trial_balance.csv"'
        return resp


class ExportAuditLogCSVView(APIView):
    permission_classes = [require("audit.event.export")]

    def get(self, request):
        date_from = _parse_date(request.query_params.get("date_from"))
        date_to = _parse_date(request.query_params.get("date_to"))
        csv_data = export_audit_log_csv(date_from=date_from, date_to=date_to)
        resp = HttpResponse(csv_data, content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="audit_log.csv"'
        return resp

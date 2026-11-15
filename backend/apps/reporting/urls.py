from django.urls import path

from apps.reporting.views import (
    CommercialReportView,
    DashboardSummaryView,
    ExportAuditLogCSVView,
    ExportInventoryAssetsCSVView,
    ExportReceivablesCSVView,
    ExportTrialBalanceCSVView,
    MaintenancePerformanceReportView,
    ProcurementShipmentsReportView,
    ReceivablesAgingReportView,
    WarrantiesForecastReportView,
)

urlpatterns = [
    path("dashboard/", DashboardSummaryView.as_view(), name="reporting-dashboard"),
    path("commercial/", CommercialReportView.as_view(), name="reporting-commercial"),
    path("receivables-aging/", ReceivablesAgingReportView.as_view(), name="reporting-receivables-aging"),
    path("warranties-forecast/", WarrantiesForecastReportView.as_view(), name="reporting-warranties-forecast"),
    path("maintenance-performance/", MaintenancePerformanceReportView.as_view(), name="reporting-maintenance"),
    path("procurement-shipments/", ProcurementShipmentsReportView.as_view(), name="reporting-procurement-shipments"),
    # CSV Exports
    path("export/receivables/", ExportReceivablesCSVView.as_view(), name="reporting-export-receivables"),
    path("export/inventory-assets/", ExportInventoryAssetsCSVView.as_view(), name="reporting-export-inventory"),
    path("export/trial-balance/", ExportTrialBalanceCSVView.as_view(), name="reporting-export-trial-balance"),
    path("export/audit-log/", ExportAuditLogCSVView.as_view(), name="reporting-export-audit-log"),
]

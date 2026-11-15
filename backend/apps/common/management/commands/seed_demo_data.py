from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounting.models import Currency
from apps.biomedical.models import ServiceTicket, WarrantyContract
from apps.catalog.models import Category, Manufacturer, Product, ProductModel
from apps.crm.models import Customer, Opportunity
from apps.identity_access.management.commands.seed_rbac import sync_rbac
from apps.identity_access.models import Role, User
from apps.inventory.models import Location, SerialAsset
from apps.notifications.services import send_notification
from apps.payments.models import BankAccount, CustomerInvoice, InvoiceStatus
from apps.pricing.models import PriceList, PriceListItem
from apps.procurement.models import Supplier, SupplierOrder
from apps.quotations.models import CommercialModel
from apps.sales_orders.models import Deal
from apps.shipments.models import Shipment


class Command(BaseCommand):
    help = "Seed realistic demo data for testing SMSES platform in browser."

    def handle(self, *args, **options):
        self.stdout.write("Syncing RBAC roles and permissions...")
        sync_rbac()

        # 1. Users
        users_data = [
            ("admin@smses.local", "مدير النظام والمدير العام", ["SYSTEM_ADMIN", "GENERAL_MANAGER"]),
            ("sales@smses.local", "مدير المبيعات", ["SALES_MANAGER"]),
            ("rep@smses.local", "مندوب المبيعات الميداني", ["SALES_REP"]),
            ("engineer@smses.local", "مهندس الهندسة الطبية", ["BIOMED_ENGINEER"]),
            ("accountant@smses.local", "المحاسب المالي", ["ACCOUNTANT"]),
            ("warehouse@smses.local", "أمين المستودع", ["WAREHOUSE_KEEPER"]),
        ]
        created_users = {}
        for email, name, role_codes in users_data:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"full_name": name, "is_active": True, "is_staff": True},
            )
            user.set_password("Admin@123456")
            user.save()
            for code in role_codes:
                try:
                    role = Role.objects.get(code=code)
                    user.roles.add(role)
                except Role.DoesNotExist:
                    pass
            created_users[email] = user
            self.stdout.write(f"User: {email} (Password: Admin@123456) -> {role_codes}")

        admin_user = created_users["admin@smses.local"]
        eng_user = created_users["engineer@smses.local"]

        # 2. Currencies & Bank Accounts
        usd = Currency.objects.get(code="USD")
        yer = Currency.objects.get(code="YER")

        bank_usd, _ = BankAccount.objects.get_or_create(
            name_ar="حساب بنك التضامن الإسلامي (USD)",
            defaults={
                "name_en": "Tadhamon Bank USD Account",
                "bank_name": "بنك التضامن الإسلامي الدولي",
                "account_number": "1002345678",
                "currency": usd,
                "opening_balance": Decimal("150000.00"),
                "current_balance": Decimal("185000.00"),
            },
        )
        cash_box, _ = BankAccount.objects.get_or_create(
            name_ar="صندوق الخزينة الرئيسي - صنعاء",
            defaults={
                "name_en": "Main Cash Vault Sanaa",
                "bank_name": "الخزينة النقدية للشركة",
                "account_number": "CASH-001",
                "currency": yer,
                "opening_balance": Decimal("25000000.00"),
                "current_balance": Decimal("32000000.00"),
            },
        )

        # 3. Suppliers (Chinese Partner)
        supplier_cn, _ = Supplier.objects.get_or_create(
            code="CH-MEDCARE",
            defaults={
                "name_ar": "شركة شنتشن ميديكال كير الصينية المحدودة",
                "name_en": "Shenzhen MedCare Technology Co., Ltd.",
                "country": "China",
                "contact_person": "Li Wei (Director of International Sales)",
                "email": "export@shenzhen-medcare.cn",
                "phone": "+86-755-88889999",
                "currency": "USD",
                "payment_terms": "30% Advance Deposit, 70% before Shipment against B/L copy",
                "is_primary_partner": True,
            },
        )

        # 4. Catalog & Models
        cat_rad, _ = Category.objects.get_or_create(code="RAD", defaults={"name_ar": "أجهزة الأشعة والتصوير الطبي"})
        cat_icu, _ = Category.objects.get_or_create(code="ICU", defaults={"name_ar": "أجهزة العناية المركزة والتنفس"})
        cat_us, _ = Category.objects.get_or_create(code="ULTRA", defaults={"name_ar": "أجهزة الموجات فوق الصوتية والسونار"})

        mfr_cn, _ = Manufacturer.objects.get_or_create(
            code="MEDCARE-CN",
            defaults={
                "name_ar": "ميد كير تكنولوجي - شنتشن",
                "name_en": "MedCare Technology Shenzhen",
                "country": "China",
                "is_primary_partner": True,
            },
        )

        prod_xray, _ = Product.objects.get_or_create(
            code="PRD-DR500",
            defaults={
                "name_ar": "جهاز الأشعة السينية الرقمي DR المعلق",
                "name_en": "Ceiling Mounted Digital Radiography System DR-500",
                "category": cat_rad,
                "manufacturer": mfr_cn,
                "device_class": Product.DeviceClass.CLASS_IIB,
            },
        )
        model_xray, _ = ProductModel.objects.get_or_create(
            product=prod_xray,
            model_code="DR-500X",
            defaults={
                "model_name": "DR-500X Digital Flat Panel System",
                "sku": "SKU-DR500X-CN",
                "standard_warranty_months": 24,
                "approval_status": ProductModel.ApprovalStatus.APPROVED,
                "power_requirements": "380V 3-Phase 50Hz, 65kW",
            },
        )

        prod_vent, _ = Product.objects.get_or_create(
            code="PRD-VENT-V8",
            defaults={
                "name_ar": "جهاز التنفس الاصطناعي الذكي للعناية المركزة",
                "name_en": "Advanced ICU Ventilator V8 Smart",
                "category": cat_icu,
                "manufacturer": mfr_cn,
                "device_class": Product.DeviceClass.CLASS_III,
            },
        )
        model_vent, _ = ProductModel.objects.get_or_create(
            product=prod_vent,
            model_code="VENT-V8",
            defaults={
                "model_name": "VentCare V8 High-End ICU Ventilator",
                "sku": "SKU-VENT-V8-CN",
                "standard_warranty_months": 24,
                "approval_status": ProductModel.ApprovalStatus.APPROVED,
                "power_requirements": "220V 50Hz, Built-in 4h Battery Backup",
            },
        )

        prod_us, _ = Product.objects.get_or_create(
            code="PRD-SONO9",
            defaults={
                "name_ar": "جهاز الموجات فوق الصوتية الملون 4D للأوعية والقلب",
                "name_en": "Color Doppler Ultrasound System SonoPro 9",
                "category": cat_us,
                "manufacturer": mfr_cn,
                "device_class": Product.DeviceClass.CLASS_IIA,
            },
        )
        model_us, _ = ProductModel.objects.get_or_create(
            product=prod_us,
            model_code="SONOPRO-9",
            defaults={
                "model_name": "SonoPro 9 Diagnostic Ultrasound",
                "sku": "SKU-SONO9-CN",
                "standard_warranty_months": 12,
                "approval_status": ProductModel.ApprovalStatus.APPROVED,
                "power_requirements": "220V 50Hz, 800VA",
            },
        )

        # 5. Price List
        plist, _ = PriceList.objects.get_or_create(
            code="PL-2026-USD",
            defaults={
                "name_ar": "قائمة الأسعار القياسية لعام 2026 (دولار)",
                "name_en": "Standard Price List 2026 (USD)",
                "currency": "USD",
                "effective_from": timezone.now().date() - timedelta(days=60),
                "status": PriceList.Status.ACTIVE,
                "is_active": True,
                "is_default": True,
            },
        )
        PriceListItem.objects.get_or_create(
            price_list=plist,
            model=model_xray,
            defaults={
                "cost_price": Decimal("38000.00"),
                "base_price": Decimal("58000.00"),
                "min_price": Decimal("52000.00"),
            },
        )
        PriceListItem.objects.get_or_create(
            price_list=plist,
            model=model_vent,
            defaults={
                "cost_price": Decimal("14000.00"),
                "base_price": Decimal("24000.00"),
                "min_price": Decimal("21000.00"),
            },
        )
        PriceListItem.objects.get_or_create(
            price_list=plist,
            model=model_us,
            defaults={
                "cost_price": Decimal("18000.00"),
                "base_price": Decimal("29500.00"),
                "min_price": Decimal("26500.00"),
            },
        )

        # 6. Customers
        cust_thawra, _ = Customer.objects.get_or_create(
            customer_number="CUST-2026-000001",
            defaults={
                "legal_name_ar": "هيئة مستشفى الثورة العام النموذجي - صنعاء",
                "legal_name_en": "Al-Thawra Modern General Hospital Authority",
                "customer_type": Customer.CustomerType.HOSPITAL,
                "phone": "+967-1-246000",
                "email": "procurement@thawrahospital.ye",
                "governorate": "صنعاء",
            },
        )
        cust_basaheeb, _ = Customer.objects.get_or_create(
            customer_number="CUST-2026-000002",
            defaults={
                "legal_name_ar": "مستشفى باصهيب العسكري العام - عدن",
                "legal_name_en": "Basaheeb Military General Hospital Aden",
                "customer_type": Customer.CustomerType.HOSPITAL,
                "phone": "+967-2-203040",
                "governorate": "عدن",
            },
        )
        cust_ust, _ = Customer.objects.get_or_create(
            customer_number="CUST-2026-000003",
            defaults={
                "legal_name_ar": "مستشفى جامعة العلوم والتكنولوجيا - صنعاء",
                "legal_name_en": "University of Science & Technology Hospital",
                "customer_type": Customer.CustomerType.HOSPITAL,
                "phone": "+967-1-500000",
                "governorate": "صنعاء",
            },
        )

        # 7. Locations
        loc_sanaa, _ = Location.objects.get_or_create(
            code="WH-SANAA-MAIN",
            defaults={
                "name_ar": "المستودع المركزي الطبي الرئيسي - صنعاء",
                "location_type": Location.LocationType.WAREHOUSE,
            },
        )
        loc_aden, _ = Location.objects.get_or_create(
            code="WH-ADEN-FREEZONE",
            defaults={
                "name_ar": "مستودع الترانزيت والمنطقة الحرة - عدن",
                "location_type": Location.LocationType.WAREHOUSE,
            },
        )
        loc_thawra_site, _ = Location.objects.get_or_create(
            code="SITE-THAWRA-HOSP",
            defaults={
                "name_ar": "موقع هيئة مستشفى الثورة - قسم الأشعة التشخيصية",
                "location_type": Location.LocationType.CUSTOMER_SITE,
            },
        )

        # 8. Assets with separated Legal Ownership and Custody (§1.1, §7.1)
        # Asset 1: Installed at customer hospital
        asset1, _ = SerialAsset.objects.get_or_create(
            serial_number="SN-DR500-2026-01",
            defaults={
                "model": model_xray,
                "current_location": loc_thawra_site,
                "current_owner": "هيئة مستشفى الثورة العام (مملوك للعميل بموجب عقد البيع)",
                "current_custodian": "إدارة قسم الأشعة - هيئة مستشفى الثورة",
                "status": SerialAsset.Status.DELIVERED_TO_CUSTOMER,
                "manufacture_date": timezone.now().date() - timedelta(days=90),
                "cost_price": Decimal("38000.00"),
            },
        )
        # Asset 2: In warehouse owned by local company
        asset2, _ = SerialAsset.objects.get_or_create(
            serial_number="SN-VENT-2026-02",
            defaults={
                "model": model_vent,
                "current_location": loc_sanaa,
                "current_owner": "الشركة المحلية (مخزون تجاري مملوك)",
                "current_custodian": "أمين المستودع الطبي المركزي",
                "status": SerialAsset.Status.IN_STOCK,
                "manufacture_date": timezone.now().date() - timedelta(days=45),
                "cost_price": Decimal("14000.00"),
            },
        )
        # Asset 3: In warehouse under consignment from Chinese partner
        asset3, _ = SerialAsset.objects.get_or_create(
            serial_number="SN-SONO-2026-03",
            defaults={
                "model": model_us,
                "current_location": loc_sanaa,
                "current_owner": "الشركة الصينية المصنعة (بضاعة أمانة/وكالة)",
                "current_custodian": "الشركة المحلية - قسم العرض والتجربة",
                "status": SerialAsset.Status.DEMO_LOAN,
                "manufacture_date": timezone.now().date() - timedelta(days=30),
                "cost_price": Decimal("18000.00"),
            },
        )

        # 9. Warranties
        WarrantyContract.objects.get_or_create(
            contract_number="WAR-2026-000001",
            defaults={
                "asset": asset1,
                "customer": cust_thawra,
                "warranty_type": WarrantyContract.WarrantyType.CUSTOMER_WARRANTY,
                "start_date": timezone.now().date() - timedelta(days=60),
                "end_date": timezone.now().date() + timedelta(days=18),  # expiring in 18 days!
                "sla_response_hours": 12,
                "is_active": True,
            },
        )
        WarrantyContract.objects.get_or_create(
            contract_number="WAR-2026-000002",
            defaults={
                "asset": asset1,
                "customer": cust_thawra,
                "warranty_type": WarrantyContract.WarrantyType.MANUFACTURER_WARRANTY,
                "start_date": timezone.now().date() - timedelta(days=90),
                "end_date": timezone.now().date() + timedelta(days=640),
                "sla_response_hours": 48,
                "is_active": True,
            },
        )

        # 10. Service Tickets
        ServiceTicket.objects.get_or_create(
            ticket_number="SRV-2026-000001",
            defaults={
                "asset": asset1,
                "customer": cust_thawra,
                "assigned_engineer": eng_user,
                "ticket_type": ServiceTicket.TicketType.PREVENTIVE,
                "priority": ServiceTicket.Priority.HIGH,
                "title": "صيانة دورية ومعايرة إشعاعية ربع سنوية",
                "reported_issue": "موعد الفحص الدوري المجدول لجهاز الأشعة DR-500X",
                "status": ServiceTicket.Status.IN_PROGRESS,
            },
        )
        ServiceTicket.objects.get_or_create(
            ticket_number="SRV-2026-000002",
            defaults={
                "asset": asset2,
                "customer": cust_basaheeb,
                "assigned_engineer": eng_user,
                "ticket_type": ServiceTicket.TicketType.CALIBRATION,
                "priority": ServiceTicket.Priority.MEDIUM,
                "title": "معايرة حساسات التدفق لجهاز التنفس",
                "reported_issue": "فحص ما قبل التسليم والتشغيل",
                "status": ServiceTicket.Status.OPEN,
            },
        )

        # 11. Commercial Deals, Invoices & Receivables
        deal1, _ = Deal.objects.get_or_create(
            deal_number="DEAL-2026-000001",
            defaults={
                "title": "توريد وتركيب وحدة الأشعة الرقمية DR-500X",
                "customer": cust_thawra,
                "commercial_model": CommercialModel.DIRECT_SALE,
                "seller_of_record": "الشركة المحلية للتجهيزات الطبية",
                "invoice_issuer": "الشركة المحلية للتجهيزات الطبية",
                "payment_recipient": "بنك التضامن الإسلامي الدولي",
                "currency": "USD",
                "total_value": Decimal("58000.00"),
                "status": Deal.Status.CONFIRMED,
            },
        )

        inv1, _ = CustomerInvoice.objects.get_or_create(
            invoice_number="INV-2026-000001",
            defaults={
                "customer": cust_thawra,
                "deal": deal1,
                "invoice_date": timezone.now().date() - timedelta(days=50),
                "due_date": timezone.now().date() - timedelta(days=20),  # 20 days overdue!
                "currency": usd,
                "subtotal": Decimal("58000.00"),
                "total_amount": Decimal("58000.00"),
                "paid_amount": Decimal("20000.00"),
                "status": InvoiceStatus.POSTED,
                "notes": "الدفعة المقدمة مسددة والمتبقي 38000 دولار مستحق عند انتهاء التدريب",
            },
        )

        inv2, _ = CustomerInvoice.objects.get_or_create(
            invoice_number="INV-2026-000002",
            defaults={
                "customer": cust_basaheeb,
                "invoice_date": timezone.now().date() - timedelta(days=10),
                "due_date": timezone.now().date() + timedelta(days=20),
                "currency": usd,
                "subtotal": Decimal("24000.00"),
                "total_amount": Decimal("24000.00"),
                "paid_amount": Decimal("0.00"),
                "status": InvoiceStatus.POSTED,
                "notes": "فاتورة جهاز التنفس الاصطناعي V8",
            },
        )

        # 12. Chinese Supplier Order & International Shipment
        po1, _ = SupplierOrder.objects.get_or_create(
            order_number="PO-2026-000001",
            defaults={
                "supplier": supplier_cn,
                "currency": "USD",
                "total_amount": Decimal("52000.00"),
                "status": SupplierOrder.Status.SHIPPED,
                "supplier_pi_reference": "PI-SZ-2026-8891",
                "shipping_port": "Shenzhen Port, China",
            },
        )

        Shipment.objects.get_or_create(
            shipment_number="SHP-2026-000001",
            defaults={
                "supplier_order": po1,
                "carrier_name": "Cosco Shipping Lines",
                "tracking_number": "COSU6392019482",
                "origin_port": "Shenzhen Port, China",
                "destination_port": "Aden Container Terminal, Yemen",
                "estimated_arrival": timezone.now().date() + timedelta(days=12),
                "status": Shipment.Status.IN_TRANSIT,
            },
        )

        # 13. Opportunities
        Opportunity.objects.get_or_create(
            opportunity_number="OPP-2026-000001",
            defaults={
                "title": "مشروع تجهيز قسم الطوارئ والعناية المركزة",
                "customer": cust_ust,
                "stage": Opportunity.Stage.PROPOSAL,
                "expected_value": Decimal("95000.00"),
                "currency": "USD",
                "probability_pct": 75,
            },
        )
        Opportunity.objects.get_or_create(
            opportunity_number="OPP-2026-000002",
            defaults={
                "title": "تحديث أجهزة السونار للعيادات التخصصية",
                "customer": cust_basaheeb,
                "stage": Opportunity.Stage.QUALIFIED,
                "expected_value": Decimal("48000.00"),
                "currency": "USD",
                "probability_pct": 50,
            },
        )

        # 14. In-App Notifications
        send_notification(
            recipient=admin_user,
            title="مرحباً بك في نظام SMSES للمبيعات والهندسة الطبية",
            message="تم تهيئة وتثبيت النظام بنجاح وتفعيل كافة الوحدات التشغيلية والمالية وفق المواصفات القياسية.",
            channel="IN_APP",
            priority="HIGH",
        )
        send_notification(
            recipient=admin_user,
            title="⚠️ تنبيه استحقاق ضمان طبي قريب",
            message="عقد الضمان رقم WAR-2026-000001 لجهاز الأشعة في هيئة مستشفى الثورة ينتهي خلال 18 يوماً.",
            channel="IN_APP",
            priority="URGENT",
        )
        send_notification(
            recipient=eng_user,
            title="تم إسناد تذكرة صيانة وقائية جديدة",
            message="تم تعيينك مهندساً مسؤولاً عن تذكرة الصيانة الوقائية رقم SRV-2026-000001 في مستشفى الثورة.",
            channel="IN_APP",
            priority="NORMAL",
        )

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully!"))

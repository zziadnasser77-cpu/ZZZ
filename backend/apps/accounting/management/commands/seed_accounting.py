from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounting.models import Account, AccountType, Currency, ExchangeRate


class Command(BaseCommand):
    help = "Seeds initial currencies, exchange rates, and chart of accounts."

    def handle(self, *args, **options):
        currencies_data = [
            {
                "code": "YER",
                "name_ar": "ريال يمني",
                "name_en": "Yemeni Rial",
                "symbol": "ر.ي",
                "is_base": True,
                "decimals": 2,
            },
            {
                "code": "USD",
                "name_ar": "دولار أمريكي",
                "name_en": "US Dollar",
                "symbol": "$",
                "is_base": False,
                "decimals": 2,
            },
            {
                "code": "CNY",
                "name_ar": "يوان صيني",
                "name_en": "Chinese Yuan",
                "symbol": "¥",
                "is_base": False,
                "decimals": 2,
            },
            {
                "code": "SAR",
                "name_ar": "ريال سعودي",
                "name_en": "Saudi Riyal",
                "symbol": "ر.س",
                "is_base": False,
                "decimals": 2,
            },
            {
                "code": "EUR",
                "name_ar": "يورو",
                "name_en": "Euro",
                "symbol": "€",
                "is_base": False,
                "decimals": 2,
            },
        ]

        curr_map = {}
        for c in currencies_data:
            obj, _ = Currency.objects.update_or_create(code=c["code"], defaults=c)
            curr_map[c["code"]] = obj

        yer = curr_map["YER"]
        rates = [
            ("USD", Decimal("535.000000")),
            ("CNY", Decimal("74.500000")),
            ("SAR", Decimal("142.500000")),
            ("EUR", Decimal("575.000000")),
        ]
        today = timezone.now().date()
        for code, rate in rates:
            fc = curr_map[code]
            ExchangeRate.objects.get_or_create(
                from_currency=fc,
                to_currency=yer,
                effective_date=today,
                defaults={"rate": rate, "source": ExchangeRate.Source.CENTRAL_BANK},
            )

        accounts_data = [
            # Assets
            ("1000", "الأصول", "Assets", AccountType.ASSET, None),
            ("1010", "الصندوق والخزينة الرئيسية", "Cash on Hand", AccountType.ASSET, "1000"),
            ("1020", "البنوك والنقدية", "Cash & Bank Accounts", AccountType.ASSET, "1000"),
            ("1120", "العملاء والذمم المدينة", "Accounts Receivable", AccountType.ASSET, "1000"),
            ("1130", "مخزون الأجهزة الطبية", "Medical Equipment Inventory", AccountType.ASSET, "1000"),
            ("1200", "الأصول الثابتة", "Fixed Assets", AccountType.ASSET, "1000"),
            # Liabilities
            ("2000", "الخصوم", "Liabilities", AccountType.LIABILITY, None),
            ("2110", "الموردون والذمم الدائنة", "Accounts Payable", AccountType.LIABILITY, "2000"),
            ("2120", "دفعات مقدمة من العملاء", "Customer Advances", AccountType.LIABILITY, "2000"),
            ("2130", "مستحقات الشركة الصينية", "Chinese Partner Payable", AccountType.LIABILITY, "2000"),
            # Equity
            ("3000", "حقوق الملكية", "Equity", AccountType.EQUITY, None),
            ("3010", "رأس المال", "Share Capital", AccountType.EQUITY, "3000"),
            ("3020", "الأرباح المبقاة", "Retained Earnings", AccountType.EQUITY, "3000"),
            # Revenue
            ("4000", "الإيرادات", "Revenue", AccountType.REVENUE, None),
            (
                "4100",
                "إيرادات مبيعات الأجهزة الطبية",
                "Medical Equipment Sales Revenue",
                AccountType.REVENUE,
                "4000",
            ),
            ("4200", "إيرادات عمولات الوكالة", "Agency Commissions", AccountType.REVENUE, "4000"),
            (
                "4300",
                "إيرادات عقود الصيانة والخدمات",
                "Maintenance & Service Revenue",
                AccountType.REVENUE,
                "4000",
            ),
            # Expenses
            ("5000", "المصروفات", "Expenses", AccountType.EXPENSE, None),
            ("5100", "تكلفة الأجهزة المباعة", "Cost of Goods Sold", AccountType.EXPENSE, "5000"),
            ("5200", "مصاريف الشحن والتخليص", "Freight & Customs Expenses", AccountType.EXPENSE, "5000"),
            (
                "5300",
                "مصاريف عمومية وإدارية",
                "General & Administrative Expenses",
                AccountType.EXPENSE,
                "5000",
            ),
        ]

        created_accounts = {}
        for code, ar, en, acc_type, parent_code in accounts_data:
            parent = created_accounts.get(parent_code)
            acc, _ = Account.objects.update_or_create(
                code=code,
                defaults={
                    "name_ar": ar,
                    "name_en": en,
                    "account_type": acc_type,
                    "parent": parent,
                    "is_active": True,
                },
            )
            created_accounts[code] = acc

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded {len(curr_map)} currencies and {len(created_accounts)} accounts."
            )
        )

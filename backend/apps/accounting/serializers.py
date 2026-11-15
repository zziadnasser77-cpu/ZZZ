from decimal import Decimal

from rest_framework import serializers

from apps.accounting.models import (
    Account,
    Currency,
    ExchangeRate,
    JournalEntry,
    JournalLine,
)


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = [
            "id",
            "code",
            "name_ar",
            "name_en",
            "symbol",
            "is_base",
            "decimals",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ExchangeRateSerializer(serializers.ModelSerializer):
    from_currency_code = serializers.CharField(source="from_currency.code", read_only=True)
    to_currency_code = serializers.CharField(source="to_currency.code", read_only=True)

    class Meta:
        model = ExchangeRate
        fields = [
            "id",
            "from_currency",
            "from_currency_code",
            "to_currency",
            "to_currency_code",
            "rate",
            "effective_date",
            "source",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]


class AccountSerializer(serializers.ModelSerializer):
    parent_code = serializers.CharField(source="parent.code", read_only=True)
    currency_code = serializers.CharField(source="currency.code", read_only=True)

    class Meta:
        model = Account
        fields = [
            "id",
            "code",
            "name_ar",
            "name_en",
            "account_type",
            "parent",
            "parent_code",
            "currency",
            "currency_code",
            "is_reconcilable",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class JournalLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name_ar", read_only=True)
    currency_code = serializers.CharField(source="currency.code", read_only=True)

    class Meta:
        model = JournalLine
        fields = [
            "id",
            "entry",
            "account",
            "account_code",
            "account_name",
            "description",
            "currency",
            "currency_code",
            "exchange_rate",
            "debit",
            "credit",
            "base_debit",
            "base_credit",
            "created_at",
        ]
        read_only_fields = ["id", "entry", "created_at"]


class JournalEntryListSerializer(serializers.ModelSerializer):
    total_debit = serializers.SerializerMethodField()
    total_credit = serializers.SerializerMethodField()

    class Meta:
        model = JournalEntry
        fields = [
            "id",
            "entry_number",
            "entry_date",
            "reference",
            "description",
            "status",
            "source_document_type",
            "total_debit",
            "total_credit",
            "posted_at",
            "created_at",
        ]

    def get_total_debit(self, obj):
        return float(sum((line.base_debit for line in obj.lines.all()), Decimal("0.00")))

    def get_total_credit(self, obj):
        return float(sum((line.base_credit for line in obj.lines.all()), Decimal("0.00")))


class JournalEntryDetailSerializer(serializers.ModelSerializer):
    lines = JournalLineSerializer(many=True, required=False)
    reversed_entry_number = serializers.CharField(source="reversed_entry.entry_number", read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    posted_by_name = serializers.CharField(source="posted_by.full_name", read_only=True)
    total_debit = serializers.SerializerMethodField()
    total_credit = serializers.SerializerMethodField()

    class Meta:
        model = JournalEntry
        fields = [
            "id",
            "entry_number",
            "entry_date",
            "reference",
            "description",
            "status",
            "source_document_type",
            "source_document_id",
            "created_by",
            "created_by_name",
            "posted_by",
            "posted_by_name",
            "posted_at",
            "reversed_entry",
            "reversed_entry_number",
            "total_debit",
            "total_credit",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "entry_number",
            "status",
            "created_by",
            "posted_by",
            "posted_at",
            "reversed_entry",
            "created_at",
            "updated_at",
        ]

    def get_total_debit(self, obj):
        return float(sum((line.base_debit for line in obj.lines.all()), Decimal("0.00")))

    def get_total_credit(self, obj):
        return float(sum((line.base_credit for line in obj.lines.all()), Decimal("0.00")))

    def create(self, validated_data):
        lines_data = self.context["request"].data.get("lines", [])
        validated_data["created_by"] = self.context["request"].user
        entry = JournalEntry.objects.create(**validated_data)
        for line_data in lines_data:
            JournalLine.objects.create(
                entry=entry,
                account_id=line_data["account"],
                description=line_data.get("description", ""),
                currency_id=line_data["currency"],
                exchange_rate=Decimal(str(line_data.get("exchange_rate", "1.000000"))),
                debit=Decimal(str(line_data.get("debit", "0.00"))),
                credit=Decimal(str(line_data.get("credit", "0.00"))),
            )
        return entry

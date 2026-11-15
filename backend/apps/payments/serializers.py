from decimal import Decimal

from rest_framework import serializers

from apps.payments.models import (
    BankAccount,
    CustomerInvoice,
    CustomerInvoiceLine,
    Payment,
    PaymentAllocation,
    SupplierBill,
    SupplierBillLine,
)


class BankAccountSerializer(serializers.ModelSerializer):
    currency_code = serializers.CharField(source="currency.code", read_only=True)
    gl_account_code = serializers.CharField(source="gl_account.code", read_only=True)

    class Meta:
        model = BankAccount
        fields = [
            "id",
            "account_type",
            "name_ar",
            "name_en",
            "bank_name",
            "account_number",
            "iban",
            "swift_bic",
            "currency",
            "currency_code",
            "gl_account",
            "gl_account_code",
            "opening_balance",
            "current_balance",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CustomerInvoiceLineSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source="model.model_name", read_only=True)

    class Meta:
        model = CustomerInvoiceLine
        fields = [
            "id",
            "invoice",
            "model",
            "model_name",
            "description",
            "quantity",
            "unit_price",
            "subtotal",
            "created_at",
        ]
        read_only_fields = ["id", "invoice", "subtotal", "created_at"]


class CustomerInvoiceSerializer(serializers.ModelSerializer):
    lines = CustomerInvoiceLineSerializer(many=True, required=False)
    customer_name = serializers.CharField(source="customer.legal_name_ar", read_only=True)
    currency_code = serializers.CharField(source="currency.code", read_only=True)
    gl_entry_number = serializers.CharField(source="gl_entry.entry_number", read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)

    class Meta:
        model = CustomerInvoice
        fields = [
            "id",
            "invoice_number",
            "sales_order",
            "deal",
            "customer",
            "customer_name",
            "invoice_date",
            "due_date",
            "currency",
            "currency_code",
            "exchange_rate",
            "subtotal",
            "tax_amount",
            "discount_amount",
            "total_amount",
            "paid_amount",
            "remaining_amount",
            "status",
            "gl_entry",
            "gl_entry_number",
            "notes",
            "created_by",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "invoice_number",
            "subtotal",
            "total_amount",
            "paid_amount",
            "remaining_amount",
            "status",
            "gl_entry",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        lines_data = self.context["request"].data.get("lines", [])
        validated_data["created_by"] = self.context["request"].user
        invoice = CustomerInvoice.objects.create(**validated_data)
        subtotal = Decimal("0.00")
        for line_data in lines_data:
            qty = int(line_data.get("quantity", 1))
            price = Decimal(str(line_data.get("unit_price", "0.00")))
            line_sub = qty * price
            subtotal += line_sub
            CustomerInvoiceLine.objects.create(
                invoice=invoice,
                model_id=line_data.get("model"),
                description=line_data.get("description", ""),
                quantity=qty,
                unit_price=price,
                subtotal=line_sub,
            )
        invoice.subtotal = subtotal
        invoice.total_amount = subtotal + invoice.tax_amount - invoice.discount_amount
        invoice.save(update_fields=["subtotal", "total_amount"])
        return invoice


class SupplierBillLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierBillLine
        fields = [
            "id",
            "bill",
            "description",
            "quantity",
            "unit_price",
            "subtotal",
            "created_at",
        ]
        read_only_fields = ["id", "bill", "subtotal", "created_at"]


class SupplierBillSerializer(serializers.ModelSerializer):
    lines = SupplierBillLineSerializer(many=True, required=False)
    supplier_name = serializers.CharField(source="supplier.name_ar", read_only=True)
    currency_code = serializers.CharField(source="currency.code", read_only=True)
    gl_entry_number = serializers.CharField(source="gl_entry.entry_number", read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)

    class Meta:
        model = SupplierBill
        fields = [
            "id",
            "bill_number",
            "supplier_order",
            "supplier",
            "supplier_name",
            "bill_date",
            "due_date",
            "currency",
            "currency_code",
            "exchange_rate",
            "total_amount",
            "paid_amount",
            "remaining_amount",
            "status",
            "gl_entry",
            "gl_entry_number",
            "notes",
            "created_by",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "bill_number",
            "total_amount",
            "paid_amount",
            "remaining_amount",
            "status",
            "gl_entry",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        lines_data = self.context["request"].data.get("lines", [])
        validated_data["created_by"] = self.context["request"].user
        bill = SupplierBill.objects.create(**validated_data)
        total = Decimal("0.00")
        for line_data in lines_data:
            qty = int(line_data.get("quantity", 1))
            price = Decimal(str(line_data.get("unit_price", "0.00")))
            line_sub = qty * price
            total += line_sub
            SupplierBillLine.objects.create(
                bill=bill,
                description=line_data.get("description", ""),
                quantity=qty,
                unit_price=price,
                subtotal=line_sub,
            )
        bill.total_amount = total
        bill.save(update_fields=["total_amount"])
        return bill


class PaymentAllocationSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    bill_number = serializers.CharField(source="bill.bill_number", read_only=True)

    class Meta:
        model = PaymentAllocation
        fields = [
            "id",
            "payment",
            "invoice",
            "invoice_number",
            "bill",
            "bill_number",
            "allocated_amount",
            "allocated_at",
        ]
        read_only_fields = ["id", "allocated_at"]


class PaymentSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.legal_name_ar", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name_ar", read_only=True)
    bank_account_name = serializers.CharField(source="bank_account.name_ar", read_only=True)
    currency_code = serializers.CharField(source="currency.code", read_only=True)
    gl_entry_number = serializers.CharField(source="gl_entry.entry_number", read_only=True)
    allocations = PaymentAllocationSerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "payment_number",
            "payment_type",
            "customer",
            "customer_name",
            "supplier",
            "supplier_name",
            "bank_account",
            "bank_account_name",
            "payment_date",
            "payment_method",
            "reference_number",
            "amount",
            "currency",
            "currency_code",
            "exchange_rate",
            "base_amount",
            "allocated_amount",
            "unallocated_amount",
            "status",
            "gl_entry",
            "gl_entry_number",
            "allocations",
            "notes",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "payment_number",
            "base_amount",
            "allocated_amount",
            "unallocated_amount",
            "status",
            "gl_entry",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)

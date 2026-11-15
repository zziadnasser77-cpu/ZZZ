from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounting.models import (
    Account,
    Currency,
    ExchangeRate,
    JournalEntry,
    JournalLine,
)
from apps.accounting.serializers import (
    AccountSerializer,
    CurrencySerializer,
    ExchangeRateSerializer,
    JournalEntryDetailSerializer,
    JournalEntryListSerializer,
    JournalLineSerializer,
)
from apps.accounting.services import (
    get_trial_balance,
    post_journal_entry,
    reverse_journal_entry,
)
from apps.identity_access.permissions import HasPermission


class CurrencyViewSet(viewsets.ModelViewSet):
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "accounting.currency.view",
        "retrieve": "accounting.currency.view",
        "create": "accounting.currency.edit",
        "update": "accounting.currency.edit",
        "partial_update": "accounting.currency.edit",
        "destroy": "accounting.currency.edit",
    }


class ExchangeRateViewSet(viewsets.ModelViewSet):
    queryset = ExchangeRate.objects.select_related("from_currency", "to_currency", "created_by").all()
    serializer_class = ExchangeRateSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "accounting.rate.view",
        "retrieve": "accounting.rate.view",
        "create": "accounting.rate.edit",
        "update": "accounting.rate.edit",
        "partial_update": "accounting.rate.edit",
        "destroy": "accounting.rate.edit",
    }

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.select_related("parent", "currency").all()
    serializer_class = AccountSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "accounting.account.view",
        "retrieve": "accounting.account.view",
        "create": "accounting.account.edit",
        "update": "accounting.account.edit",
        "partial_update": "accounting.account.edit",
        "destroy": "accounting.account.edit",
    }
    filterset_fields = ["account_type", "is_active", "parent"]
    search_fields = ["code", "name_ar", "name_en"]


class JournalEntryViewSet(viewsets.ModelViewSet):
    queryset = (
        JournalEntry.objects.select_related("created_by", "posted_by", "reversed_entry")
        .prefetch_related("lines__account", "lines__currency")
        .all()
    )
    permission_classes = [HasPermission]
    permission_map = {
        "list": "accounting.entry.view",
        "retrieve": "accounting.entry.view",
        "create": "accounting.entry.create",
        "update": "accounting.entry.edit",
        "partial_update": "accounting.entry.edit",
        "destroy": "accounting.entry.cancel",
        "post_entry": "accounting.entry.post",
        "reverse": "accounting.entry.post",
        "trial_balance": "accounting.report.view",
    }
    filterset_fields = ["status", "entry_date", "source_document_type"]
    search_fields = ["entry_number", "reference", "description"]

    def get_serializer_class(self):
        if self.action == "list":
            return JournalEntryListSerializer
        return JournalEntryDetailSerializer

    @action(detail=True, methods=["post"])
    def post_entry(self, request, pk=None):
        entry = self.get_object()
        post_journal_entry(entry, user=request.user)
        entry = (
            JournalEntry.objects.select_related("created_by", "posted_by", "reversed_entry")
            .prefetch_related("lines__account", "lines__currency")
            .get(pk=entry.pk)
        )
        return Response(JournalEntryDetailSerializer(entry, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        entry = self.get_object()
        reason = request.data.get("reason", "")
        rev_entry = reverse_journal_entry(entry, user=request.user, reason=reason)
        rev_entry = (
            JournalEntry.objects.select_related("created_by", "posted_by", "reversed_entry")
            .prefetch_related("lines__account", "lines__currency")
            .get(pk=rev_entry.pk)
        )
        return Response(
            JournalEntryDetailSerializer(rev_entry, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"])
    def trial_balance(self, request):
        as_of_date = request.query_params.get("as_of_date")
        data = get_trial_balance(as_of_date=as_of_date)
        return Response(data)


class JournalLineViewSet(viewsets.ModelViewSet):
    queryset = JournalLine.objects.select_related("entry", "account", "currency").all()
    serializer_class = JournalLineSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "accounting.entry.view",
        "retrieve": "accounting.entry.view",
        "create": "accounting.entry.edit",
        "update": "accounting.entry.edit",
        "partial_update": "accounting.entry.edit",
        "destroy": "accounting.entry.edit",
    }

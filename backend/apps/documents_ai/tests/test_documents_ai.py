import pytest

from apps.catalog.models import ProductModel
from apps.documents_ai.models import Document, DocumentType, ExtractionJob
from apps.documents_ai.services import (
    review_and_approve_extraction,
    rollback_extraction_approval,
    trigger_ai_extraction,
)
from apps.pricing.models import PriceListItem


@pytest.fixture
def sample_document(db, admin_user):
    return Document.objects.create(
        title="كتالوج جهاز الأشعة الرقمي DR-500",
        document_type=DocumentType.CATALOG_BROCHURE,
        language="zh",
        uploaded_by=admin_user,
    )


@pytest.mark.django_db
def test_document_creation_and_numbering(sample_document):
    assert sample_document.document_number.startswith("DOC-")
    assert sample_document.document_type == DocumentType.CATALOG_BROCHURE


@pytest.mark.django_db
def test_ai_extraction_workflow(sample_document, admin_user):
    job = trigger_ai_extraction(
        document=sample_document,
        target_entity_type=ExtractionJob.TargetEntityType.PRODUCT_SPECS,
        provider="GEMINI_FLASH_GATEWAY",
        user=admin_user,
    )

    assert job.job_number.startswith("EXT-")
    assert job.status == ExtractionJob.Status.AWAITING_REVIEW

    fields = list(job.fields.all())
    assert len(fields) >= 5

    # Non-hallucination verification (§5.12)
    missing_fields = [f for f in fields if f.is_unknown_or_missing]
    assert len(missing_fields) > 0
    assert "[UNKNOWN/NEEDS_REVIEW]" in missing_fields[0].extracted_value


@pytest.mark.django_db
def test_human_review_and_approval(sample_document, admin_user):
    job = trigger_ai_extraction(
        document=sample_document,
        target_entity_type=ExtractionJob.TargetEntityType.PRODUCT_SPECS,
        user=admin_user,
    )

    corrections = {
        "optional_accessories": "محطة عمل إضافية وطابعة ليزرية طبية",
        "supplier_price_usd": "18000.00",
    }

    reviewed = review_and_approve_extraction(
        job=job,
        field_corrections=corrections,
        is_approved=True,
        review_notes="تمت المراجعة والمطابقة مع الفاتورة المبدئية الصينية",
        user=admin_user,
    )

    assert reviewed.status == ExtractionJob.Status.APPROVED
    assert reviewed.reviewed_by == admin_user
    assert reviewed.reviewed_at is not None

    acc_field = job.fields.get(field_key="optional_accessories")
    assert acc_field.corrected_value == "محطة عمل إضافية وطابعة ليزرية طبية"
    assert acc_field.is_approved is True


@pytest.mark.django_db
def test_extraction_publishing_and_rollback(sample_document, admin_user):
    # 1. Product specs publishing
    job = trigger_ai_extraction(
        document=sample_document,
        target_entity_type=ExtractionJob.TargetEntityType.PRODUCT_SPECS,
        user=admin_user,
    )
    reviewed = review_and_approve_extraction(
        job=job,
        field_corrections={"sku": "CN-DR500-GEN3", "model_name": "Digital Radiography DR-500"},
        is_approved=True,
        review_notes="اعتماد ونشر الموديل",
        user=admin_user,
    )
    assert reviewed.status == ExtractionJob.Status.APPROVED

    model_obj = ProductModel.objects.filter(sku="CN-DR500-GEN3").first()
    assert model_obj is not None
    assert model_obj.approval_status == ProductModel.ApprovalStatus.APPROVED

    # 2. Price list publishing
    job_price = trigger_ai_extraction(
        document=sample_document,
        target_entity_type=ExtractionJob.TargetEntityType.PRICE_LIST,
        user=admin_user,
    )
    reviewed_price = review_and_approve_extraction(
        job=job_price,
        field_corrections={"sku": "CN-DR500-GEN3", "supplier_price_usd": "20000.00"},
        is_approved=True,
        review_notes="اعتماد قائمة الأسعار",
        user=admin_user,
    )
    assert reviewed_price.status == ExtractionJob.Status.APPROVED
    price_item = PriceListItem.objects.filter(model=model_obj).first()
    assert price_item is not None
    assert price_item.cost_price == 20000.00
    assert price_item.base_price > price_item.cost_price

    # 3. Rollback test
    rolled_back = rollback_extraction_approval(job=reviewed_price, reason="خطأ في سعر المورد", user=admin_user)
    assert rolled_back.status == ExtractionJob.Status.AWAITING_REVIEW
    assert "تم التراجع" in rolled_back.review_notes

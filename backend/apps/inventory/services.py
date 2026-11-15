from django.db import models, transaction
from django.utils import timezone

from apps.audit.services import log_event
from apps.catalog.models import ProductModel
from apps.common.exceptions import BusinessRuleViolation

from .models import (
    CustodyRecord,
    Location,
    OwnershipRecord,
    SerialAsset,
    StockCount,
    StockMovement,
)


def get_stock_balance(model: ProductModel, location: Location | None = None) -> int:
    """Calculate stock level dynamically from immutable stock movements. Spec §1.1, §5.8."""
    inward_qs = StockMovement.objects.filter(model=model, is_posted=True, to_location__isnull=False)
    outward_qs = StockMovement.objects.filter(model=model, is_posted=True, from_location__isnull=False)

    if location is not None:
        inward_qs = inward_qs.filter(to_location=location)
        outward_qs = outward_qs.filter(from_location=location)

    inward_total = inward_qs.aggregate(total=models.Sum("quantity"))["total"] or 0
    outward_total = outward_qs.aggregate(total=models.Sum("quantity"))["total"] or 0
    return inward_total - outward_total


@transaction.atomic
def record_stock_movement(
    *,
    movement_type: str,
    model: ProductModel,
    quantity: int,
    from_location: Location | None = None,
    to_location: Location | None = None,
    asset: SerialAsset | None = None,
    unit_cost=0.00,
    reference_document="",
    notes="",
    user=None,
) -> StockMovement:
    """Atomically record an immutable stock movement and update serial asset location if applicable."""
    if quantity <= 0:
        raise BusinessRuleViolation("Movement quantity must be positive.")
    if from_location is None and to_location is None:
        raise BusinessRuleViolation("Movement must specify at least one location.")

    total_cost = round(quantity * unit_cost, 2)
    movement = StockMovement.objects.create(
        movement_type=movement_type,
        model=model,
        asset=asset,
        from_location=from_location,
        to_location=to_location,
        quantity=quantity,
        unit_cost=unit_cost,
        total_cost=total_cost,
        reference_document=reference_document,
        is_posted=True,
        notes=notes,
    )

    if asset is not None and to_location is not None:
        asset.current_location = to_location
        if movement_type == StockMovement.MovementType.SALE_DISPATCH:
            asset.status = SerialAsset.Status.DELIVERED_TO_CUSTOMER
        elif to_location.location_type == Location.LocationType.IN_TRANSIT:
            asset.status = SerialAsset.Status.IN_TRANSIT
        elif to_location.location_type == Location.LocationType.MAINTENANCE_LAB:
            asset.status = SerialAsset.Status.IN_MAINTENANCE
        else:
            asset.status = SerialAsset.Status.IN_STOCK
        asset.save(update_fields=["current_location", "status", "updated_at"])

    log_event(
        "inventory.movement_posted",
        entity=movement,
        summary=f"Movement {movement.movement_number} ({movement_type}): {quantity} x {model.model_code}",
        sensitive=True,
    )
    return movement


@transaction.atomic
def transfer_custody(
    asset: SerialAsset,
    *,
    custodian_type: str,
    custodian_name: str,
    purpose: str,
    custodian_user=None,
    notes="",
) -> CustodyRecord:
    """Transfer physical custody without affecting legal ownership. Spec §1.1, §5.8."""
    now = timezone.now()
    # Expire previous custody
    CustodyRecord.objects.filter(asset=asset, is_current=True).update(is_current=False, effective_to=now)

    record = CustodyRecord.objects.create(
        asset=asset,
        custodian_type=custodian_type,
        custodian_name=custodian_name,
        custodian_user=custodian_user,
        effective_from=now,
        purpose=purpose,
        is_current=True,
        notes=notes,
    )
    asset.current_custodian = f"{custodian_name} ({purpose})"
    asset.save(update_fields=["current_custodian", "updated_at"])

    log_event(
        "inventory.custody_transferred",
        entity=asset,
        summary=f"Asset {asset.serial_number} custody transferred to {custodian_name} ({purpose})",
        sensitive=True,
    )
    return record


@transaction.atomic
def transfer_ownership(
    asset: SerialAsset,
    *,
    owner_type: str,
    owner_name: str,
    proof_document_ref: str,
    notes="",
) -> OwnershipRecord:
    """Transfer legal title/ownership with formal documentary proof. Spec §1.1, §5.8."""
    now = timezone.now()
    # Expire previous ownership
    OwnershipRecord.objects.filter(asset=asset, is_current=True).update(is_current=False, effective_to=now)

    record = OwnershipRecord.objects.create(
        asset=asset,
        owner_type=owner_type,
        owner_name=owner_name,
        proof_document_ref=proof_document_ref,
        effective_from=now,
        is_current=True,
        notes=notes,
    )
    asset.current_owner = owner_name
    asset.save(update_fields=["current_owner", "updated_at"])

    log_event(
        "inventory.ownership_transferred",
        entity=asset,
        summary=f"Asset {asset.serial_number} ownership transferred to {owner_name} (Proof: {proof_document_ref})",
        sensitive=True,
    )
    return record


@transaction.atomic
def post_stock_count(stock_count: StockCount, user):
    """Post an approved stock count and generate required adjustment movements. Spec §5.8, §6.5."""
    if stock_count.status != StockCount.Status.APPROVED:
        raise BusinessRuleViolation("Only approved stock counts can be posted.")

    for item in stock_count.items.all():
        diff = item.discrepancy_quantity
        if diff != 0:
            if diff > 0:
                # Overage (surplus found): receipt adjustment into location
                record_stock_movement(
                    movement_type=StockMovement.MovementType.ADJUSTMENT,
                    model=item.model,
                    quantity=abs(diff),
                    from_location=None,
                    to_location=stock_count.location,
                    reference_document=stock_count.count_number,
                    notes=f"Inventory surplus adjustment: +{diff}",
                    user=user,
                )
            else:
                # Shortage (missing): issue adjustment out of location
                record_stock_movement(
                    movement_type=StockMovement.MovementType.ADJUSTMENT,
                    model=item.model,
                    quantity=abs(diff),
                    from_location=stock_count.location,
                    to_location=None,
                    reference_document=stock_count.count_number,
                    notes=f"Inventory shortage adjustment: {diff}",
                    user=user,
                )

    stock_count.status = StockCount.Status.POSTED
    stock_count.save(update_fields=["status", "updated_at"])

    log_event(
        "inventory.count_posted",
        entity=stock_count,
        summary=f"Stock Count {stock_count.count_number} adjustments posted",
        sensitive=True,
    )
    return stock_count

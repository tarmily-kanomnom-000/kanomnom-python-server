from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from core.grocy.exceptions import MetadataNotFoundError

from core.grocy.note_metadata import PurchaseEntryNoteMetadata, validate_note_text
from core.grocy.stock import PurchaseEntryDraft
from models.grocy import (
    GrocyProductInventoryEntry,
    PurchaseEntryDefaultsBatchRequest,
    PurchaseEntryDefaultsBatchResponse,
    PurchaseEntryDefaultsResponse,
    PurchaseEntryMetadataPayload,
    PurchaseEntryRequest,
)

from .dependencies import governor, router
from .helpers import execute_product_mutation, serialize_inventory_view


@dataclass(frozen=True)
class PurchaseDefaultsQuery:
    shopping_location_id: int | None


def _parse_purchase_defaults_query(request: Request) -> PurchaseDefaultsQuery:
    raw_value = request.query_params.get("shopping_location_id")
    if raw_value is None:
        return PurchaseDefaultsQuery(shopping_location_id=None)
    trimmed = raw_value.strip()
    if not trimmed:
        return PurchaseDefaultsQuery(shopping_location_id=None)
    try:
        return PurchaseDefaultsQuery(shopping_location_id=int(trimmed))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="shopping_location_id must be an integer.") from exc


@router.get(
    "/{instance_index}/products/{product_id}/purchase/defaults",
    response_model=PurchaseEntryDefaultsResponse,
)
async def get_purchase_entry_defaults(
    instance_index: str,
    product_id: int,
    request: Request,
) -> PurchaseEntryDefaultsResponse:
    """Return default metadata suggestions for purchase entries."""
    query = _parse_purchase_defaults_query(request)

    def _load_defaults():
        manager = governor.manager_for(instance_index)
        return manager.get_purchase_entry_defaults(product_id, query.shopping_location_id)

    try:
        defaults = await run_in_threadpool(_load_defaults)
    except MetadataNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    metadata_payload = PurchaseEntryMetadataPayload(
        shipping_cost=defaults.shipping_cost,
        tax_rate=defaults.tax_rate,
        brand=defaults.brand,
        package_size=defaults.package_size,
        package_price=defaults.package_price,
        package_quantity=defaults.package_quantity,
        currency=defaults.currency,
        conversion_rate=defaults.conversion_rate,
    )
    return PurchaseEntryDefaultsResponse(
        product_id=product_id,
        shopping_location_id=query.shopping_location_id,
        metadata=metadata_payload,
    )


@router.post(
    "/{instance_index}/purchases/defaults",
    response_model=PurchaseEntryDefaultsBatchResponse,
)
async def get_purchase_entry_defaults_batch(
    instance_index: str,
    payload: PurchaseEntryDefaultsBatchRequest,
) -> PurchaseEntryDefaultsBatchResponse:
    """Return default metadata suggestions for multiple products."""
    if not payload.product_ids:
        raise HTTPException(status_code=400, detail="product_ids must include at least one entry.")

    def _load_defaults():
        manager = governor.manager_for(instance_index)
        return manager.get_purchase_entry_defaults_batch(payload.product_ids, payload.shopping_location_id)

    try:
        defaults = await run_in_threadpool(_load_defaults)
    except MetadataNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    # Future extension: accept richer hints (e.g., prior brand or cost overrides)
    # so downstream heuristics can adjust defaults per context without new endpoints.
    shaped: list[PurchaseEntryDefaultsResponse] = []
    for item, product_id in zip(defaults, payload.product_ids):
        metadata_payload = PurchaseEntryMetadataPayload(
            shipping_cost=item.shipping_cost,
            tax_rate=item.tax_rate,
            brand=item.brand,
            package_size=item.package_size,
            package_price=item.package_price,
            package_quantity=item.package_quantity,
            currency=item.currency,
            conversion_rate=item.conversion_rate,
        )
        shaped.append(
            PurchaseEntryDefaultsResponse(
                product_id=product_id,
                shopping_location_id=payload.shopping_location_id,
                metadata=metadata_payload,
            )
        )

    return PurchaseEntryDefaultsBatchResponse(defaults=shaped)


@router.post(
    "/{instance_index}/products/{product_id}/purchase",
    response_model=GrocyProductInventoryEntry,
)
async def record_purchase_entry(
    instance_index: str,
    product_id: int,
    purchase: PurchaseEntryRequest,
) -> GrocyProductInventoryEntry:
    """Record a purchase entry for the specified product."""

    metadata: PurchaseEntryNoteMetadata | None = None
    derived_amount: float | None = None
    derived_unit_price: float | None = None
    try:
        if purchase.metadata is not None:
            candidate = PurchaseEntryNoteMetadata(
                shipping_cost=purchase.metadata.shipping_cost,
                tax_rate=purchase.metadata.tax_rate,
                brand=purchase.metadata.brand,
                package_size=purchase.metadata.package_size,
                package_price=purchase.metadata.package_price,
                package_quantity=purchase.metadata.package_quantity,
                currency=purchase.metadata.currency,
                conversion_rate=purchase.metadata.conversion_rate,
            )
            derived_amount, derived_unit_price = _derive_purchase_amount_and_price(candidate)
            if candidate.to_attrs():
                metadata = candidate
        validate_note_text(purchase.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    resolved_amount = derived_amount if derived_amount is not None else purchase.amount
    resolved_price = derived_unit_price if derived_unit_price is not None else purchase.price
    if resolved_amount is None or resolved_price is None:
        raise HTTPException(status_code=400, detail="amount and price must be provided or derivable from metadata.")

    draft = PurchaseEntryDraft(
        amount=resolved_amount,
        price_per_unit=resolved_price,
        best_before_date=purchase.best_before_date,
        purchased_date=purchase.purchased_date,
        location_id=purchase.location_id,
        shopping_location_id=purchase.shopping_location_id,
        note=purchase.note,
        metadata=metadata,
    )
    updated_product = await execute_product_mutation(
        instance_index,
        product_id,
        lambda manager, payload: manager.record_purchase_entry(product_id, payload),
        draft,
    )
    return serialize_inventory_view(updated_product)
def _derive_purchase_amount_and_price(metadata: PurchaseEntryNoteMetadata | None) -> tuple[float | None, float | None]:
    if metadata is None:
        return None, None
    if (
        metadata.package_size is None
        or metadata.package_quantity is None
        or metadata.package_price is None
        or metadata.conversion_rate is None
    ):
        return None, None
    amount = metadata.package_size * metadata.package_quantity
    if amount <= 0:
        raise ValueError("package_size and quantity must produce a positive purchase amount.")
    shipping_cost = metadata.shipping_cost or 0.0
    tax_rate = metadata.tax_rate or 0.0
    subtotal = metadata.package_price * metadata.package_quantity + shipping_cost
    total_usd = subtotal * (1 + tax_rate) * metadata.conversion_rate
    if total_usd <= 0:
        raise ValueError("Conversion rate and pricing must produce a positive USD total.")
    unit_price = total_usd / amount
    return amount, unit_price

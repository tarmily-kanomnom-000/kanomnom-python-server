from __future__ import annotations

from fastapi import HTTPException

from core.grocy.note_metadata import InventoryCorrectionNoteMetadata, validate_note_text
from core.grocy.stock import InventoryCorrection
from models.grocy import GrocyProductInventoryEntry, InventoryCorrectionRequest

from .dependencies import router
from .helpers import execute_product_mutation, serialize_inventory_view


@router.post(
    "/{instance_index}/products/{product_id}/inventory",
    response_model=GrocyProductInventoryEntry,
)
async def correct_product_inventory(
    instance_index: str,
    product_id: int,
    correction: InventoryCorrectionRequest,
) -> GrocyProductInventoryEntry:
    """Apply an inventory correction for the specified product."""

    metadata: InventoryCorrectionNoteMetadata | None = None
    try:
        if correction.metadata is not None:
            loss_entries = [
                {"reason": detail.reason, "note": detail.note}
                for detail in (correction.metadata.losses or [])
            ]
            if loss_entries:
                metadata = InventoryCorrectionNoteMetadata(losses=loss_entries)
        validate_note_text(correction.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    mutation = InventoryCorrection(
        new_amount=correction.new_amount,
        best_before_date=correction.best_before_date,
        location_id=correction.location_id,
        note=correction.note,
        metadata=metadata,
    )
    updated_product = await execute_product_mutation(
        instance_index,
        product_id,
        lambda manager, payload: manager.correct_product_inventory(product_id, payload),
        mutation,
    )
    return serialize_inventory_view(updated_product)

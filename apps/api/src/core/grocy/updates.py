from __future__ import annotations

from core.grocy.inventory import ProductDescriptionMetadataUpdate
from core.grocy.note_metadata import (
    ProductDescriptionMetadata,
    ProductUnitConversion,
    validate_note_text,
)
from models.grocy import ProductDescriptionMetadataBatchRequest


def build_product_metadata_updates(
    payload: ProductDescriptionMetadataBatchRequest,
) -> list[ProductDescriptionMetadataUpdate]:
    """Validate and translate product description metadata updates."""
    updates: list[ProductDescriptionMetadataUpdate] = []
    for update in payload.updates:
        validate_note_text(update.description)
        conversions = tuple(
            ProductUnitConversion(
                from_unit=conversion.from_unit,
                to_unit=conversion.to_unit,
                factor=conversion.factor,
                tare=conversion.tare,
            )
            for conversion in update.description_metadata.unit_conversions
        )
        if not conversions and not (update.description or "").strip():
            raise ValueError(
                "description or unit conversions must include at least one entry."
            )
        metadata = ProductDescriptionMetadata(unit_conversions=conversions)
        updates.append(
            ProductDescriptionMetadataUpdate(
                product_id=update.product_id,
                description=update.description,
                metadata=metadata,
            )
        )
    return updates

from __future__ import annotations

from dataclasses import dataclass

from core.grocy.exceptions import MetadataNotFoundError
from core.grocy.inventory import ProductDescriptionMetadataUpdate
from core.grocy.note_metadata import (
    ProductDescriptionMetadata,
    ProductUnitConversion,
    validate_note_text,
)
from fastapi import HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from models.grocy import (
    GrocyProductInventoryEntry,
    GrocyProductsResponse,
    ProductDescriptionMetadataBatchRequest,
)

from .common import parse_force_refresh, with_grocy_manager
from .dependencies import router
from .helpers import serialize_inventory_view


@dataclass(frozen=True)
class GrocyProductsQuery:
    """Query parameters for listing Grocy products."""

    force_refresh: bool


def _parse_products_query(request: Request) -> GrocyProductsQuery:
    return GrocyProductsQuery(force_refresh=parse_force_refresh(request))


@router.get("/{instance_index}/products", response_model=GrocyProductsResponse)
async def list_products(instance_index: str, request: Request) -> GrocyProductsResponse:
    """Return Grocy products enriched with stock quantities and recency info."""
    query = _parse_products_query(request)

    def _load_products():
        return with_grocy_manager(
            instance_index,
            lambda manager: (
                manager.force_refresh_product_inventory()
                or manager.list_product_inventory()
                if query.force_refresh
                else manager.list_product_inventory()
            ),
        )

    try:
        inventory_views = await run_in_threadpool(_load_products)
    except MetadataNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    shaped_products = [serialize_inventory_view(view) for view in inventory_views]

    return GrocyProductsResponse(
        instance_index=instance_index, products=shaped_products
    )


@router.get(
    "/{instance_index}/products/{product_id}", response_model=GrocyProductInventoryEntry
)
async def get_product(
    instance_index: str, product_id: int
) -> GrocyProductInventoryEntry:
    """Return a single Grocy product with fresh stock entries."""

    def _load_product():
        return with_grocy_manager(
            instance_index, lambda manager: manager.get_product_inventory(product_id)
        )

    try:
        inventory_view = await run_in_threadpool(_load_product)
    except MetadataNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return serialize_inventory_view(inventory_view)


@router.post(
    "/{instance_index}/products/description-metadata",
    response_model=GrocyProductsResponse,
)
async def update_product_description_metadata(
    instance_index: str,
    payload: ProductDescriptionMetadataBatchRequest,
) -> GrocyProductsResponse:
    """Apply structured description metadata updates to the specified products."""

    def _apply_updates():
        return with_grocy_manager(
            instance_index,
            lambda manager: manager.update_product_description_metadata(
                _build_product_metadata_updates(payload)
            ),
        )

    try:
        updated_views = await run_in_threadpool(_apply_updates)
    except MetadataNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    shaped_products = [serialize_inventory_view(view) for view in updated_views]
    return GrocyProductsResponse(
        instance_index=instance_index, products=shaped_products
    )


def _build_product_metadata_updates(
    payload: ProductDescriptionMetadataBatchRequest,
) -> list[ProductDescriptionMetadataUpdate]:
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

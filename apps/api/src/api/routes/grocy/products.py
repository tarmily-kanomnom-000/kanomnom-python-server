from __future__ import annotations

from dataclasses import asdict

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from core.grocy.exceptions import MetadataNotFoundError
from models.grocy import GrocyProductInventoryEntry, GrocyProductsResponse

from .dependencies import governor, router


@router.get("/{instance_index}/products", response_model=GrocyProductsResponse)
async def list_products(instance_index: str) -> GrocyProductsResponse:
    """Return Grocy products enriched with stock quantities and recency info."""

    def _load_products():
        manager = governor.manager_for(instance_index)
        return manager.list_product_inventory()

    try:
        inventory_views = await run_in_threadpool(_load_products)
    except MetadataNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    shaped_products = [
        GrocyProductInventoryEntry(
            **asdict(view.product),
            quantity_on_hand=view.quantity_on_hand,
            last_stock_updated_at=view.last_updated_at,
            product_group_name=view.product_group_name,
        )
        for view in inventory_views
    ]

    return GrocyProductsResponse(instance_index=instance_index, products=shaped_products)

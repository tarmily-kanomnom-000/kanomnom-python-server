from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
import logging

from core.cache.grocy_shopping_locations_cache import get_grocy_shopping_locations_cache
from core.grocy.price_analyzer import PriceAnalyzer
from core.grocy.shopping_list_generator import ShoppingListGenerator
from core.grocy.shopping_list_manager import ShoppingListManager
from models.shopping_list import (
    AddItemRequest,
    BulkUpdateRequest,
    GenerateListRequest,
    ShoppingList,
    ShoppingListItem,
)
from models.shopping_list_remove import BulkRemoveRequest

from .dependencies import SERVICE_ROOT, governor, router

# Shopping lists are stored in apps/api/shopping_lists
SHOPPING_LISTS_ROOT = SERVICE_ROOT / "shopping_lists"
logger = logging.getLogger(__name__)


def _get_manager() -> ShoppingListManager:
    """Get shopping list manager instance"""
    return ShoppingListManager(SHOPPING_LISTS_ROOT)


async def _get_generator(instance_index: str, with_price_analyzer: bool = False) -> ShoppingListGenerator:
    """Get shopping list generator instance"""
    try:
        manager = await run_in_threadpool(governor.manager_for, instance_index)
        inventory_service = manager._inventory
        shopping_locations_cache = get_grocy_shopping_locations_cache()

        price_analyzer = None
        if with_price_analyzer:
            grocy_client = manager.client
            price_analyzer = PriceAnalyzer(grocy_client)

        return ShoppingListGenerator(inventory_service, shopping_locations_cache, price_analyzer)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to initialize generator: {exc!s}") from exc


async def _get_price_analyzer(instance_index: str) -> PriceAnalyzer:
    """Get price analyzer instance"""
    try:
        manager = await run_in_threadpool(governor.manager_for, instance_index)
        grocy_client = manager.client
        return PriceAnalyzer(grocy_client)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to initialize price analyzer: {exc!s}") from exc


async def _build_item_data(
    instance_index: str, request: AddItemRequest, price_analyzer: PriceAnalyzer | None = None
) -> dict:
    """Build a shopping list item payload with price/location enrichment."""
    grocy_manager = await run_in_threadpool(governor.manager_for, instance_index)
    inventory_service = grocy_manager._inventory

    products_with_inv = await run_in_threadpool(
        inventory_service.list_products_with_inventory, instance_index
    )
    product_view = None
    for p in products_with_inv:
        if p.product.id == request.product_id:
            product_view = p
            break

    if not product_view:
        raise HTTPException(
            status_code=404,
            detail=f"Product {request.product_id} not found in Grocy",
        )

    current_stock = 0.0
    if product_view.stocks:
        for stock in product_view.stocks:
            current_stock += stock.amount

    shopping_locations_cache = get_grocy_shopping_locations_cache()
    shopping_locations = await run_in_threadpool(
        shopping_locations_cache.load_shopping_locations, instance_index
    )
    location_names = {}
    if shopping_locations:
        location_names = {loc.id: loc.name for loc in shopping_locations}

    location_id = product_view.product.shopping_location_id
    location_name = "UNKNOWN"
    if location_id is not None:
        location_name = location_names.get(location_id, f"Location {location_id}")

    analyzer = price_analyzer or await _get_price_analyzer(instance_index)
    last_price = await run_in_threadpool(
        analyzer.get_last_purchase_price, request.product_id
    )

    now = datetime.utcnow().isoformat() + "Z"
    return {
        "id": str(uuid.uuid4()),
        "product_id": request.product_id,
        "product_name": product_view.product.name,
        "shopping_location_id": location_id,
        "shopping_location_name": location_name,
        "status": "pending",
        "quantity_suggested": request.quantity,
        "quantity_purchased": None,
        "quantity_unit": product_view.stock_unit_name or "unit",
        "current_stock": current_stock,
        "min_stock": product_view.product.min_stock_amount,
        "last_price": last_price,
        "notes": "",
        "checked_at": None,
        "modified_at": now,
    }


@router.post("/{instance_index}/shopping-list/generate", response_model=ShoppingList)
async def generate_shopping_list(
    instance_index: str, request: GenerateListRequest
) -> ShoppingList:
    """Generate shopping list with Phase 2 features (price, merge support)"""
    manager = _get_manager()

    if await run_in_threadpool(manager.active_list_exists, instance_index):
        if not request.merge_with_existing:
            raise HTTPException(
                status_code=409,
                detail="Active shopping list exists. Set merge_with_existing=true to merge, or complete current list first.",
            )

        existing_list = await run_in_threadpool(manager.load_active_list, instance_index)
        generator = await _get_generator(instance_index, with_price_analyzer=True)
        merged_list = await run_in_threadpool(
            generator.merge_with_existing, existing_list, instance_index
        )
        await run_in_threadpool(manager.save_active_list, instance_index, merged_list)
        return ShoppingList(**merged_list)

    generator = await _get_generator(instance_index, with_price_analyzer=True)
    list_data = await run_in_threadpool(generator.generate_list, instance_index, True)

    await run_in_threadpool(manager.save_active_list, instance_index, list_data)

    return ShoppingList(**list_data)


@router.get("/{instance_index}/shopping-list/active", response_model=ShoppingList | None)
async def get_active_list(instance_index: str) -> ShoppingList | None:
    """Get the current active shopping list, or null if none exists"""
    manager = _get_manager()

    try:
        list_data = await run_in_threadpool(manager.load_active_list, instance_index)
        return ShoppingList(**list_data)
    except FileNotFoundError:
        return None


@router.post("/{instance_index}/shopping-list/active/complete")
async def complete_shopping_list(instance_index: str) -> dict[str, str]:
    """Complete the active shopping list (archive and clear)"""
    manager = _get_manager()

    try:
        archived_path = await run_in_threadpool(manager.archive_active_list, instance_index)
        return {
            "archived_to": archived_path,
            "message": "Shopping list completed and archived",
        }
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="No active shopping list to complete",
        ) from exc


@router.post(
    "/{instance_index}/shopping-list/active/items",
    response_model=ShoppingListItem,
    status_code=201,
)
async def add_item(
    instance_index: str,
    request: AddItemRequest,
) -> ShoppingListItem:
    """Add a new item to the active shopping list"""
    manager = _get_manager()

    try:
        analyzer = await _get_price_analyzer(instance_index)
        item_data = await _build_item_data(instance_index, request, analyzer)
        added_item = await run_in_threadpool(manager.add_item, instance_index, item_data)
        return ShoppingListItem(**added_item)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="No active shopping list exists",
        ) from exc


@router.delete(
    "/{instance_index}/shopping-list/active/items/{item_id}",
    status_code=204,
    response_model=None,
)
async def remove_item(
    instance_index: str,
    item_id: str,
):
    """Remove an item from the active shopping list"""
    manager = _get_manager()

    try:
        await run_in_threadpool(manager.remove_item, instance_index, item_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="No active shopping list exists",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{instance_index}/shopping-list/items/bulk",
    response_model=list[ShoppingListItem],
)
async def bulk_update_items(
    instance_index: str,
    request: BulkUpdateRequest,
) -> list[ShoppingListItem]:
    """Update multiple shopping list items in a single request

    This endpoint allows updating multiple items at once, which is more efficient
    than making individual PATCH requests for each item.

    Example request body:
    {
      "updates": [
        {
          "item_id": "uuid-1",
          "status": "purchased",
          "checked_at": "2024-12-30T10:30:00Z"
        },
        {
          "item_id": "uuid-2",
          "status": "purchased",
          "checked_at": "2024-12-30T10:30:00Z"
        }
      ]
    }
    """
    manager = _get_manager()

    try:
        # Convert Pydantic models to dicts for the manager
        updates_dict = [
            {
                "item_id": update.item_id,
                "status": update.status,
                "quantity_purchased": update.quantity_purchased,
                "notes": update.notes,
                "checked_at": update.checked_at,
            }
            for update in request.updates
        ]

        updated_items = await run_in_threadpool(
            manager.bulk_update_items,
            instance_index,
            updates_dict,
        )

        return [ShoppingListItem(**item) for item in updated_items]
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="No active shopping list exists",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.post(
    "/{instance_index}/shopping-list/active/items/bulk",
    response_model=list[ShoppingListItem],
    status_code=201,
)
async def bulk_add_items(
    instance_index: str,
    requests: list[AddItemRequest],
) -> list[ShoppingListItem]:
    """Add multiple items to the active shopping list (Design for N)."""
    manager = _get_manager()

    try:
        analyzer = await _get_price_analyzer(instance_index)
        item_payloads = []
        for req in requests:
          item_payloads.append(await _build_item_data(instance_index, req, analyzer))

        added_items = []
        for payload in item_payloads:
            added_item = await run_in_threadpool(manager.add_item, instance_index, payload)
            added_items.append(ShoppingListItem(**added_item))

        logger.info(
            "shopping_list_bulk_add",
            extra={"instance_index": instance_index, "count": len(added_items)},
        )
        return added_items
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="No active shopping list exists",
        ) from exc


@router.post(
    "/{instance_index}/shopping-list/items/remove",
    response_model=list[ShoppingListItem],
)
async def bulk_remove_items(
    instance_index: str,
    request: BulkRemoveRequest,
) -> list[ShoppingListItem]:
    """Remove multiple items from the active shopping list."""
    manager = _get_manager()

    try:
        removed = await run_in_threadpool(
            manager.bulk_remove_items, instance_index, request
        )
        logger.info(
            "shopping_list_bulk_remove",
            extra={"instance_index": instance_index, "count": len(removed)},
        )
        return [ShoppingListItem(**item) for item in removed]
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="No active shopping list exists",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

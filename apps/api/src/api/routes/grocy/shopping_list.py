from __future__ import annotations

import logging

from core.grocy.shopping_list_service import (
    ShoppingListGeneratorOptions,
    ShoppingListItemNotFoundError,
    ShoppingListItemValidationError,
    ShoppingListServiceError,
    build_items_payloads,
    build_shopping_list_generator,
    build_shopping_list_manager,
)
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from models.shopping_list import (
    AddItemRequest,
    BulkItemUpdate,
    BulkUpdateRequest,
    GenerateListRequest,
    ShoppingList,
    ShoppingListItem,
)
from models.shopping_list_remove import BulkRemoveRequest

from .common import get_manager
from .dependencies import SERVICE_ROOT, router

# Shopping lists are stored in apps/api/shopping_lists
SHOPPING_LISTS_ROOT = SERVICE_ROOT / "shopping_lists"
logger = logging.getLogger(__name__)


def _get_manager():
    """Get shopping list manager instance"""
    return build_shopping_list_manager(SHOPPING_LISTS_ROOT)


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

        existing_list = await run_in_threadpool(
            manager.load_active_list, instance_index
        )
        grocy_manager = await get_manager(instance_index)
        options = ShoppingListGeneratorOptions(with_price_analyzer=True)
        try:
            generator = build_shopping_list_generator(grocy_manager, options)
        except ShoppingListServiceError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        merged_list = await run_in_threadpool(
            generator.merge_with_existing, existing_list, instance_index
        )
        await run_in_threadpool(manager.save_active_list, instance_index, merged_list)
        return ShoppingList(**merged_list)

    grocy_manager = await get_manager(instance_index)
    options = ShoppingListGeneratorOptions(with_price_analyzer=True)
    try:
        generator = build_shopping_list_generator(grocy_manager, options)
    except ShoppingListServiceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    list_data = await run_in_threadpool(generator.generate_list, instance_index, True)

    await run_in_threadpool(manager.save_active_list, instance_index, list_data)

    return ShoppingList(**list_data)


@router.get(
    "/{instance_index}/shopping-list/active", response_model=ShoppingList | None
)
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
        archived_path = await run_in_threadpool(
            manager.archive_active_list, instance_index
        )
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
        grocy_manager = await get_manager(instance_index)
        items_data = await run_in_threadpool(
            build_items_payloads, instance_index, grocy_manager, [request]
        )
        added_items = await run_in_threadpool(
            manager.add_items_bulk, instance_index, items_data
        )
        return ShoppingListItem(**added_items[0])
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="No active shopping list exists",
        ) from exc
    except ShoppingListItemValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ShoppingListItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        status_code = 409 if "already exist" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


def _serialize_updates(updates: list[BulkItemUpdate]) -> list[dict]:
    """
    Convert BulkItemUpdate models into dicts while preserving only caller-specified fields.

    Using exclude_unset avoids sending implicit null shopping_location fields during status-only
    updates, which previously cleared locations and pushed items into the UNKNOWN section.
    """
    return [update.model_dump(exclude_unset=True) for update in updates]


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
        updates_dict = _serialize_updates(request.updates)

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
        status_code = 404 if "Items not found" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


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
        grocy_manager = await get_manager(instance_index)
        item_payloads = await run_in_threadpool(
            build_items_payloads, instance_index, grocy_manager, requests
        )
        added_items = await run_in_threadpool(
            manager.add_items_bulk, instance_index, item_payloads
        )
        shopping_list_items = [ShoppingListItem(**item) for item in added_items]

        logger.info(
            "shopping_list_bulk_add",
            extra={"instance_index": instance_index, "count": len(shopping_list_items)},
        )
        return shopping_list_items
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="No active shopping list exists",
        ) from exc
    except ShoppingListItemValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ShoppingListItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        status_code = 409 if "already exist" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


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
        status_code = 404 if "Items not found" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

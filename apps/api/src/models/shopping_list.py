from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class PriceSnapshot(BaseModel):
    """Last purchase price info for an item"""

    unit_price: float
    purchase_date: str
    shopping_location_name: str


class ShoppingListItem(BaseModel):
    """Shopping list item with price, notes, and flexible quantity"""

    id: str
    product_id: int
    product_name: str
    shopping_location_id: int | None
    shopping_location_name: str
    status: Literal["pending", "purchased", "unavailable"]
    quantity_suggested: float
    quantity_purchased: float | None = None
    quantity_unit: str
    current_stock: float
    min_stock: float
    last_price: PriceSnapshot | None = None
    notes: str = ""
    checked_at: str | None = None
    modified_at: str


class ShoppingList(BaseModel):
    """Shopping list with version tracking"""

    id: str
    instance_index: str
    version: int
    created_at: str
    last_modified_at: str
    items: list[ShoppingListItem]
    location_order: list[str | int]
    deleted_product_ids: list[int] = []  # Track manually deleted products to exclude from merge


class AddItemRequest(BaseModel):
    """Request to add a new item to the shopping list"""

    product_id: int
    quantity: float


class GenerateListRequest(BaseModel):
    """Request to generate a shopping list with optional merge"""

    merge_with_existing: bool


class BulkItemUpdate(BaseModel):
    """Single item update in a bulk operation"""

    item_id: str
    status: Literal["pending", "purchased", "unavailable"] | None = None
    quantity_purchased: float | None = None
    notes: str | None = None
    checked_at: str | None = None
    shopping_location_id: int | None = None
    shopping_location_name: str | None = None


class BulkUpdateRequest(BaseModel):
    """Request to update multiple items at once"""

    updates: list[BulkItemUpdate]


__all__ = [
    "PriceSnapshot",
    "ShoppingListItem",
    "ShoppingList",
    "AddItemRequest",
    "GenerateListRequest",
    "BulkItemUpdate",
    "BulkUpdateRequest",
]

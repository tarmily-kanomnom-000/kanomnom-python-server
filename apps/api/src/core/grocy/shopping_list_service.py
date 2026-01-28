from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.cache.grocy_shopping_locations_cache import get_grocy_shopping_locations_cache
from core.grocy.manager import GrocyManager
from core.grocy.price_analyzer import PriceAnalyzer
from core.grocy.shopping_list_generator import ShoppingListGenerator
from core.grocy.shopping_list_manager import ShoppingListManager
from models.shopping_list import AddItemRequest


class ShoppingListServiceError(RuntimeError):
    """Raised when the shopping list service cannot be initialized."""


class ShoppingListItemValidationError(ValueError):
    """Raised when shopping list item inputs are invalid."""


class ShoppingListItemNotFoundError(ValueError):
    """Raised when requested Grocy products are missing."""


@dataclass(frozen=True)
class ShoppingListGeneratorOptions:
    with_price_analyzer: bool


def build_shopping_list_manager(base_path: Path) -> ShoppingListManager:
    return ShoppingListManager(base_path)


def build_price_analyzer(manager: GrocyManager) -> PriceAnalyzer:
    return PriceAnalyzer(manager.client)


def build_shopping_list_generator(
    manager: GrocyManager,
    options: ShoppingListGeneratorOptions,
) -> ShoppingListGenerator:
    try:
        shopping_locations_cache = get_grocy_shopping_locations_cache()
        price_analyzer = (
            build_price_analyzer(manager) if options.with_price_analyzer else None
        )
        return ShoppingListGenerator(
            manager.inventory_service(), shopping_locations_cache, price_analyzer
        )
    except Exception as exc:
        raise ShoppingListServiceError(
            f"Failed to initialize generator: {exc!s}"
        ) from exc


def build_items_payloads(
    instance_index: str,
    manager: GrocyManager,
    requests: list[AddItemRequest],
) -> list[dict]:
    if not requests:
        raise ShoppingListItemValidationError("No items provided")

    products_with_inv = manager.list_product_inventory()
    product_map = {product.product.id: product for product in products_with_inv}

    requested_product_ids = [req.product_id for req in requests]
    if len(set(requested_product_ids)) != len(requested_product_ids):
        raise ShoppingListItemValidationError("Duplicate product_ids in add request")

    missing_products = [
        product_id
        for product_id in requested_product_ids
        if product_id not in product_map
    ]
    if missing_products:
        missing_str = ", ".join(str(pid) for pid in sorted(missing_products))
        raise ShoppingListItemNotFoundError(
            f"Products not found in Grocy: {missing_str}"
        )

    shopping_locations_cache = get_grocy_shopping_locations_cache()
    shopping_locations = shopping_locations_cache.load_shopping_locations(
        instance_index
    )
    location_names = {}
    if shopping_locations:
        location_names = {loc.id: loc.name for loc in shopping_locations}

    analyzer = build_price_analyzer(manager)

    now = datetime.utcnow().isoformat() + "Z"
    items: list[dict] = []
    for req in requests:
        product_view = product_map[req.product_id]
        current_stock = 0.0
        if product_view.stocks:
            for stock in product_view.stocks:
                current_stock += stock.amount

        location_id = product_view.product.shopping_location_id
        location_name = "UNKNOWN"
        if location_id is not None:
            location_name = location_names.get(location_id, f"Location {location_id}")

        last_price = analyzer.get_last_purchase_price(req.product_id)

        items.append(
            {
                "id": str(uuid.uuid4()),
                "product_id": req.product_id,
                "product_name": product_view.product.name,
                "shopping_location_id": location_id,
                "shopping_location_name": location_name,
                "status": "pending",
                "quantity_suggested": req.quantity,
                "quantity_purchased": None,
                "quantity_unit": product_view.stock_unit_name or "unit",
                "current_stock": current_stock,
                "min_stock": product_view.product.min_stock_amount,
                "last_price": last_price,
                "notes": "",
                "checked_at": None,
                "modified_at": now,
            }
        )

    return items

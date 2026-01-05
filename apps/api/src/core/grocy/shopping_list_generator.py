from __future__ import annotations

import logging
import uuid
from datetime import datetime

from core.cache.grocy_shopping_locations_cache import GrocyShoppingLocationsCacheManager
from core.grocy.price_analyzer import PriceAnalyzer
from core.grocy.inventory import ProductInventoryService

logger = logging.getLogger(__name__)


class ShoppingListGenerator:
    """Generates shopping lists from current inventory state"""

    def __init__(
        self,
        inventory_service: ProductInventoryService,
        shopping_locations_cache: GrocyShoppingLocationsCacheManager,
        price_analyzer: PriceAnalyzer | None = None,
    ) -> None:
        self.inventory_service = inventory_service
        self.shopping_locations_cache = shopping_locations_cache
        self.price_analyzer = price_analyzer

    def generate_list(self, instance_index: str, use_phase2: bool = False) -> dict:
        """
        Generate shopping list from current inventory.

        Args:
            instance_index: The grocy instance to generate list for
            use_phase2: If True, generate Phase 2 format with price, notes, etc.

        Returns:
            Shopping list dict
        """
        products = self.inventory_service.list_products_with_inventory(instance_index)

        shopping_locations = self.shopping_locations_cache.load_shopping_locations(instance_index)
        location_names = {}
        if shopping_locations:
            location_names = {loc.id: loc.name for loc in shopping_locations}

        items_to_buy = []
        for product_view in products:
            if self._needs_purchase(product_view):
                item = self._create_list_item(product_view, location_names, use_phase2)
                items_to_buy.append(item)

        location_order = self._build_location_order(items_to_buy)

        now = datetime.utcnow().isoformat() + "Z"
        shopping_list = {
            "id": str(uuid.uuid4()),
            "instance_index": instance_index,
            "created_at": now,
            "items": items_to_buy,
            "location_order": location_order,
        }

        if use_phase2:
            shopping_list["version"] = 1
            shopping_list["last_modified_at"] = now

        return shopping_list

    def _needs_purchase(self, product_view) -> bool:
        """Check if product is below minimum or out of stock"""
        minimum = product_view.product.min_stock_amount

        # Skip products with no minimum set
        if minimum <= 0:
            return False

        current = self._get_current_stock(product_view)
        return current < minimum

    def _get_current_stock(self, product_view) -> float:
        """Calculate current stock from stock entries"""
        if not product_view.stocks:
            return 0.0

        total = 0.0
        for stock in product_view.stocks:
            total += stock.amount
        return total

    def _create_list_item(self, product_view, location_names: dict[int, str], use_phase2: bool = False) -> dict:
        """Create a shopping list item from product view"""
        current_stock = self._get_current_stock(product_view)
        min_stock = product_view.product.min_stock_amount
        quantity_needed = max(min_stock - current_stock, 1.0)

        location_id = product_view.product.shopping_location_id
        location_name = "UNKNOWN"
        if location_id is not None:
            location_name = location_names.get(location_id, f"Location {location_id}")

        unit_name = product_view.stock_unit_name or "unit"

        item = {
            "id": str(uuid.uuid4()),
            "product_id": product_view.product.id,
            "product_name": product_view.product.name,
            "shopping_location_id": location_id,
            "shopping_location_name": location_name,
            "status": "pending",
            "quantity_needed": quantity_needed,
            "quantity_unit": unit_name,
            "current_stock": current_stock,
            "min_stock": min_stock,
            "checked_at": None,
        }

        if use_phase2:
            now = datetime.utcnow().isoformat() + "Z"
            item["quantity_suggested"] = item.pop("quantity_needed")
            item["quantity_purchased"] = None
            item["notes"] = ""
            item["modified_at"] = now

            last_price = None
            if self.price_analyzer:
                last_price = self.price_analyzer.get_last_purchase_price(product_view.product.id)
            item["last_price"] = last_price

        return item

    def merge_with_existing(self, existing_list: dict, instance_index: str) -> dict:
        """
        Merge newly generated items with existing list.

        Preserves:
        - All checked items (purchased/unavailable)
        - Notes and custom edits on unchecked items
        - Manually deleted items (won't be re-added)

        Updates:
        - Quantities based on current stock levels
        - Price info
        - Adds new items that fell below threshold
        - Removes items no longer needed
        """
        fresh_list = self.generate_list(instance_index, use_phase2=True)

        checked_items = [item for item in existing_list["items"] if item["status"] in ["purchased", "unavailable"]]
        checked_product_ids = {item["product_id"] for item in checked_items}

        existing_unchecked = {item["product_id"]: item for item in existing_list["items"] if item["status"] == "pending"}

        fresh_items_map = {item["product_id"]: item for item in fresh_list["items"]}

        # Get list of manually deleted product IDs to exclude
        deleted_product_ids = set(existing_list.get("deleted_product_ids", []))

        merged_items = []

        merged_items.extend(checked_items)

        merge_summary = {
            "preserved_checked": len(checked_items),
            "merged_pending": 0,
            "added": 0,
            "skipped_deleted": 0,
        }

        for product_id, fresh_item in fresh_items_map.items():
            # Skip products that were manually deleted
            if product_id in deleted_product_ids:
                merge_summary["skipped_deleted"] += 1
                continue

            # Skip products that were already purchased/unavailable to avoid duplicates
            if product_id in checked_product_ids:
                continue

            if product_id in existing_unchecked:
                existing_item = existing_unchecked[product_id]
                existing_item["quantity_suggested"] = fresh_item["quantity_suggested"]
                existing_item["current_stock"] = fresh_item["current_stock"]
                existing_item["min_stock"] = fresh_item["min_stock"]
                existing_item["last_price"] = fresh_item["last_price"]
                existing_item["modified_at"] = fresh_item["modified_at"]
                merged_items.append(existing_item)
                merge_summary["merged_pending"] += 1
            else:
                merged_items.append(fresh_item)
                merge_summary["added"] += 1

        location_order = self._build_location_order(merged_items)

        now = datetime.utcnow().isoformat() + "Z"

        logger.info(
            "shopping_list_merge_summary",
            extra={
                "instance_index": instance_index,
                **merge_summary,
                "result_items": len(merged_items),
                "deleted_product_ids": len(deleted_product_ids),
            },
        )

        return {
            "id": existing_list["id"],
            "instance_index": instance_index,
            "version": existing_list.get("version", 1) + 1,
            "created_at": existing_list["created_at"],
            "last_modified_at": now,
            "items": merged_items,
            "location_order": location_order,
            "deleted_product_ids": list(deleted_product_ids),
        }

    def _build_location_order(self, items: list[dict]) -> list[str | int]:
        """Build ordered list of location IDs for display"""
        location_ids = set()

        for item in items:
            loc_id = item["shopping_location_id"]
            if loc_id is None:
                location_ids.add("UNKNOWN")
            else:
                location_ids.add(loc_id)

        sorted_locations = []
        if "UNKNOWN" in location_ids:
            sorted_locations.append("UNKNOWN")

        numeric_locations = sorted([loc for loc in location_ids if loc != "UNKNOWN"])
        sorted_locations.extend(numeric_locations)

        return sorted_locations

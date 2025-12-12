from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.core.cache.grocy_product_cache import GrocyProductCacheManager
from src.core.cache.grocy_product_groups_cache import get_grocy_product_groups_cache
from src.core.cache.grocy_stock_cache import GrocyStockCacheManager
from src.core.cache.grocy_stock_log_cache import GrocyStockLogCacheManager
from src.core.grocy.client import GrocyClient
from src.core.grocy.responses import GrocyProduct, GrocyProductGroup, GrocyStockEntry, GrocyStockLogEntry


@dataclass(frozen=True)
class StockUpdateSettings:
    """Configuration for computing fallback timestamps."""

    cold_start_timestamp: datetime


@dataclass(frozen=True)
class ProductInventoryView:
    """Represents a Grocy product enriched with stock metadata."""

    product: GrocyProduct
    last_updated_at: datetime
    quantity_on_hand: float
    product_group_name: str | None


class ProductInventoryService:
    """Enriches Grocy product payloads with inventory metadata."""

    def __init__(
        self,
        client: GrocyClient,
        product_cache: GrocyProductCacheManager,
        stock_log_cache: GrocyStockLogCacheManager,
        stock_cache: GrocyStockCacheManager,
        settings: StockUpdateSettings,
    ) -> None:
        self.client = client
        self.product_cache = product_cache
        self.stock_log_cache = stock_log_cache
        self.stock_cache = stock_cache
        self._settings = settings
        self._product_groups_cache = get_grocy_product_groups_cache()

    def list_products_with_inventory(self, instance_index: str) -> list[ProductInventoryView]:
        """Return Grocy products with stock quantities and recency information."""
        products = self._load_products(instance_index)
        stock_log = self._load_stock_log(instance_index)
        last_update_by_id = _map_last_update(stock_log)
        stock_state = self._load_stock_state(instance_index)
        fallback = self._settings.cold_start_timestamp
        groups_by_id = {group.id: group.name for group in self._load_product_groups(instance_index)}
        enriched = []
        for product in products:
            last_updated = last_update_by_id.get(product.id, fallback)
            quantity = stock_state.get(product.id, 0.0)
            enriched.append(
                ProductInventoryView(
                    product=product,
                    last_updated_at=last_updated,
                    quantity_on_hand=quantity,
                    product_group_name=groups_by_id.get(product.product_group_id),
                )
            )
        enriched.sort(key=lambda entry: entry.product.name.lower())
        return enriched

    def _load_products(self, instance_index: str) -> list[GrocyProduct]:
        cached_products = self.product_cache.load_products(instance_index)
        if cached_products is not None:
            return cached_products
        products = self.client.list_products()
        self.product_cache.save_products(instance_index, products)
        return products

    def _load_stock_log(self, instance_index: str) -> list[GrocyStockLogEntry]:
        cached_log = self.stock_log_cache.load_log(instance_index)
        if cached_log is not None:
            return cached_log
        entries = self.client.list_stock_log()
        self.stock_log_cache.save_log(instance_index, entries)
        return entries

    def _load_stock_state(self, instance_index: str) -> dict[int, float]:
        cached_stock = self.stock_cache.load_stock(instance_index)
        if cached_stock is not None:
            return _map_stock_amounts(cached_stock)
        entries = self.client.list_stock()
        self.stock_cache.save_stock(instance_index, entries)
        return _map_stock_amounts(entries)

    def _load_product_groups(self, instance_index: str) -> list[GrocyProductGroup]:
        cached = self._product_groups_cache.load_groups(instance_index)
        if cached is not None:
            return cached
        groups = self.client.list_product_groups()
        self._product_groups_cache.save_groups(instance_index, groups)
        return groups


def _map_last_update(stock_log_entries: list[GrocyStockLogEntry]) -> dict[int, datetime]:
    """Determine the most recent stock log timestamp per product id."""
    last_update: dict[int, datetime] = {}
    for entry in stock_log_entries:
        product_id = entry.product_id
        timestamp = entry.row_created_timestamp
        current = last_update.get(product_id)
        if current is None or timestamp > current:
            last_update[product_id] = timestamp
    return last_update


def _map_stock_amounts(entries: list[GrocyStockEntry]) -> dict[int, float]:
    stock_map: dict[int, float] = {}
    for entry in entries:
        stock_map[entry.product_id] = entry.amount
    return stock_map

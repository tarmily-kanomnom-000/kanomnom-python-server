from __future__ import annotations

from datetime import datetime, timezone

from src.core.cache.grocy_locations_cache import get_grocy_locations_cache
from src.core.cache.grocy_product_cache import get_grocy_product_cache
from src.core.cache.grocy_stock_cache import get_grocy_stock_cache
from src.core.cache.grocy_stock_log_cache import get_grocy_stock_log_cache
from src.core.grocy.client import GrocyClient
from src.core.grocy.models import QuantityUnitDefinition, UniversalManifest
from src.core.grocy.responses import GrocyLocation
from src.core.grocy.services import QuantityUnitService, QuantityUnitSyncResult
from src.core.grocy.stock import ProductInventoryService, ProductInventoryView, StockUpdateSettings
from src.core.grocy.sync import EntitySyncer

_STOCK_UPDATE_SETTINGS = StockUpdateSettings(
    cold_start_timestamp=datetime(1900, 1, 1, tzinfo=timezone.utc),
)


class GrocyManager:
    """High-level orchestrator that exposes operations for Grocy instances."""

    def __init__(self, instance_index: str, client: GrocyClient) -> None:
        self.instance_index = instance_index
        self.client = client
        self._syncer: EntitySyncer[QuantityUnitDefinition] = EntitySyncer()
        self.quantity_units = QuantityUnitService(self.client, self._syncer)
        self._inventory = ProductInventoryService(
            self.client,
            get_grocy_product_cache(),
            get_grocy_stock_log_cache(),
            get_grocy_stock_cache(),
            _STOCK_UPDATE_SETTINGS,
        )
        self._locations_cache = get_grocy_locations_cache()

    def ensure_quantity_units(self, manifest: UniversalManifest) -> QuantityUnitSyncResult:
        """Ensure the provided manifest quantity units exist in Grocy."""
        return self.quantity_units.ensure_quantity_units(manifest.quantity_units)

    def list_product_inventory(self) -> list[ProductInventoryView]:
        """Return products merged with stock availability metadata."""
        return self._inventory.list_products_with_inventory(self.instance_index)

    def list_locations(self) -> list[GrocyLocation]:
        """Return cached Grocy locations for this instance."""
        cached = self._locations_cache.load_locations(self.instance_index)
        if cached is not None:
            return cached
        locations = self.client.list_locations()
        self._locations_cache.save_locations(self.instance_index, locations)
        return locations

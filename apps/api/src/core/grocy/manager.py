from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from core.cache.grocy_locations_cache import get_grocy_locations_cache
from core.cache.grocy_product_cache import get_grocy_product_cache
from core.cache.grocy_quantity_units_cache import get_grocy_quantity_units_cache
from core.cache.grocy_shopping_locations_cache import get_grocy_shopping_locations_cache
from core.cache.grocy_stock_cache import get_grocy_stock_cache
from core.cache.grocy_stock_log_cache import get_grocy_stock_log_cache
from core.grocy.client import GrocyClient
from core.grocy.models import (
    ProductGroupDefinition,
    QuantityUnitDefinition,
    UniversalManifest,
)
from core.grocy.responses import GrocyLocation, GrocyShoppingLocation
from core.grocy.services import (
    ProductGroupService,
    ProductGroupSyncResult,
    QuantityUnitService,
    QuantityUnitSyncResult,
)
from core.grocy.stock import (
    InventoryCorrection,
    ProductInventoryService,
    ProductInventoryView,
    PurchaseEntry,
    PurchaseEntryDefaults,
    PurchaseEntryDraft,
    StockUpdateSettings,
)
from core.grocy.sync import EntitySyncer

_STOCK_UPDATE_SETTINGS = StockUpdateSettings(
    cold_start_timestamp=datetime(1900, 1, 1, tzinfo=timezone.utc),
)


class GrocyManager:
    """High-level orchestrator that exposes operations for Grocy instances."""

    def __init__(self, instance_index: str, client: GrocyClient) -> None:
        self.instance_index = instance_index
        self.client = client
        self._quantity_unit_syncer: EntitySyncer[QuantityUnitDefinition] = EntitySyncer()
        self._product_group_syncer: EntitySyncer[ProductGroupDefinition] = EntitySyncer()
        self.quantity_units = QuantityUnitService(self.client, self._quantity_unit_syncer)
        self.product_groups = ProductGroupService(self.client, self._product_group_syncer)
        self._inventory = ProductInventoryService(
            self.client,
            get_grocy_product_cache(),
            get_grocy_stock_log_cache(),
            get_grocy_stock_cache(),
            get_grocy_quantity_units_cache(),
            _STOCK_UPDATE_SETTINGS,
        )
        self._locations_cache = get_grocy_locations_cache()
        self._shopping_locations_cache = get_grocy_shopping_locations_cache()

    def ensure_quantity_units(self, manifest: UniversalManifest) -> QuantityUnitSyncResult:
        """Ensure the provided manifest quantity units exist in Grocy."""
        return self.quantity_units.ensure_quantity_units(manifest.quantity_units)

    def ensure_product_groups(self, manifest: UniversalManifest) -> ProductGroupSyncResult:
        """Ensure the provided manifest product groups exist in Grocy."""
        return self.product_groups.ensure_product_groups(manifest.product_groups)

    def list_product_inventory(self) -> list[ProductInventoryView]:
        """Return products merged with stock availability metadata."""
        return self._inventory.list_products_with_inventory(self.instance_index)

    def force_refresh_product_inventory(self) -> None:
        """Clear cached inventory artifacts so subsequent reads fetch fresh data."""
        self._inventory.force_refresh_inventory(self.instance_index)

    def get_product_inventory(self, product_id: int) -> ProductInventoryView:
        """Return a single product with refreshed stock entries."""
        return self._inventory.get_product_inventory(self.instance_index, product_id)

    def list_locations(self) -> list[GrocyLocation]:
        """Return cached Grocy locations for this instance."""
        return self._load_or_fetch(
            self._locations_cache.load_locations,
            self.client.list_locations,
            self._locations_cache.save_locations,
        )

    def correct_product_inventory(
        self, product_id: int, correction: InventoryCorrection
    ) -> tuple[InventoryCorrection, dict[str, Any] | list[dict[str, Any]] | None]:
        """Apply an inventory correction to a Grocy product."""
        resolved = self._inventory.resolve_inventory_correction(self.instance_index, product_id, correction)
        response = self.client.correct_product_inventory(product_id, resolved.to_payload())
        self._refresh_inventory_caches()
        return resolved, response

    def record_purchase_entry(
        self, product_id: int, entry: PurchaseEntryDraft
    ) -> tuple[PurchaseEntry, dict[str, Any] | list[dict[str, Any]] | None]:
        """Record a purchase entry for a Grocy product."""
        resolved = self._inventory.resolve_purchase_entry(self.instance_index, product_id, entry)
        response = self.client.add_product_purchase_entry(product_id, resolved.to_payload())
        self._refresh_inventory_caches()
        return resolved, response

    def get_purchase_entry_defaults(self, product_id: int, shopping_location_id: int | None) -> PurchaseEntryDefaults:
        """Return default metadata suggestions for purchase entry mutations."""
        return self._inventory.build_purchase_defaults(self.instance_index, product_id, shopping_location_id)

    def get_purchase_entry_defaults_batch(
        self, product_ids: list[int], shopping_location_id: int | None
    ) -> list[PurchaseEntryDefaults]:
        """Return purchase metadata defaults for multiple products."""
        defaults: list[PurchaseEntryDefaults] = []
        for product_id in product_ids:
            defaults.append(
                self._inventory.build_purchase_defaults(self.instance_index, product_id, shopping_location_id)
            )
        return defaults

    def list_shopping_locations(self) -> list[GrocyShoppingLocation]:
        """Return cached Grocy shopping locations for this instance."""
        return self._load_or_fetch(
            self._shopping_locations_cache.load_shopping_locations,
            self.client.list_shopping_locations,
            self._shopping_locations_cache.save_shopping_locations,
        )

    def _refresh_inventory_caches(self) -> None:
        self._inventory.invalidate_inventory_caches(self.instance_index)
        self._inventory.refresh_inventory_caches(self.instance_index)

    def _load_or_fetch(
        self,
        loader: Callable[[str], Any],
        fetcher: Callable[[], Any],
        saver: Callable[[str, Any], None],
    ) -> Any:
        cached = loader(self.instance_index)
        if cached is not None:
            return cached
        fresh = fetcher()
        saver(self.instance_index, fresh)
        return fresh

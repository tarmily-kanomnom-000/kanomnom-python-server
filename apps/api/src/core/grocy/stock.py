from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from core.cache.grocy_product_cache import GrocyProductCacheManager
from core.cache.grocy_product_groups_cache import get_grocy_product_groups_cache
from core.cache.grocy_quantity_units_cache import GrocyQuantityUnitsCacheManager
from core.cache.grocy_stock_cache import GrocyStockCacheManager
from core.cache.grocy_stock_log_cache import GrocyStockLogCacheManager
from core.grocy.client import GrocyClient
from core.grocy.note_metadata import (
    InventoryCorrectionNoteMetadata,
    PurchaseEntryNoteMetadata,
    encode_structured_note,
)
from core.grocy.responses import GrocyProduct, GrocyProductGroup, GrocyQuantityUnit, GrocyStockEntry, GrocyStockLogEntry


@dataclass(frozen=True)
class StockUpdateSettings:
    """Configuration for computing fallback timestamps."""

    cold_start_timestamp: datetime


@dataclass(frozen=True)
class ProductInventoryView:
    """Represents a Grocy product enriched with stock metadata."""

    product: GrocyProduct
    last_updated_at: datetime
    product_group_name: str | None
    purchase_unit_name: str | None
    stock_unit_name: str | None
    consume_unit_name: str | None
    price_unit_name: str | None
    unit_name_lookup: dict[str, str]
    discrete_units: dict[str, bool]
    stocks: list[GrocyStockEntry]


@dataclass(frozen=True)
class InventoryContext:
    """Shared metadata required to build product inventory views."""

    groups_by_id: dict[int, str]
    unit_names: dict[int, str]
    discrete_units: dict[str, bool]
    unit_name_lookup: dict[str, str]


@dataclass(frozen=True)
class InventoryCorrection:
    """Inventory correction payload resolved with optional defaults."""

    new_amount: float
    best_before_date: date | None
    location_id: int | None
    note: str | None
    metadata: InventoryCorrectionNoteMetadata | None = None

    def to_payload(self) -> dict[str, Any]:
        note_payload = encode_structured_note(self.note, self.metadata)
        payload: dict[str, Any] = {
            "new_amount": self.new_amount,
            "shopping_location_id": None,
            "price": 0,
        }
        if self.best_before_date is not None:
            payload["best_before_date"] = self.best_before_date.isoformat()
        if self.location_id is not None:
            payload["location_id"] = self.location_id
        if note_payload is not None:
            payload["note"] = note_payload
        return payload


@dataclass(frozen=True)
class PurchaseEntryDraft:
    """Raw purchase entry payload provided by callers."""

    amount: float
    price_per_unit: float
    best_before_date: date | None
    purchased_date: date | None
    location_id: int | None
    shopping_location_id: int | None
    note: str | None
    metadata: PurchaseEntryNoteMetadata | None = None


@dataclass(frozen=True)
class PurchaseEntry:
    """Purchase entry resolved with defaults before persisting."""

    amount: float
    price_per_unit: float
    best_before_date: date | None
    purchased_date: date
    location_id: int | None
    shopping_location_id: int | None
    note: str | None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "amount": self.amount,
            "transaction_type": "purchase",
            "price": self.price_per_unit,
            "purchased_date": self.purchased_date.isoformat(),
        }
        if self.best_before_date is not None:
            payload["best_before_date"] = self.best_before_date.isoformat()
        if self.location_id is not None:
            payload["location_id"] = self.location_id
        if self.shopping_location_id is not None:
            payload["shopping_location_id"] = self.shopping_location_id
        if self.note:
            payload["note"] = self.note
        return payload


@dataclass(frozen=True)
class PurchaseEntryDefaults:
    """Default metadata suggestions for a purchase entry."""

    shipping_cost: float
    tax_rate: float
    on_sale: bool
    brand: str | None = None
    package_size: float | None = None
    package_price: float | None = None
    package_quantity: float | None = None
    currency: str | None = None
    conversion_rate: float | None = None


class ProductInventoryService:
    """Enriches Grocy product payloads with inventory metadata."""

    def __init__(
        self,
        client: GrocyClient,
        product_cache: GrocyProductCacheManager,
        stock_log_cache: GrocyStockLogCacheManager,
        stock_cache: GrocyStockCacheManager,
        quantity_units_cache: GrocyQuantityUnitsCacheManager,
        settings: StockUpdateSettings,
    ) -> None:
        self.client = client
        self.product_cache = product_cache
        self.stock_log_cache = stock_log_cache
        self.stock_cache = stock_cache
        self._quantity_units_cache = quantity_units_cache
        self._settings = settings
        self._product_groups_cache = get_grocy_product_groups_cache()
        self._product_lookup: dict[str, dict[int, GrocyProduct]] = {}

    def list_products_with_inventory(self, instance_index: str) -> list[ProductInventoryView]:
        """Return Grocy products with stock quantities and recency information."""
        products = self._load_products(instance_index)
        stock_log = self._load_stock_log(instance_index)
        last_update_by_id = _map_last_update(stock_log)
        stock_entries = self._load_stock_entries(instance_index)
        stock_entries_by_product = _group_stock_entries(stock_entries)
        fallback = self._settings.cold_start_timestamp
        context = self._build_inventory_context(instance_index)
        enriched = []
        for product in products:
            entries_for_product = stock_entries_by_product.get(product.id, [])
            enriched.append(
                self._create_inventory_view(
                    product,
                    entries_for_product,
                    context.groups_by_id,
                    context.unit_names,
                    context.discrete_units,
                    context.unit_name_lookup,
                    fallback,
                    last_update_by_id.get(product.id),
                )
            )
        enriched.sort(key=lambda entry: entry.product.name.lower())
        return enriched

    def get_product_inventory(
        self,
        instance_index: str,
        product_id: int,
    ) -> ProductInventoryView:
        """Return a single product with refreshed stock entries."""
        product = self._get_product(instance_index, product_id)
        entries = self.client.list_product_stock_entries(product_id)
        context = self._build_inventory_context(instance_index)
        return self._create_inventory_view(
            product,
            entries,
            context.groups_by_id,
            context.unit_names,
            context.discrete_units,
            context.unit_name_lookup,
            self._settings.cold_start_timestamp,
        )

    def resolve_inventory_correction(
        self,
        instance_index: str,
        product_id: int,
        correction: InventoryCorrection,
    ) -> InventoryCorrection:
        """Fill missing fields in an inventory correction using product defaults."""
        product = self._get_product(instance_index, product_id)
        best_before_date = correction.best_before_date
        if best_before_date is None:
            best_before_date = _default_best_before_date(product)
        location_id = correction.location_id if correction.location_id is not None else product.location_id
        return InventoryCorrection(
            new_amount=correction.new_amount,
            best_before_date=best_before_date,
            location_id=location_id,
            note=correction.note,
            metadata=correction.metadata,
        )

    def resolve_purchase_entry(
        self,
        instance_index: str,
        product_id: int,
        entry: PurchaseEntryDraft,
    ) -> PurchaseEntry:
        """Fill missing purchase entry fields using product defaults."""
        product = self._get_product(instance_index, product_id)
        tare_weight = product.tare_weight if product.enable_tare_weight_handling and product.tare_weight > 0 else 0
        if tare_weight > 0:
            current_stock = self._current_stock_amount(product_id)
            amount = entry.amount + current_stock + tare_weight
        else:
            amount = entry.amount
        best_before_date = entry.best_before_date
        if best_before_date is None:
            best_before_date = _default_best_before_date(product)
        purchased_date = entry.purchased_date or date.today()
        location_id = entry.location_id if entry.location_id is not None else product.location_id
        shopping_location_id = (
            entry.shopping_location_id if entry.shopping_location_id is not None else product.shopping_location_id
        )
        rounded_price = _round_price(entry.price_per_unit)
        note_payload = encode_structured_note(entry.note, entry.metadata)
        return PurchaseEntry(
            amount=amount,
            price_per_unit=rounded_price,
            best_before_date=best_before_date,
            purchased_date=purchased_date,
            location_id=location_id,
            shopping_location_id=shopping_location_id,
            note=note_payload,
        )

    def build_purchase_defaults(
        self,
        instance_index: str,
        product_id: int,
        _shopping_location_id: int | None,
    ) -> PurchaseEntryDefaults:
        """Return default metadata used to pre-populate purchase entries."""
        # Touch the product so invalid identifiers fail fast and future heuristics have context.
        self._get_product(instance_index, product_id)
        return PurchaseEntryDefaults(
            shipping_cost=0.0,
            tax_rate=0.0,
            on_sale=False,
            brand=None,
            package_size=None,
            package_price=None,
            package_quantity=None,
            currency="USD",
            conversion_rate=1.0,
        )

    def invalidate_inventory_caches(self, instance_index: str) -> None:
        """Invalidate cached stock artifacts so corrections are reflected on next read."""
        self.stock_cache.clear_cache(instance_index)
        self.stock_log_cache.clear_cache(instance_index)

    def refresh_inventory_caches(self, instance_index: str) -> None:
        """Refresh cached stock artifacts by fetching current data from Grocy."""
        entries = self.client.list_stock()
        self.stock_cache.save_stock(instance_index, entries)
        log_entries = self.client.list_stock_log()
        self.stock_log_cache.save_log(instance_index, log_entries)

    def force_refresh_inventory(self, instance_index: str) -> None:
        """Invalidate every cached artifact so the next read fetches from Grocy."""
        self.product_cache.clear_cache(instance_index)
        self._product_lookup.pop(instance_index, None)
        self.invalidate_inventory_caches(instance_index)
        self._product_groups_cache.clear_cache(instance_index)
        self._quantity_units_cache.clear_cache(instance_index)

    def _load_products(self, instance_index: str) -> list[GrocyProduct]:
        cached_products = self.product_cache.load_products(instance_index)
        if cached_products is not None:
            self._prime_product_lookup(instance_index, cached_products)
            return cached_products
        products = self.client.list_products()
        self.product_cache.save_products(instance_index, products)
        self._prime_product_lookup(instance_index, products)
        return products

    def _load_stock_log(self, instance_index: str) -> list[GrocyStockLogEntry]:
        cached_log = self.stock_log_cache.load_log(instance_index)
        if cached_log is not None:
            return cached_log
        entries = self.client.list_stock_log()
        self.stock_log_cache.save_log(instance_index, entries)
        return entries

    def _load_stock_entries(self, instance_index: str) -> list[GrocyStockEntry]:
        cached_stock = self.stock_cache.load_stock(instance_index)
        if cached_stock is not None:
            return cached_stock
        entries = self.client.list_stock()
        self.stock_cache.save_stock(instance_index, entries)
        return entries

    def _get_product(self, instance_index: str, product_id: int) -> GrocyProduct:
        lookup = self._product_lookup_for_instance(instance_index)
        product = lookup.get(product_id)
        if product is not None:
            return product
        raise ValueError(f"Product id {product_id} is not available for instance {instance_index}")

    def _product_lookup_for_instance(self, instance_index: str) -> dict[int, GrocyProduct]:
        lookup = self._product_lookup.get(instance_index)
        if lookup is None:
            products = self._load_products(instance_index)
            lookup = self._product_lookup.get(instance_index)
            if lookup is None:
                lookup = {product.id: product for product in products}
                self._product_lookup[instance_index] = lookup
        return lookup

    def _prime_product_lookup(self, instance_index: str, products: list[GrocyProduct]) -> None:
        self._product_lookup[instance_index] = {product.id: product for product in products}

    def _build_inventory_context(self, instance_index: str) -> InventoryContext:
        """Load shared product-group and quantity-unit data for inventory views."""
        groups = self._load_product_groups(instance_index)
        units = self._load_quantity_units(instance_index)
        unit_names_map = _map_unit_names(units)
        return InventoryContext(
            groups_by_id={group.id: group.name for group in groups},
            unit_names=unit_names_map,
            discrete_units=_map_discrete_units(units),
            unit_name_lookup=_build_unit_name_lookup(unit_names_map),
        )

    def _load_product_groups(self, instance_index: str) -> list[GrocyProductGroup]:
        cached = self._product_groups_cache.load_groups(instance_index)
        if cached is not None:
            return cached
        groups = self.client.list_product_groups()
        self._product_groups_cache.save_groups(instance_index, groups)
        return groups

    def _load_quantity_units(self, instance_index: str) -> list[GrocyQuantityUnit]:
        cached = self._quantity_units_cache.load_units(instance_index)
        if cached is not None:
            return cached
        units = self.client.list_quantity_units()
        self._quantity_units_cache.save_units(instance_index, units)
        return units

    def _current_stock_amount(self, product_id: int) -> float:
        """Return the total quantity currently recorded for a product."""
        entries = self.client.list_product_stock_entries(product_id)
        total = 0.0
        for entry in entries:
            total += entry.amount
        return total

    def _create_inventory_view(
        self,
        product: GrocyProduct,
        entries: list[GrocyStockEntry],
        groups_by_id: dict[int, str],
        unit_names: dict[int, str],
        discrete_units: dict[str, bool],
        unit_name_lookup: dict[str, str],
        fallback_timestamp: datetime,
        last_updated_override: datetime | None = None,
    ) -> ProductInventoryView:
        last_updated = last_updated_override or _latest_entry_timestamp(entries, fallback_timestamp)
        return ProductInventoryView(
            product=product,
            last_updated_at=last_updated,
            product_group_name=groups_by_id.get(product.product_group_id),
            purchase_unit_name=_resolve_unit_name(product.qu_id_purchase, unit_names),
            stock_unit_name=_resolve_unit_name(product.qu_id_stock, unit_names),
            consume_unit_name=_resolve_unit_name(product.qu_id_consume, unit_names),
            price_unit_name=_resolve_unit_name(product.qu_id_price, unit_names),
            unit_name_lookup=unit_name_lookup,
            discrete_units=discrete_units,
            stocks=entries,
        )

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


def _latest_entry_timestamp(entries: list[GrocyStockEntry], fallback: datetime) -> datetime:
    latest = fallback
    for entry in entries:
        if entry.row_created_timestamp > latest:
            latest = entry.row_created_timestamp
    return latest


def _group_stock_entries(entries: list[GrocyStockEntry]) -> dict[int, list[GrocyStockEntry]]:
    grouped: dict[int, list[GrocyStockEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.product_id, []).append(entry)
    return grouped


def _map_unit_names(units: list[GrocyQuantityUnit]) -> dict[int, str]:
    return {unit.id: unit.name for unit in units}


def _map_discrete_units(units: list[GrocyQuantityUnit]) -> dict[str, bool]:
    mapping: dict[str, bool] = {}
    for unit in units:
        if unit.is_discrete is None:
            continue
        normalized = unit.name.strip().lower()
        if not normalized:
            continue
        mapping[normalized] = unit.is_discrete
    return mapping


def _build_unit_name_lookup(unit_names: dict[int, str]) -> dict[str, str]:
    """Create a lookup table of normalized unit names to their canonical display form."""
    lookup: dict[str, str] = {}
    for name in unit_names.values():
        if not name:
            continue
        normalized = name.strip().lower()
        if not normalized:
            continue
        lookup.setdefault(normalized, name)
    return lookup


def _resolve_unit_name(unit_id: int | None, names_by_id: dict[int, str]) -> str | None:
    if unit_id is None:
        return None
    return names_by_id.get(unit_id)


def _default_best_before_date(product: GrocyProduct) -> date | None:
    days = product.default_best_before_days
    if days <= 0:
        return None
    return date.today() + timedelta(days=days)


def _round_price(value: float) -> float:
    quantized = Decimal(value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return float(quantized)

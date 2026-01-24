from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from core.grocy.responses import GrocyQuantityUnit, GrocyStockEntry, GrocyStockLogEntry


def map_last_update(stock_log_entries: list[GrocyStockLogEntry]) -> dict[int, datetime]:
    """Determine the most recent stock log timestamp per product id."""
    last_update: dict[int, datetime] = {}
    for entry in stock_log_entries:
        product_id = entry.product_id
        timestamp = entry.row_created_timestamp
        current = last_update.get(product_id)
        if current is None or timestamp > current:
            last_update[product_id] = timestamp
    return last_update


def latest_entry_timestamp(
    entries: list[GrocyStockEntry], fallback: datetime
) -> datetime:
    latest = fallback
    for entry in entries:
        if entry.row_created_timestamp > latest:
            latest = entry.row_created_timestamp
    return latest


def group_stock_entries(
    entries: list[GrocyStockEntry],
) -> dict[int, list[GrocyStockEntry]]:
    grouped: dict[int, list[GrocyStockEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.product_id, []).append(entry)
    return grouped


def map_unit_names(units: list[GrocyQuantityUnit]) -> dict[int, str]:
    return {unit.id: unit.name for unit in units}


def map_discrete_units(units: list[GrocyQuantityUnit]) -> dict[str, bool]:
    mapping: dict[str, bool] = {}
    for unit in units:
        if unit.is_discrete is None:
            continue
        normalized = unit.name.strip().lower()
        if not normalized:
            continue
        mapping[normalized] = unit.is_discrete
    return mapping


def build_unit_name_lookup(unit_names: dict[int, str]) -> dict[str, str]:
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


def resolve_unit_name(unit_id: int | None, names_by_id: dict[int, str]) -> str | None:
    if unit_id is None:
        return None
    return names_by_id.get(unit_id)


def default_best_before_date(product) -> date | None:
    days = product.default_best_before_days
    if days <= 0:
        return None
    return date.today() + timedelta(days=days)


def round_price(value: float) -> float:
    quantized = Decimal(value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return float(quantized)

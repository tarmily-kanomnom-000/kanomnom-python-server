from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, tzinfo
from typing import Any

from core.grocy.note_metadata import (
    ProductGroupDescriptionMetadata,
    QuantityUnitDescriptionMetadata,
    decode_structured_note,
)

class GrocyResponseError(ValueError):
    """Raised when Grocy responses cannot be parsed into strongly typed models."""


def _require_int(raw: Any, field: str) -> int:
    if isinstance(raw, bool):
        raise GrocyResponseError(f"Expected integer for '{field}', received boolean")
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise GrocyResponseError(f"Expected integer for '{field}', received {raw!r}") from exc


def _optional_int(raw: Any, field: str) -> int | None:
    if raw is None:
        return None
    return _require_int(raw, field)


def _require_float(raw: Any, field: str) -> float:
    if isinstance(raw, bool):
        raise GrocyResponseError(f"Expected float for '{field}', received boolean")
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise GrocyResponseError(f"Expected float for '{field}', received {raw!r}") from exc


def _optional_float(raw: Any, field: str) -> float | None:
    if raw is None:
        return None
    return _require_float(raw, field)


def _require_bool(raw: Any, field: str) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)) and raw in (0, 1):
        return bool(raw)
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if normalized in {"1", "true"}:
            return True
        if normalized in {"0", "false"}:
            return False
    raise GrocyResponseError(f"Expected boolean-indicative value for '{field}', received {raw!r}")


def _optional_bool(raw: Any, field: str) -> bool | None:
    if raw is None:
        return None
    return _require_bool(raw, field)


def _require_str(raw: Any, field: str) -> str:
    if raw is None:
        raise GrocyResponseError(f"Expected string for '{field}', received None")
    value = str(raw).strip()
    if not value:
        raise GrocyResponseError(f"Expected non-empty string for '{field}', received {raw!r}")
    return value


def _optional_str(raw: Any) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    return value if value else None


def _require_timestamp(raw: Any, field: str, source_timezone: tzinfo | None) -> datetime:
    if raw is None:
        raise GrocyResponseError(f"Expected timestamp for '{field}', received None")
    cleaned = str(raw).strip().replace(" ", "T")
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise GrocyResponseError(f"Invalid timestamp for '{field}': {raw!r}") from exc
    if parsed.tzinfo is None:
        localized = parsed.replace(tzinfo=source_timezone or timezone.utc)
    else:
        localized = parsed
    return localized.astimezone(timezone.utc)


def _optional_timestamp(raw: Any, field: str, source_timezone: tzinfo | None) -> datetime | None:
    if raw is None:
        return None
    return _require_timestamp(raw, field, source_timezone)


@dataclass(frozen=True)
class GrocyProduct:
    id: int
    name: str
    description: str | None
    product_group_id: int | None
    active: bool
    location_id: int | None
    shopping_location_id: int | None
    qu_id_purchase: int | None
    qu_id_stock: int | None
    min_stock_amount: float
    default_best_before_days: int
    default_best_before_days_after_open: int
    default_best_before_days_after_freezing: int
    default_best_before_days_after_thawing: int
    picture_file_name: str | None
    enable_tare_weight_handling: bool
    tare_weight: float
    not_check_stock_fulfillment_for_recipes: bool
    parent_product_id: int | None
    calories: float
    cumulate_min_stock_amount_of_sub_products: bool
    due_type: int | None
    quick_consume_amount: float
    hide_on_stock_overview: bool
    default_stock_label_type: int | None
    should_not_be_frozen: bool
    treat_opened_as_out_of_stock: bool
    no_own_stock: bool
    default_consume_location_id: int | None
    move_on_open: bool
    row_created_timestamp: datetime
    qu_id_consume: int | None
    auto_reprint_stock_label: bool
    quick_open_amount: float
    qu_id_price: int | None
    disable_open: bool
    default_purchase_price_type: int | None

    @staticmethod
    def from_dict(raw: dict[str, Any], source_timezone: tzinfo | None) -> "GrocyProduct":
        return GrocyProduct(
            id=_require_int(raw.get("id"), "id"),
            name=_require_str(raw.get("name"), "name"),
            description=_optional_str(raw.get("description")),
            product_group_id=_optional_int(raw.get("product_group_id"), "product_group_id"),
            active=_require_bool(raw.get("active"), "active"),
            location_id=_optional_int(raw.get("location_id"), "location_id"),
            shopping_location_id=_optional_int(raw.get("shopping_location_id"), "shopping_location_id"),
            qu_id_purchase=_optional_int(raw.get("qu_id_purchase"), "qu_id_purchase"),
            qu_id_stock=_optional_int(raw.get("qu_id_stock"), "qu_id_stock"),
            min_stock_amount=_require_float(raw.get("min_stock_amount"), "min_stock_amount"),
            default_best_before_days=_require_int(raw.get("default_best_before_days"), "default_best_before_days"),
            default_best_before_days_after_open=_require_int(
                raw.get("default_best_before_days_after_open"), "default_best_before_days_after_open"
            ),
            default_best_before_days_after_freezing=_require_int(
                raw.get("default_best_before_days_after_freezing"), "default_best_before_days_after_freezing"
            ),
            default_best_before_days_after_thawing=_require_int(
                raw.get("default_best_before_days_after_thawing"), "default_best_before_days_after_thawing"
            ),
            picture_file_name=_optional_str(raw.get("picture_file_name")),
            enable_tare_weight_handling=_require_bool(raw.get("enable_tare_weight_handling"), "enable_tare_weight_handling"),
            tare_weight=_require_float(raw.get("tare_weight"), "tare_weight"),
            not_check_stock_fulfillment_for_recipes=_require_bool(
                raw.get("not_check_stock_fulfillment_for_recipes"), "not_check_stock_fulfillment_for_recipes"
            ),
            parent_product_id=_optional_int(raw.get("parent_product_id"), "parent_product_id"),
            calories=_require_float(raw.get("calories"), "calories"),
            cumulate_min_stock_amount_of_sub_products=_require_bool(
                raw.get("cumulate_min_stock_amount_of_sub_products"), "cumulate_min_stock_amount_of_sub_products"
            ),
            due_type=_optional_int(raw.get("due_type"), "due_type"),
            quick_consume_amount=_require_float(raw.get("quick_consume_amount"), "quick_consume_amount"),
            hide_on_stock_overview=_require_bool(raw.get("hide_on_stock_overview"), "hide_on_stock_overview"),
            default_stock_label_type=_optional_int(raw.get("default_stock_label_type"), "default_stock_label_type"),
            should_not_be_frozen=_require_bool(raw.get("should_not_be_frozen"), "should_not_be_frozen"),
            treat_opened_as_out_of_stock=_require_bool(raw.get("treat_opened_as_out_of_stock"), "treat_opened_as_out_of_stock"),
            no_own_stock=_require_bool(raw.get("no_own_stock"), "no_own_stock"),
            default_consume_location_id=_optional_int(raw.get("default_consume_location_id"), "default_consume_location_id"),
            move_on_open=_require_bool(raw.get("move_on_open"), "move_on_open"),
            row_created_timestamp=_require_timestamp(
                raw.get("row_created_timestamp"), "row_created_timestamp", source_timezone
            ),
            qu_id_consume=_optional_int(raw.get("qu_id_consume"), "qu_id_consume"),
            auto_reprint_stock_label=_require_bool(raw.get("auto_reprint_stock_label"), "auto_reprint_stock_label"),
            quick_open_amount=_require_float(raw.get("quick_open_amount"), "quick_open_amount"),
            qu_id_price=_optional_int(raw.get("qu_id_price"), "qu_id_price"),
            disable_open=_require_bool(raw.get("disable_open"), "disable_open"),
            default_purchase_price_type=_optional_int(raw.get("default_purchase_price_type"), "default_purchase_price_type"),
        )


@dataclass(frozen=True)
class GrocyStockEntry:
    id: int
    product_id: int
    amount: float
    best_before_date: datetime | None
    purchased_date: datetime | None
    stock_id: str | None
    price: float | None
    open: bool
    opened_date: datetime | None
    row_created_timestamp: datetime
    location_id: int | None
    shopping_location_id: int | None
    note: str | None

    @staticmethod
    def from_dict(raw: dict[str, Any], source_timezone: tzinfo | None) -> "GrocyStockEntry":
        return GrocyStockEntry(
            id=_require_int(raw.get("id"), "id"),
            product_id=_require_int(raw.get("product_id"), "product_id"),
            amount=_require_float(raw.get("amount"), "amount"),
            best_before_date=_optional_timestamp(raw.get("best_before_date"), "best_before_date", source_timezone),
            purchased_date=_optional_timestamp(raw.get("purchased_date"), "purchased_date", source_timezone),
            stock_id=_optional_str(raw.get("stock_id")),
            price=_optional_float(raw.get("price"), "price"),
            open=_require_bool(raw.get("open"), "open"),
            opened_date=_optional_timestamp(raw.get("opened_date"), "opened_date", source_timezone),
            row_created_timestamp=_require_timestamp(
                raw.get("row_created_timestamp"), "row_created_timestamp", source_timezone
            ),
            location_id=_optional_int(raw.get("location_id"), "location_id"),
            shopping_location_id=_optional_int(raw.get("shopping_location_id"), "shopping_location_id"),
            note=_optional_str(raw.get("note")),
        )


@dataclass(frozen=True)
class GrocyStockLogEntry:
    id: int
    product_id: int
    amount: float
    best_before_date: datetime | None
    purchased_date: datetime | None
    used_date: datetime | None
    spoiled: bool
    stock_id: str | None
    transaction_type: str | None
    price: float | None
    undone: bool
    undone_timestamp: datetime | None
    opened_date: datetime | None
    location_id: int | None
    recipe_id: int | None
    correlation_id: str | None
    transaction_id: str | None
    stock_row_id: str | None
    shopping_location_id: int | None
    user_id: int | None
    row_created_timestamp: datetime
    note: str | None

    @staticmethod
    def from_dict(raw: dict[str, Any], source_timezone: tzinfo | None) -> "GrocyStockLogEntry":
        return GrocyStockLogEntry(
            id=_require_int(raw.get("id"), "id"),
            product_id=_require_int(raw.get("product_id"), "product_id"),
            amount=_require_float(raw.get("amount"), "amount"),
            best_before_date=_optional_timestamp(raw.get("best_before_date"), "best_before_date", source_timezone),
            purchased_date=_optional_timestamp(raw.get("purchased_date"), "purchased_date", source_timezone),
            used_date=_optional_timestamp(raw.get("used_date"), "used_date", source_timezone),
            spoiled=_require_bool(raw.get("spoiled"), "spoiled"),
            stock_id=_optional_str(raw.get("stock_id")),
            transaction_type=_optional_str(raw.get("transaction_type")),
            price=_optional_float(raw.get("price"), "price"),
            undone=_require_bool(raw.get("undone"), "undone"),
            undone_timestamp=_optional_timestamp(raw.get("undone_timestamp"), "undone_timestamp", source_timezone),
            opened_date=_optional_timestamp(raw.get("opened_date"), "opened_date", source_timezone),
            location_id=_optional_int(raw.get("location_id"), "location_id"),
            recipe_id=_optional_int(raw.get("recipe_id"), "recipe_id"),
            correlation_id=_optional_str(raw.get("correlation_id")),
            transaction_id=_optional_str(raw.get("transaction_id")),
            stock_row_id=_optional_str(raw.get("stock_row_id")),
            shopping_location_id=_optional_int(raw.get("shopping_location_id"), "shopping_location_id"),
            user_id=_optional_int(raw.get("user_id"), "user_id"),
            row_created_timestamp=_require_timestamp(
                raw.get("row_created_timestamp"), "row_created_timestamp", source_timezone
            ),
            note=_optional_str(raw.get("note")),
        )


@dataclass(frozen=True)
class GrocyQuantityUnit:
    id: int
    name: str
    description: str | None
    name_plural: str | None
    plural_forms: str | None
    active: bool
    is_discrete: bool | None = None

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> "GrocyQuantityUnit":
        description = _optional_str(raw.get("description"))
        is_discrete: bool | None = None
        if description:
            decoded_description = decode_structured_note(description)
            description = decoded_description.note or None
            metadata = decoded_description.metadata
            if isinstance(metadata, QuantityUnitDescriptionMetadata):
                is_discrete = metadata.is_discrete
        return GrocyQuantityUnit(
            id=_require_int(raw.get("id"), "id"),
            name=_require_str(raw.get("name"), "name"),
            description=description,
            name_plural=_optional_str(raw.get("name_plural")),
            plural_forms=_optional_str(raw.get("plural_forms")),
            active=_require_bool(raw.get("active"), "active"),
            is_discrete=is_discrete,
        )


def _parse_collection(raw: Any, entity: str) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise GrocyResponseError(f"Expected list response for '{entity}', received {type(raw).__name__}")
    parsed: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise GrocyResponseError(f"Expected dict entries for '{entity}' at index {index}, received {type(item).__name__}")
        parsed.append(item)
    return parsed


def parse_products(raw: Any, source_timezone: tzinfo | None) -> list[GrocyProduct]:
    return [GrocyProduct.from_dict(entry, source_timezone) for entry in _parse_collection(raw, "products")]


def parse_stock_entries(raw: Any, source_timezone: tzinfo | None) -> list[GrocyStockEntry]:
    return [GrocyStockEntry.from_dict(entry, source_timezone) for entry in _parse_collection(raw, "stock")]


def parse_stock_log_entries(raw: Any, source_timezone: tzinfo | None) -> list[GrocyStockLogEntry]:
    return [GrocyStockLogEntry.from_dict(entry, source_timezone) for entry in _parse_collection(raw, "stock_log")]


def parse_quantity_units(raw: Any) -> list[GrocyQuantityUnit]:
    return [GrocyQuantityUnit.from_dict(entry) for entry in _parse_collection(raw, "quantity_units")]


def parse_product_stock_entries(raw: Any, source_timezone: tzinfo | None) -> list[GrocyStockEntry]:
    if not isinstance(raw, list):
        raise GrocyResponseError("Expected list of product stock entries")
    return [GrocyStockEntry.from_dict(entry, source_timezone) for entry in raw]


@dataclass(frozen=True)
class GrocyLocation:
    id: int
    name: str
    description: str | None
    row_created_timestamp: datetime
    is_freezer: bool
    active: bool

    @staticmethod
    def from_dict(raw: dict[str, Any], source_timezone: tzinfo | None) -> "GrocyLocation":
        return GrocyLocation(
            id=_require_int(raw.get("id"), "id"),
            name=_require_str(raw.get("name"), "name"),
            description=_optional_str(raw.get("description")),
            row_created_timestamp=_require_timestamp(
                raw.get("row_created_timestamp"), "row_created_timestamp", source_timezone
            ),
            is_freezer=_require_bool(raw.get("is_freezer"), "is_freezer"),
            active=_require_bool(raw.get("active"), "active"),
        )


def parse_locations(raw: Any, source_timezone: tzinfo | None) -> list[GrocyLocation]:
    return [GrocyLocation.from_dict(entry, source_timezone) for entry in _parse_collection(raw, "locations")]


@dataclass(frozen=True)
class GrocyShoppingLocation:
    id: int
    name: str
    description: str | None
    row_created_timestamp: datetime
    active: bool

    @staticmethod
    def from_dict(raw: dict[str, Any], source_timezone: tzinfo | None) -> "GrocyShoppingLocation":
        return GrocyShoppingLocation(
            id=_require_int(raw.get("id"), "id"),
            name=_require_str(raw.get("name"), "name"),
            description=_optional_str(raw.get("description")),
            row_created_timestamp=_require_timestamp(
                raw.get("row_created_timestamp"), "row_created_timestamp", source_timezone
            ),
            active=_require_bool(raw.get("active"), "active"),
        )


def parse_shopping_locations(raw: Any, source_timezone: tzinfo | None) -> list[GrocyShoppingLocation]:
    return [GrocyShoppingLocation.from_dict(entry, source_timezone) for entry in _parse_collection(raw, "shopping_locations")]


@dataclass(frozen=True)
class GrocyProductGroup:
    id: int
    name: str
    description: str | None
    row_created_timestamp: datetime
    active: bool
    allergens: tuple[str, ...] = ()

    @staticmethod
    def from_dict(raw: dict[str, Any], source_timezone: tzinfo | None) -> "GrocyProductGroup":
        description = _optional_str(raw.get("description"))
        allergens: tuple[str, ...] = ()
        if description:
            decoded_description = decode_structured_note(description)
            description = decoded_description.note or None
            metadata = decoded_description.metadata
            if isinstance(metadata, ProductGroupDescriptionMetadata):
                allergens = metadata.allergens
        return GrocyProductGroup(
            id=_require_int(raw.get("id"), "id"),
            name=_require_str(raw.get("name"), "name"),
            description=description,
            row_created_timestamp=_require_timestamp(
                raw.get("row_created_timestamp"), "row_created_timestamp", source_timezone
            ),
            active=_require_bool(raw.get("active"), "active"),
            allergens=allergens,
        )


def parse_product_groups(raw: Any, source_timezone: tzinfo | None) -> list[GrocyProductGroup]:
    return [GrocyProductGroup.from_dict(entry, source_timezone) for entry in _parse_collection(raw, "product_groups")]


__all__ = [
    "GrocyProduct",
    "GrocyStockEntry",
    "GrocyStockLogEntry",
    "GrocyQuantityUnit",
    "GrocyShoppingLocation",
    "GrocyProductGroup",
    "GrocyLocation",
    "parse_products",
    "parse_stock_entries",
    "parse_stock_log_entries",
    "parse_quantity_units",
    "parse_product_groups",
    "parse_shopping_locations",
    "parse_locations",
    "parse_product_stock_entries",
]

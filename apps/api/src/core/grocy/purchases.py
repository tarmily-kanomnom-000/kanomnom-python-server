from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from core.grocy.note_metadata import PurchaseEntryNoteMetadata, encode_structured_note
from core.grocy.responses import GrocyProduct

from .stock_helpers import default_best_before_date, round_price


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


def resolve_purchase_entry(
    product: GrocyProduct, entry: PurchaseEntryDraft, current_stock_amount: float
) -> PurchaseEntry:
    tare_weight = (
        product.tare_weight
        if product.enable_tare_weight_handling and product.tare_weight > 0
        else 0
    )
    if tare_weight > 0:
        amount = entry.amount + current_stock_amount + tare_weight
    else:
        amount = entry.amount
    best_before_date = entry.best_before_date
    if best_before_date is None:
        best_before_date = default_best_before_date(product)
    purchased_date = entry.purchased_date or date.today()
    location_id = (
        entry.location_id if entry.location_id is not None else product.location_id
    )
    shopping_location_id = (
        entry.shopping_location_id
        if entry.shopping_location_id is not None
        else product.shopping_location_id
    )
    rounded_price = round_price(entry.price_per_unit)
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


def build_purchase_defaults(product: GrocyProduct) -> PurchaseEntryDefaults:
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

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, time
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from core.grocy.exceptions import ManifestNotFoundError, MetadataNotFoundError
from core.grocy.note_metadata import (
    PurchaseEntryNoteMetadata,
    decode_structured_note,
    validate_note_text,
)
from core.grocy.responses import GrocyStockEntry
from core.grocy.stock import PurchaseEntry, PurchaseEntryDraft
from models.grocy import (
    GrocyProductInventoryEntry,
    GrocyStockEntryPayload,
    PurchaseEntryCalculationRequest,
    PurchaseEntryCalculationResponse,
    PurchaseEntryDefaultsBatchRequest,
    PurchaseEntryDefaultsBatchResponse,
    PurchaseEntryDefaultsResponse,
    PurchaseEntryMetadataPayload,
    PurchaseEntryRequest,
)
from shared.grist_service import create_grist_purchase_record

from .dependencies import governor, router
from .helpers import execute_product_mutation, serialize_inventory_view

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PurchaseDefaultsQuery:
    shopping_location_id: int | None


def _parse_purchase_defaults_query(request: Request) -> PurchaseDefaultsQuery:
    raw_value = request.query_params.get("shopping_location_id")
    if raw_value is None:
        return PurchaseDefaultsQuery(shopping_location_id=None)
    trimmed = raw_value.strip()
    if not trimmed:
        return PurchaseDefaultsQuery(shopping_location_id=None)
    try:
        return PurchaseDefaultsQuery(shopping_location_id=int(trimmed))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="shopping_location_id must be an integer.") from exc


def _schema_root() -> Path:
    return Path(__file__).resolve().parents[6] / "schemas"


def _load_shared_purchase_schema() -> dict[str, Any]:
    schema_path = _schema_root() / "purchase-entry-request.schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Missing shared purchase entry schema: {schema_path}")
    with schema_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _ensure_schema_alignment(schema: dict[str, Any]) -> None:
    model_schema = PurchaseEntryRequest.model_json_schema()
    model_properties = set(model_schema.get("properties", {}).keys())
    shared_properties = set(schema.get("properties", {}).keys())
    if model_properties != shared_properties:
        raise RuntimeError("Shared purchase entry schema properties do not match PurchaseEntryRequest definition.")


def _resolve_package_batch(metadata: PurchaseEntryNoteMetadata | None) -> tuple[int, float] | None:
    if metadata is None:
        return None
    if metadata.package_quantity is None or metadata.package_size is None:
        return None
    quantity = metadata.package_quantity
    # Only split into discrete packages when the quantity is a whole number; otherwise treat as a single entry.
    if float(quantity).is_integer():
        count = int(quantity)
        if count < 1:
            raise ValueError("package_quantity must be at least 1.")
        return count, metadata.package_size
    return None


def _serialize_stock_entries(entries: list[GrocyStockEntry]) -> list[GrocyStockEntryPayload]:
    serialized: list[GrocyStockEntryPayload] = []
    for entry in entries:
        decoded_note = decode_structured_note(entry.note)
        payload: dict[str, Any] = {
            "id": entry.id,
            "amount": entry.amount,
            "best_before_date": entry.best_before_date,
            "purchased_date": entry.purchased_date,
            "stock_id": entry.stock_id,
            "price": entry.price,
            "open": entry.open,
            "opened_date": entry.opened_date,
            "row_created_timestamp": entry.row_created_timestamp,
            "location_id": entry.location_id,
            "shopping_location_id": entry.shopping_location_id,
            "note": decoded_note.note or None,
        }
        if decoded_note.metadata is not None:
            payload["note_metadata"] = decoded_note.metadata.to_api_payload()
        serialized.append(GrocyStockEntryPayload(**payload))
    return serialized


def _build_purchase_drafts(
    purchase: PurchaseEntryRequest,
    metadata: PurchaseEntryNoteMetadata | None,
    resolved_amount: float,
    resolved_price: float,
    shopping_location_id: int | None,
) -> list[PurchaseEntryDraft]:
    package_batch = _resolve_package_batch(metadata)
    if package_batch is None:
        entry_amount = resolved_amount
        entry_count = 1
    else:
        entry_count, package_size = package_batch
        entry_amount = package_size
    drafts: list[PurchaseEntryDraft] = []
    base_note = (purchase.note or "").strip()
    for index in range(entry_count):
        tag = f"(package {index + 1}/{entry_count})" if entry_count > 1 else ""
        resolved_note = base_note
        if tag:
            resolved_note = f"{base_note} {tag}".strip() if base_note else tag
        drafts.append(
            PurchaseEntryDraft(
                amount=entry_amount,
                price_per_unit=resolved_price,
                best_before_date=purchase.best_before_date,
                purchased_date=purchase.purchased_date,
                location_id=purchase.location_id,
                shopping_location_id=shopping_location_id,
                note=resolved_note,
                metadata=metadata,
            )
        )
    return drafts


_PURCHASE_ENTRY_SCHEMA = _load_shared_purchase_schema()
_ensure_schema_alignment(_PURCHASE_ENTRY_SCHEMA)


@router.get(
    "/{instance_index}/products/{product_id}/purchase/defaults",
    response_model=PurchaseEntryDefaultsResponse,
)
async def get_purchase_entry_defaults(
    instance_index: str,
    product_id: int,
    request: Request,
) -> PurchaseEntryDefaultsResponse:
    """Return default metadata suggestions for purchase entries."""
    query = _parse_purchase_defaults_query(request)

    def _load_defaults():
        manager = governor.manager_for(instance_index)
        return manager.get_purchase_entry_defaults(product_id, query.shopping_location_id)

    try:
        defaults = await run_in_threadpool(_load_defaults)
    except MetadataNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    metadata_payload = PurchaseEntryMetadataPayload(
        shipping_cost=defaults.shipping_cost,
        tax_rate=defaults.tax_rate,
        brand=defaults.brand,
        package_size=defaults.package_size,
        package_price=defaults.package_price,
        package_quantity=defaults.package_quantity,
        currency=defaults.currency,
        conversion_rate=defaults.conversion_rate,
        on_sale=defaults.on_sale,
    )
    return PurchaseEntryDefaultsResponse(
        product_id=product_id,
        shopping_location_id=query.shopping_location_id,
        metadata=metadata_payload,
    )


@router.post(
    "/{instance_index}/purchases/defaults",
    response_model=PurchaseEntryDefaultsBatchResponse,
)
async def get_purchase_entry_defaults_batch(
    instance_index: str,
    payload: PurchaseEntryDefaultsBatchRequest,
) -> PurchaseEntryDefaultsBatchResponse:
    """Return default metadata suggestions for multiple products."""
    if not payload.product_ids:
        raise HTTPException(status_code=400, detail="product_ids must include at least one entry.")

    def _load_defaults():
        manager = governor.manager_for(instance_index)
        return manager.get_purchase_entry_defaults_batch(payload.product_ids, payload.shopping_location_id)

    try:
        defaults = await run_in_threadpool(_load_defaults)
    except MetadataNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    # Future extension: accept richer hints (e.g., prior brand or cost overrides)
    # so downstream heuristics can adjust defaults per context without new endpoints.
    if len(defaults) != len(payload.product_ids):
        raise HTTPException(
            status_code=500,
            detail=(
                "Purchase defaults response size mismatch; "
                f"expected {len(payload.product_ids)} entries but received {len(defaults)}."
            ),
        )

    shaped: list[PurchaseEntryDefaultsResponse] = []
    for index, product_id in enumerate(payload.product_ids):
        item = defaults[index]
        metadata_payload = PurchaseEntryMetadataPayload(
            shipping_cost=item.shipping_cost,
            tax_rate=item.tax_rate,
            brand=item.brand,
            package_size=item.package_size,
            package_price=item.package_price,
            package_quantity=item.package_quantity,
            currency=item.currency,
            conversion_rate=item.conversion_rate,
            on_sale=item.on_sale,
        )
        shaped.append(
            PurchaseEntryDefaultsResponse(
                product_id=product_id,
                shopping_location_id=payload.shopping_location_id,
                metadata=metadata_payload,
            )
        )

    return PurchaseEntryDefaultsBatchResponse(defaults=shaped)


@router.get("/purchases/schema")
async def get_purchase_entry_schema() -> dict[str, Any]:
    """Expose the shared JSON schema for purchase entry payloads."""
    return _PURCHASE_ENTRY_SCHEMA


@router.post(
    "/{instance_index}/products/{product_id}/purchase",
    response_model=list[GrocyStockEntryPayload],
)
async def record_purchase_entry(
    instance_index: str,
    product_id: int,
    purchase: PurchaseEntryRequest,
) -> list[GrocyStockEntryPayload]:
    """Record purchase entries for the specified product and return the new stock rows."""

    metadata: PurchaseEntryNoteMetadata | None = None
    derived_amount: float | None = None
    derived_unit_price: float | None = None
    try:
        if purchase.metadata is not None:
            candidate = PurchaseEntryNoteMetadata(
                shipping_cost=purchase.metadata.shipping_cost,
                tax_rate=purchase.metadata.tax_rate,
                brand=purchase.metadata.brand,
                package_size=purchase.metadata.package_size,
                package_price=purchase.metadata.package_price,
                package_quantity=purchase.metadata.package_quantity,
                currency=purchase.metadata.currency,
                conversion_rate=purchase.metadata.conversion_rate,
                on_sale=purchase.metadata.on_sale,
            )
            derived_amount, derived_unit_price, _ = _derive_purchase_amount_and_price(candidate)
            if candidate.to_attrs():
                metadata = candidate
            logger.info(
                "Purchase metadata received: product_id=%s raw_on_sale=%s normalized_on_sale=%s",
                product_id,
                purchase.metadata.on_sale,
                metadata.on_sale if metadata else None,
            )
        validate_note_text(purchase.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    resolved_amount = derived_amount if derived_amount is not None else purchase.amount
    resolved_price = derived_unit_price if derived_unit_price is not None else purchase.price
    if resolved_amount is None or resolved_price is None:
        raise HTTPException(status_code=400, detail="amount and price must be provided or derivable from metadata.")

    shopping_location_id = await _ensure_shopping_location_id(instance_index, purchase)

    try:
        drafts = _build_purchase_drafts(purchase, metadata, resolved_amount, resolved_price, shopping_location_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    recorded_entries: list[PurchaseEntry] = []
    baseline_entry_ids: set[int] = set()

    def _record_purchase(manager, payloads: list[PurchaseEntryDraft]) -> None:
        nonlocal baseline_entry_ids
        baseline_view = manager.get_product_inventory(product_id)
        baseline_entry_ids = {entry.id for entry in baseline_view.stocks}
        for payload in payloads:
            resolved_entry, _ = manager.record_purchase_entry(product_id, payload)
            recorded_entries.append(resolved_entry)

    updated_product = await execute_product_mutation(instance_index, product_id, _record_purchase, drafts)

    if not recorded_entries:
        raise HTTPException(status_code=500, detail="Failed to persist purchase entries.")

    expected_entries = len(drafts)
    new_entries = [entry for entry in updated_product.stocks if entry.id not in baseline_entry_ids]
    new_entries.sort(key=lambda entry: entry.row_created_timestamp)
    if len(new_entries) < expected_entries:
        logger.warning(
            "Purchase entry count mismatch; expected %s new entries but found %s. Falling back to latest entries.",
            expected_entries,
            len(new_entries),
        )
        newest = sorted(updated_product.stocks, key=lambda entry: entry.row_created_timestamp)
        new_entries = newest[-expected_entries:]
    if len(new_entries) > expected_entries:
        new_entries = new_entries[-expected_entries:]

    purchase_epoch = _compose_purchase_timestamp(recorded_entries[0].purchased_date, instance_index)
    shopping_location_name = await _resolve_shopping_location_name(instance_index, recorded_entries[0].shopping_location_id)
    serialized_product = serialize_inventory_view(updated_product)
    grist_fields = _build_grist_record_fields(
        product=serialized_product,
        purchase=purchase,
        metadata=metadata,
        recorded_entry=recorded_entries[0],
        purchase_epoch=purchase_epoch,
        shopping_location_name=shopping_location_name,
    )
    logger.info(
        "Posting purchase to Grist: product=%s on_sale=%s",
        serialized_product.name,
        grist_fields.get("on_sale"),
    )
    try:
        await create_grist_purchase_record(grist_fields)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to post purchase '%s' to Grist", updated_product.product.name)

    return _serialize_stock_entries(new_entries)


@router.post(
    "/{instance_index}/products/{product_id}/purchase/derive",
    response_model=PurchaseEntryCalculationResponse,
)
async def derive_purchase_entry(
    instance_index: str,
    product_id: int,
    payload: PurchaseEntryCalculationRequest,
) -> PurchaseEntryCalculationResponse:
    """Return canonical derived amount and unit price for purchase metadata."""

    try:
        candidate = PurchaseEntryNoteMetadata(
            shipping_cost=payload.metadata.shipping_cost,
            tax_rate=payload.metadata.tax_rate,
            brand=payload.metadata.brand,
            package_size=payload.metadata.package_size,
            package_price=payload.metadata.package_price,
            package_quantity=payload.metadata.package_quantity,
            currency=payload.metadata.currency,
            conversion_rate=payload.metadata.conversion_rate,
            on_sale=payload.metadata.on_sale,
        )
        derived_amount, derived_unit_price, total_usd = _derive_purchase_amount_and_price(candidate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if derived_amount is None or derived_unit_price is None or total_usd is None:
        raise HTTPException(
            status_code=400,
            detail="Metadata must include package_size, package_quantity, package_price, and conversion_rate values.",
        )
    return PurchaseEntryCalculationResponse(amount=derived_amount, unit_price=derived_unit_price, total_usd=total_usd)


def _derive_purchase_amount_and_price(
    metadata: PurchaseEntryNoteMetadata | None,
) -> tuple[float | None, float | None, float | None]:
    if metadata is None:
        return None, None, None
    if (
        metadata.package_size is None
        or metadata.package_quantity is None
        or metadata.package_price is None
        or metadata.conversion_rate is None
    ):
        return None, None, None
    amount = metadata.package_size * metadata.package_quantity
    if amount <= 0:
        raise ValueError("package_size and quantity must produce a positive purchase amount.")
    shipping_cost = metadata.shipping_cost or 0.0
    tax_rate = metadata.tax_rate or 0.0
    subtotal = metadata.package_price * metadata.package_quantity + shipping_cost
    total_usd = subtotal * (1 + tax_rate) * metadata.conversion_rate
    if total_usd <= 0:
        raise ValueError("Conversion rate and pricing must produce a positive USD total.")
    unit_price = total_usd / amount
    return amount, unit_price, total_usd


def _resolve_product_unit_name(product: GrocyProductInventoryEntry) -> str | None:
    for candidate in (
        product.stock_quantity_unit_name,
        product.purchase_quantity_unit_name,
        product.consume_quantity_unit_name,
        product.price_quantity_unit_name,
    ):
        if candidate:
            return candidate
    return None


def _build_grist_record_fields(
    product: GrocyProductInventoryEntry,
    purchase: PurchaseEntryRequest,
    metadata: PurchaseEntryNoteMetadata | None,
    recorded_entry: PurchaseEntry,
    purchase_epoch: int,
    shopping_location_name: str | None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "product": product.name,
        "pruchase_date": purchase_epoch,
        "notes": (purchase.note or "").strip(),
    }
    fields["on_sale"] = False
    unit_name = _resolve_product_unit_name(product)
    if unit_name:
        fields["unit"] = unit_name
    if shopping_location_name:
        fields["vendor"] = shopping_location_name
    if product.product_group_name:
        fields["category"] = product.product_group_name

    # Grist computes totals via formula columns; avoid posting those fields to prevent write errors.
    if metadata is None:
        fields.setdefault("local_currency", "USD")
        return fields

    if metadata.package_size is not None:
        fields["package_size"] = metadata.package_size
    if metadata.package_quantity is not None:
        fields["quantity_purchased"] = metadata.package_quantity
    if metadata.package_price is not None:
        fields["purchase_price_per_package_local_currency"] = metadata.package_price
    if metadata.shipping_cost is not None:
        fields["shipping_fee_local_currency"] = metadata.shipping_cost
    if metadata.tax_rate is not None:
        fields["tax_rate"] = metadata.tax_rate
    if metadata.brand is not None:
        fields["brand"] = metadata.brand
    local_currency = (metadata.currency or "").strip().upper()
    if local_currency:
        fields["local_currency"] = local_currency
    else:
        fields.setdefault("local_currency", "USD")
    if metadata.conversion_rate is not None:
        fields["conversion_rate_to_USD_at_purchase_date"] = metadata.conversion_rate
    # Explicitly coerce to bool so we never leak None or non-boolean types into Grist.
    fields["on_sale"] = bool(metadata.on_sale)

    return fields


def _compose_purchase_timestamp(purchase_date: date, instance_index: str) -> int:
    timezone = _instance_timezone(instance_index)
    now = datetime.now(timezone)
    target_date = purchase_date or now.date()
    midnight = datetime.combine(target_date, time(0, tzinfo=timezone))
    return int(midnight.timestamp())


@lru_cache(maxsize=16)
def _instance_timezone(instance_index: str) -> ZoneInfo:
    metadata = None
    try:
        metadata = governor.metadata_repository.load(instance_index)
    except ManifestNotFoundError:
        logger.warning("No metadata found for Grocy instance %s when resolving timezone.", instance_index)
    tz_name = metadata.instance_timezone if metadata else None
    if tz_name:
        try:
            return ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            logger.warning("Unknown timezone '%s' for instance %s", tz_name, instance_index)
    local_tz = datetime.now().astimezone().tzinfo
    if isinstance(local_tz, ZoneInfo):
        return local_tz
    if local_tz:
        try:
            return ZoneInfo(str(local_tz))
        except Exception:  # noqa: BLE001
            pass
    return ZoneInfo("UTC")


async def _ensure_shopping_location_id(instance_index: str, purchase: PurchaseEntryRequest) -> int | None:
    if purchase.shopping_location_id is not None:
        return purchase.shopping_location_id

    raw_name = purchase.shopping_location_name
    if raw_name is None:
        return None
    normalized_name = raw_name.strip()
    if not normalized_name:
        return None

    def _resolve_or_create() -> int:
        manager = governor.manager_for(instance_index)
        return manager.ensure_shopping_location(normalized_name).id

    try:
        return await run_in_threadpool(_resolve_or_create)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        logger.exception("Failed to ensure shopping location for instance %s", instance_index)
        raise HTTPException(status_code=500, detail="Unable to resolve shopping location.") from error


async def _resolve_shopping_location_name(instance_index: str, shopping_location_id: int | None) -> str | None:
    if shopping_location_id is None:
        return None

    def _fetch_locations() -> dict[int, str]:
        manager = governor.manager_for(instance_index)
        return {location.id: location.name for location in manager.list_shopping_locations()}

    try:
        lookup = await run_in_threadpool(_fetch_locations)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to load shopping locations for instance %s", instance_index)
        return None
    return lookup.get(shopping_location_id)

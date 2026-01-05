from __future__ import annotations

from dataclasses import asdict
from typing import Callable

import requests
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from core.grocy.exceptions import MetadataNotFoundError
from core.grocy.note_metadata import (
    ProductDescriptionMetadata,
    ProductUnitConversion,
    decode_structured_note,
)
from core.grocy.inventory import ProductInventoryView
from models.grocy import GrocyProductInventoryEntry, GrocyStockEntryPayload

from .dependencies import governor


def serialize_inventory_view(view: ProductInventoryView) -> GrocyProductInventoryEntry:
    """Convert a ProductInventoryView into the API response model."""
    decoded_description = decode_structured_note(view.product.description)
    description_text = decoded_description.note or None
    description_metadata = None
    if decoded_description.metadata is not None:
        metadata = decoded_description.metadata
        if isinstance(metadata, ProductDescriptionMetadata):
            metadata = _sanitize_product_description_metadata(metadata, view.unit_name_lookup)
        payload = metadata.to_api_payload()
        description_metadata = payload or None
    product_dict = asdict(view.product)
    product_dict["description"] = description_text
    product_dict["description_metadata"] = description_metadata
    stocks: list[GrocyStockEntryPayload] = []
    for stock in view.stocks:
        decoded_note = decode_structured_note(stock.note)
        stock_dict = {key: value for key, value in asdict(stock).items() if key not in {"product_id", "note"}}
        stock_dict["note"] = decoded_note.note or None
        if decoded_note.metadata is not None:
            stock_dict["note_metadata"] = decoded_note.metadata.to_api_payload()
        stocks.append(GrocyStockEntryPayload(**stock_dict))

    return GrocyProductInventoryEntry(
        **product_dict,
        last_stock_updated_at=view.last_updated_at,
        product_group_name=view.product_group_name,
        purchase_quantity_unit_name=view.purchase_unit_name,
        stock_quantity_unit_name=view.stock_unit_name,
        consume_quantity_unit_name=view.consume_unit_name,
        price_quantity_unit_name=view.price_unit_name,
        stocks=stocks,
    )


def _sanitize_product_description_metadata(
    metadata: ProductDescriptionMetadata,
    unit_name_lookup: dict[str, str],
) -> ProductDescriptionMetadata:
    if not metadata.unit_conversions:
        return metadata
    if not unit_name_lookup:
        raise ValueError("Unable to validate unit conversions because Grocy quantity units are unavailable.")
    seen_pairs: set[tuple[str, str]] = set()
    sanitized: list[ProductUnitConversion] = []
    for conversion in metadata.unit_conversions:
        from_key = _normalize_unit_name(conversion.from_unit)
        to_key = _normalize_unit_name(conversion.to_unit)
        if not from_key or not to_key:
            raise ValueError("Unit conversions must include from_unit and to_unit names.")
        if from_key not in unit_name_lookup:
            raise ValueError(f"Unknown Grocy quantity unit '{conversion.from_unit}'.")
        if to_key not in unit_name_lookup:
            raise ValueError(f"Unknown Grocy quantity unit '{conversion.to_unit}'.")
        pair_key = tuple(sorted((from_key, to_key)))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        sanitized.append(
            ProductUnitConversion(
                from_unit=unit_name_lookup[from_key],
                to_unit=unit_name_lookup[to_key],
                factor=conversion.factor,
            )
        )
    return ProductDescriptionMetadata(unit_conversions=tuple(sanitized))


def _normalize_unit_name(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().lower()


async def execute_product_mutation(
    instance_index: str,
    product_id: int,
    mutate: Callable[..., None],
    *args: object,
    **kwargs: object,
) -> ProductInventoryView:
    """Run a Grocy mutation and return the refreshed product view."""

    def _apply_mutation() -> None:
        manager = governor.manager_for(instance_index)
        mutate(manager, *args, **kwargs)

    try:
        await run_in_threadpool(_apply_mutation)
        return await run_in_threadpool(lambda: governor.manager_for(instance_index).get_product_inventory(product_id))
    except MetadataNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except requests.HTTPError as error:  # pragma: no cover - passthrough to HTTP
        status_code = error.response.status_code if error.response else 502
        detail = error.response.text.strip() if error.response else str(error)
        raise HTTPException(status_code=status_code, detail=detail or str(error)) from error

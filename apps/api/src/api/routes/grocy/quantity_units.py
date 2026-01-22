from __future__ import annotations

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from core.grocy.exceptions import MetadataNotFoundError
from core.grocy.models import UniversalManifest
from core.grocy.unit_conversions import (
    build_conversion_graph,
    build_full_conversion_map,
    load_quantity_unit_conversions,
)
from models.grocy import (
    GrocyQuantityUnitConversionPayload,
    GrocyQuantityUnitConversionsResponse,
    GrocyQuantityUnitPayload,
    GrocyQuantityUnitsResponse,
)

from .common import with_grocy_manager
from .dependencies import governor, router


@router.get("/{instance_index}/quantity-units", response_model=GrocyQuantityUnitsResponse)
async def list_quantity_units(instance_index: str) -> GrocyQuantityUnitsResponse:
    """Return Grocy quantity units for the requested instance."""

    def _load_units():
        return with_grocy_manager(instance_index, lambda manager: manager.list_quantity_units())

    try:
        units = await run_in_threadpool(_load_units)
    except MetadataNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    payload = [
        GrocyQuantityUnitPayload(
            id=unit.id,
            name=unit.name,
            description=unit.description,
            name_plural=unit.name_plural,
            plural_forms=unit.plural_forms,
            active=unit.active,
            is_discrete=unit.is_discrete,
        )
        for unit in units
    ]
    return GrocyQuantityUnitsResponse(instance_index=instance_index, quantity_units=payload)


@router.get("/quantity-unit-conversions", response_model=GrocyQuantityUnitConversionsResponse)
async def list_quantity_unit_conversions() -> GrocyQuantityUnitConversionsResponse:
    """Return a fully connected conversion map for universal quantity units."""

    def _load_manifest():
        return UniversalManifest.load(governor.manifest_root / "universal")

    def _load_conversion_definitions():
        conversions_path = governor.manifest_root / "universal" / "quantity_unit_conversions.json"
        return load_quantity_unit_conversions(conversions_path)

    try:
        manifest = await run_in_threadpool(_load_manifest)
        conversions = await run_in_threadpool(_load_conversion_definitions)
    except FileNotFoundError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    unit_name_lookup = {unit.normalized_name(): unit.name for unit in manifest.quantity_units}
    graph = build_conversion_graph(conversions, unit_name_lookup)
    conversion_map = build_full_conversion_map(graph)
    payload = [
        GrocyQuantityUnitConversionPayload(
            from_unit_name=unit_name_lookup[from_key],
            to_unit_name=unit_name_lookup[to_key],
            factor=factor,
        )
        for (from_key, to_key), factor in sorted(conversion_map.items())
        if from_key in unit_name_lookup and to_key in unit_name_lookup
    ]
    return GrocyQuantityUnitConversionsResponse(conversions=payload)

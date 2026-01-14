from __future__ import annotations

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from core.grocy.exceptions import MetadataNotFoundError
from models.grocy import GrocyQuantityUnitPayload, GrocyQuantityUnitsResponse

from .common import with_grocy_manager
from .dependencies import router


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

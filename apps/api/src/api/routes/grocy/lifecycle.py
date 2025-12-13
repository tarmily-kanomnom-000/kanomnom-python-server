from __future__ import annotations

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from core.grocy.exceptions import ManifestNotFoundError, MetadataNotFoundError
from models.grocy import CreatedQuantityUnit, InitializeInstanceResponse

from .dependencies import governor, router


@router.post("/{instance_index}/initialize", response_model=InitializeInstanceResponse)
async def initialize_instance(instance_index: str) -> InitializeInstanceResponse:
    """Ensure the requested Grocy instance is seeded with universal quantity units."""

    def _sync_units():
        return governor.ensure_quantity_units(instance_index)

    try:
        sync_result = await run_in_threadpool(_sync_units)
    except MetadataNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ManifestNotFoundError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    created_units = [
        CreatedQuantityUnit(name=item.definition.name, identifier=item.identifier)
        for item in sync_result.created
    ]

    return InitializeInstanceResponse(
        instance_index=instance_index,
        quantity_unit_identifiers=sync_result.identifier_by_normalized_name,
        created_units=created_units,
    )

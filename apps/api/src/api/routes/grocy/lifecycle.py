from __future__ import annotations

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from core.grocy.exceptions import ManifestNotFoundError, MetadataNotFoundError
from models.grocy import (
    CreatedProductGroup,
    CreatedQuantityUnit,
    InitializeInstanceResponse,
)

from .dependencies import governor, router


@router.post("/{instance_index}/initialize", response_model=InitializeInstanceResponse)
async def initialize_instance(instance_index: str) -> InitializeInstanceResponse:
    """Ensure the requested Grocy instance is seeded with universal product groups and quantity units."""

    def _sync_manifest():
        groups = governor.ensure_product_groups(instance_index)
        units = governor.ensure_quantity_units(instance_index)
        return groups, units

    try:
        groups_result, units_result = await run_in_threadpool(_sync_manifest)
    except MetadataNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ManifestNotFoundError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    created_units = [
        CreatedQuantityUnit(name=item.definition.name, identifier=item.identifier) for item in units_result.created
    ]
    created_groups = [
        CreatedProductGroup(name=item.definition.name, identifier=item.identifier) for item in groups_result.created
    ]

    return InitializeInstanceResponse(
        instance_index=instance_index,
        quantity_unit_identifiers=units_result.identifier_by_normalized_name,
        created_units=created_units,
        product_group_identifiers=groups_result.identifier_by_normalized_name,
        created_product_groups=created_groups,
    )

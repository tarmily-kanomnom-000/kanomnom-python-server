from __future__ import annotations

from core.grocy.exceptions import ManifestNotFoundError, MetadataNotFoundError
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from models.grocy import (
    CreatedProductGroup,
    CreatedQuantityUnit,
    CreatedShoppingLocation,
    InitializeInstanceResponse,
)

from .dependencies import governor, router


@router.post("/{instance_index}/initialize", response_model=InitializeInstanceResponse)
async def initialize_instance(instance_index: str) -> InitializeInstanceResponse:
    """Ensure the requested Grocy instance is seeded with universal manifests."""

    def _sync_manifest():
        groups = governor.ensure_product_groups(instance_index)
        units = governor.ensure_quantity_units(instance_index)
        shopping_locations = governor.ensure_shopping_locations(instance_index)
        return groups, units, shopping_locations

    try:
        groups_result, units_result, shopping_location_result = await run_in_threadpool(
            _sync_manifest
        )
    except MetadataNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ManifestNotFoundError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    created_units = [
        CreatedQuantityUnit(name=item.definition.name, identifier=item.identifier)
        for item in units_result.created
    ]
    created_groups = [
        CreatedProductGroup(name=item.definition.name, identifier=item.identifier)
        for item in groups_result.created
    ]
    created_shopping_locations = [
        CreatedShoppingLocation(name=item.definition.name, identifier=item.identifier)
        for item in shopping_location_result.created
    ]

    return InitializeInstanceResponse(
        instance_index=instance_index,
        quantity_unit_identifiers=units_result.identifier_by_normalized_name,
        created_units=created_units,
        product_group_identifiers=groups_result.identifier_by_normalized_name,
        created_product_groups=created_groups,
        shopping_location_identifiers=shopping_location_result.identifier_by_normalized_name,
        created_shopping_locations=created_shopping_locations,
    )

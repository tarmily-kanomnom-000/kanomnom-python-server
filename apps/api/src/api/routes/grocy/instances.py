from __future__ import annotations

from fastapi.concurrency import run_in_threadpool
from models.grocy import (
    GrocyLocationPayload,
    GrocyShoppingLocationPayload,
    InstanceAddressPayload,
    InstanceSummary,
    ListInstancesResponse,
)

from .dependencies import governor, router


@router.get("/instances", response_model=ListInstancesResponse)
async def list_instances() -> ListInstancesResponse:
    """List all Grocy instances known to the governor."""

    def _load_instances():
        instances = []
        for index, metadata in governor.list_instances_with_metadata():
            manager = governor.manager_for(index)
            locations = manager.list_locations()
            shopping_locations = manager.list_shopping_locations()
            instances.append((index, metadata, locations, shopping_locations))
        return instances

    instance_metadata = await run_in_threadpool(_load_instances)
    summaries = []
    for index, metadata, locations, shopping_locations in instance_metadata:
        address_payload = (
            InstanceAddressPayload(
                line1=metadata.address.line1,
                line2=metadata.address.line2,
                city=metadata.address.city,
                state=metadata.address.state,
                postal_code=metadata.address.postal_code,
                country=metadata.address.country,
            )
            if metadata.address
            else None
        )
        location_payloads = [
            GrocyLocationPayload(
                id=location.id,
                name=location.name,
                description=location.description,
                row_created_timestamp=location.row_created_timestamp,
                is_freezer=location.is_freezer,
                active=location.active,
            )
            for location in locations
        ]
        shopping_location_payloads = [
            GrocyShoppingLocationPayload(
                id=location.id,
                name=location.name,
                description=location.description,
                row_created_timestamp=location.row_created_timestamp,
                active=location.active,
            )
            for location in shopping_locations
        ]
        summaries.append(
            InstanceSummary(
                instance_index=index,
                location_name=metadata.location_name,
                location_types=metadata.location_types,
                address=address_payload,
                locations=location_payloads,
                shopping_locations=shopping_location_payloads,
            )
        )

    return ListInstancesResponse(instances=summaries)

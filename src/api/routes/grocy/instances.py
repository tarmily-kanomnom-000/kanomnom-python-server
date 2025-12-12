from __future__ import annotations

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from src.models.grocy import (
    GrocyLocationPayload,
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
            instances.append((index, metadata, locations))
        return instances

    instance_metadata = await run_in_threadpool(_load_instances)
    summaries = []
    for index, metadata, locations in instance_metadata:
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
        summaries.append(
            InstanceSummary(
                instance_index=index,
                location_name=metadata.location_name,
                location_types=metadata.location_types,
                address=address_payload,
                locations=location_payloads,
            )
        )

    return ListInstancesResponse(instances=summaries)

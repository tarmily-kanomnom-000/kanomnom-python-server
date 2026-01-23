from __future__ import annotations

from .dependencies import governor, router


@router.get("/instances")
async def list_medusa_instances() -> dict[str, list[str]]:
    """List Medusa instance keys available to the API runtime."""
    return {"instances": governor.available_instances()}

from __future__ import annotations

from pydantic import BaseModel, Field


class BulkRemoveRequest(BaseModel):
    """Request to remove multiple items at once"""

    item_ids: list[str] = Field(min_length=1)


__all__ = ["BulkRemoveRequest"]

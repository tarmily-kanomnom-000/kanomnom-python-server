from __future__ import annotations

from pydantic import BaseModel


class BulkRemoveRequest(BaseModel):
    """Request to remove multiple items at once"""

    item_ids: list[str]


__all__ = ["BulkRemoveRequest"]

from __future__ import annotations

import logging

import requests
from fastapi import HTTPException, status

from core.medusa.exceptions import MedusaMetadataNotFoundError

from .dependencies import governor, router

logger = logging.getLogger(__name__)


@router.get("/instances/{instance_key}/auth/verify")
async def verify_medusa_auth(instance_key: str) -> dict[str, str | bool]:
    """Verify Medusa authentication for the provided instance."""
    try:
        client = governor.client_for(instance_key)
        client.ensure_token()
    except MedusaMetadataNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ValueError, requests.RequestException) as exc:
        logger.exception("Medusa auth verification failed for %s", instance_key)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Medusa auth failed") from exc
    return {"instance_key": instance_key, "authenticated": True}

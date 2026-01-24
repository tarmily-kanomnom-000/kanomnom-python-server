from __future__ import annotations

from pathlib import Path

from core.medusa import MedusaGovernor, MedusaMetadataRepository
from core.medusa.credentials import MedusaCredentialsRepository
from fastapi import APIRouter

router = APIRouter(prefix="/medusa", tags=["medusa"])

# Resolve the service root (apps/api) that contains src/ and medusa_manifest/.
SERVICE_ROOT = Path(__file__).resolve().parents[4]
MANIFEST_ROOT = SERVICE_ROOT / "medusa_manifest"

metadata_repository = MedusaMetadataRepository(MANIFEST_ROOT)
credentials_repository = MedusaCredentialsRepository(MANIFEST_ROOT)
governor = MedusaGovernor(metadata_repository, credentials_repository)

__all__ = ["router", "governor"]

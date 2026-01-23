from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from core.nextcloud import (
    NextcloudCredentialsRepository,
    NextcloudGovernor,
    NextcloudMetadataRepository,
)

router = APIRouter(prefix="/nextcloud", tags=["nextcloud"])

# Resolve the service root (apps/api) that contains src/ and nextcloud_manifest/.
SERVICE_ROOT = Path(__file__).resolve().parents[4]
MANIFEST_ROOT = SERVICE_ROOT / "nextcloud_manifest"

metadata_repository = NextcloudMetadataRepository(MANIFEST_ROOT)
credentials_repository = NextcloudCredentialsRepository(MANIFEST_ROOT)
governor = NextcloudGovernor(metadata_repository, credentials_repository)

__all__ = ["router", "governor"]

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from src.core.grocy import GrocyGovernor, InstanceMetadataRepository

router = APIRouter(prefix="/grocy", tags=["grocy"])

# Resolve repository root (directory that contains src/ and grocy_manifest/)
REPO_ROOT = Path(__file__).resolve().parents[4]
MANIFEST_ROOT = REPO_ROOT / "grocy_manifest"

metadata_repository = InstanceMetadataRepository(MANIFEST_ROOT)
governor = GrocyGovernor(metadata_repository, MANIFEST_ROOT)

__all__ = ["router", "governor"]

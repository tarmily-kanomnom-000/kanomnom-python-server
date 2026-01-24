from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from core.medusa.exceptions import MedusaMetadataNotFoundError
from core.medusa.models import MedusaInstanceMetadata


class MedusaMetadataRepository:
    """Loads and enumerates Medusa instance metadata files."""

    def __init__(self, manifest_root: Path) -> None:
        self.manifest_root = manifest_root

    def list_instance_keys(self) -> list[str]:
        """Return instance keys that include a metadata.yaml."""
        instance_keys: list[str] = []
        for entry in self.manifest_root.iterdir():
            metadata_path = entry / "metadata.yaml"
            if entry.is_dir() and metadata_path.exists():
                instance_keys.append(entry.name)
        return sorted(instance_keys)

    def load(self, instance_key: str) -> MedusaInstanceMetadata:
        """Load the metadata.yaml file for a specific Medusa instance."""
        metadata_path = self.manifest_root / instance_key / "metadata.yaml"
        if not metadata_path.exists():
            raise MedusaMetadataNotFoundError(
                f"Missing metadata for instance {instance_key}: {metadata_path}"
            )
        parsed = _parse_metadata_file(metadata_path)
        base_url = _require_string(parsed.get("medusa_url"), "medusa_url")
        return MedusaInstanceMetadata(instance_key=instance_key, base_url=base_url)


def _parse_metadata_file(path: Path) -> dict[str, Any]:
    """Parse the metadata.yaml file using PyYAML for correctness and safety."""
    with path.open("r", encoding="utf-8") as handle:
        try:
            parsed = yaml.safe_load(handle) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"Failed to parse metadata file {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected mapping at root of {path}")
    return parsed


def _require_string(value: Any, field: str) -> str:
    if value is None:
        raise ValueError(f"{field} is required.")
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError(f"{field} must be a non-empty string.")
    return cleaned

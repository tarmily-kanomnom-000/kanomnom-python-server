from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from core.grocy.exceptions import MetadataNotFoundError
from core.grocy.models import InstanceAddress, InstanceMetadata


class InstanceMetadataRepository:
    """Loads and enumerates Grocy instance metadata files."""

    def __init__(self, manifest_root: Path) -> None:
        self.manifest_root = manifest_root

    def list_instance_indexes(self) -> list[str]:
        """Return instance indexes that include a metadata.yaml."""
        indexes: list[str] = []
        for entry in self.manifest_root.iterdir():
            metadata_path = entry / "metadata.yaml"
            if entry.is_dir() and metadata_path.exists():
                indexes.append(entry.name)
        return sorted(indexes)

    def load(self, instance_index: str) -> InstanceMetadata:
        """Load the metadata.yaml file for a specific Grocy instance."""
        metadata_path = self.manifest_root / instance_index / "metadata.yaml"
        if not metadata_path.exists():
            raise MetadataNotFoundError(
                f"Missing metadata for instance {instance_index}: {metadata_path}"
            )
        parsed = _parse_metadata_file(metadata_path)
        address = _hydrate_address(parsed.get("address"))
        instance_timezone = _extract_timezone(parsed.get("instance_timezone"))
        location_types = _require_string_list(parsed.get("location_types"), "location_types")
        return InstanceMetadata(
            grocy_url=_require_string(parsed.get("grocy_url"), "grocy_url"),
            api_key=_require_string(parsed.get("api_key"), "api_key"),
            location_name=_require_string(parsed.get("location_name"), "location_name"),
            location_types=location_types,
            instance_timezone=instance_timezone,
            address=address,
        )


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


def _hydrate_address(raw: Any) -> InstanceAddress | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValueError("address must be a mapping.")

    def _require(key: str) -> str:
        value = raw.get(key)
        if value is None:
            value = raw.get(key.replace(" ", "_"))
        return _require_string(value, f"address.{key}")

    line1 = _require("line 1")
    line2_raw = raw.get("line 2") or raw.get("line_2")
    return InstanceAddress(
        line1=line1,
        line2=_optional_string(line2_raw),
        city=_require("city"),
        state=_require("state"),
        postal_code=_require("postal code"),
        country=_require("country"),
    )


def _extract_timezone(raw: Any) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _require_string(value: Any, field: str) -> str:
    if value is None:
        raise ValueError(f"{field} is required.")
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError(f"{field} must be a non-empty string.")
    return cleaned


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned if cleaned else None


def _require_string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field} must be a list of strings.")
    entries: list[str] = []
    for index, entry in enumerate(value):
        entries.append(_require_string(entry, f"{field}[{index}]"))
    return entries

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from core.nextcloud.models import NextcloudCalendarMetadata, NextcloudInstanceMetadata


class NextcloudMetadataRepository:
    """Loads and enumerates Nextcloud instance metadata files."""

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

    def load(self, instance_key: str) -> NextcloudInstanceMetadata:
        """Load the metadata.yaml file for a specific Nextcloud instance."""
        metadata_path = self.manifest_root / instance_key / "metadata.yaml"
        if not metadata_path.exists():
            raise FileNotFoundError(f"Missing metadata for instance {instance_key}: {metadata_path}")
        parsed = _parse_metadata_file(metadata_path)
        dav_url = _require_string(parsed.get("dav_url"), "dav_url")
        calendars_raw = parsed.get("calendars")
        calendars = _require_calendar_list(calendars_raw, "calendars")
        return NextcloudInstanceMetadata(
            instance_key=instance_key,
            dav_url=dav_url,
            calendars=calendars,
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


def _require_string(value: Any, field: str) -> str:
    if value is None:
        raise ValueError(f"{field} is required.")
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError(f"{field} must be a non-empty string.")
    return cleaned


def _require_calendar_list(value: Any, field: str) -> list[NextcloudCalendarMetadata]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list.")
    calendars: list[NextcloudCalendarMetadata] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise ValueError(f"{field}[{index}] must be a mapping.")
        name = _require_string(entry.get("name"), f"{field}[{index}].name")
        description = _optional_string(entry.get("description"))
        tags = _require_string_list(entry.get("tags"), f"{field}[{index}].tags")
        calendars.append(
            NextcloudCalendarMetadata(
                name=name,
                description=description,
                tags=tags,
            )
        )
    if not calendars:
        raise ValueError(f"{field} must include at least one calendar.")
    return calendars


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned if cleaned else None


def _require_string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list.")
    cleaned_values: list[str] = []
    for index, entry in enumerate(value):
        cleaned_values.append(_require_string(entry, f"{field}[{index}]"))
    return cleaned_values

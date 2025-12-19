from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

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
        return InstanceMetadata(
            grocy_url=str(parsed["grocy_url"]),
            api_key=str(parsed["api_key"]),
            location_name=str(parsed["location_name"]),
            location_types=list(parsed["location_types"]),
            instance_timezone=instance_timezone,
            address=address,
        )


def _parse_metadata_file(path: Path) -> dict[str, Any]:
    """Parse the metadata.yaml file without relying on external dependencies."""
    root: dict[str, Any] = {}
    stack = [root]
    indent_stack = [0]
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            while indent < indent_stack[-1] and len(stack) > 1:
                stack.pop()
                indent_stack.pop()
            line = raw.strip()
            if ":" not in line:
                raise ValueError(f"Invalid metadata line in {path}: {raw.rstrip()}")
            key, remainder = line.split(":", 1)
            cleaned_key = key.strip().strip('"')
            value_str = remainder.strip()
            if not value_str:
                new_dict: dict[str, Any] = {}
                stack[-1][cleaned_key] = new_dict
                stack.append(new_dict)
                indent_stack.append(indent + 2)
            else:
                stack[-1][cleaned_key] = _parse_scalar(value_str)
    return root


def _hydrate_address(raw: Any) -> InstanceAddress | None:
    if not isinstance(raw, dict):
        return None
    def _require(key: str) -> str:
        value = raw.get(key) or raw.get(key.replace(" ", "_"))
        if value is None:
            raise ValueError(f"Missing required address field '{key}'")
        return str(value)

    line1 = _require("line 1")
    line2_raw = raw.get("line 2") or raw.get("line_2")
    return InstanceAddress(
        line1=line1,
        line2=str(line2_raw) if line2_raw not in (None, "") else None,
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


def _parse_scalar(raw: str) -> Any:
    """Parse a scalar value, falling back to raw strings when literal eval fails."""
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return raw.strip()

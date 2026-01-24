from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from core.medusa.models import MedusaInstanceCredentials


class MedusaCredentialsRepository:
    """Loads Medusa admin credentials from instance manifests."""

    def __init__(self, manifest_root: Path) -> None:
        self.manifest_root = manifest_root

    def load(self, instance_key: str) -> MedusaInstanceCredentials:
        """Load the credentials.yaml file for a specific Medusa instance."""
        credentials_path = self.manifest_root / instance_key / "credentials.yaml"
        if not credentials_path.exists():
            raise FileNotFoundError(
                f"Missing credentials for instance {instance_key}: {credentials_path}"
            )
        parsed = _parse_credentials_file(credentials_path)
        return _resolve_credentials(parsed, credentials_path)


def _parse_credentials_file(path: Path) -> dict[str, Any]:
    """Parse the credentials.yaml file using PyYAML for correctness and safety."""
    with path.open("r", encoding="utf-8") as handle:
        try:
            parsed = yaml.safe_load(handle) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"Failed to parse credentials file {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected mapping at root of {path}")
    return parsed


def _resolve_credentials(
    parsed: dict[str, Any], path: Path
) -> MedusaInstanceCredentials:
    credentials_list = parsed.get("credentials")
    if credentials_list is None:
        raise ValueError(f"Missing credentials data in {path}")
    entries = _require_list(credentials_list, "credentials")
    resolved = _select_default_entry(entries, path)
    admin_email = _require_string(
        resolved.get("admin_email"), "credentials.admin_email"
    )
    admin_password = _require_string(
        resolved.get("admin_password"), "credentials.admin_password"
    )
    return MedusaInstanceCredentials(
        admin_email=admin_email, admin_password=admin_password
    )


def _require_string(value: Any, field: str) -> str:
    if value is None:
        raise ValueError(f"{field} is required.")
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError(f"{field} must be a non-empty string.")
    return cleaned


def _require_list(value: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list.")
    entries: list[dict[str, Any]] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise ValueError(f"{field}[{index}] must be a mapping.")
        entries.append(entry)
    return entries


def _select_default_entry(entries: list[dict[str, Any]], path: Path) -> dict[str, Any]:
    default_entries = [entry for entry in entries if entry.get("default") is True]
    if len(default_entries) == 1:
        return default_entries[0]
    if len(default_entries) > 1:
        raise ValueError(f"Multiple default credentials entries found in {path}")
    if len(entries) == 1:
        return entries[0]
    raise ValueError(f"No default credentials entry found in {path}")

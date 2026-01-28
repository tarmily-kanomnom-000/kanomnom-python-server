from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    """Load a YAML file and require a mapping at the root."""
    with path.open("r", encoding="utf-8") as handle:
        try:
            parsed = yaml.safe_load(handle) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"Failed to parse YAML file {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected mapping at root of {path}")
    return parsed

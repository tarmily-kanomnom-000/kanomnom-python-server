from __future__ import annotations

import os

_DEFAULT_INSTANCE_KEY = "000000"


def resolve_medusa_instance_key() -> str:
    value = os.getenv("MEDUSA_DEFAULT_INSTANCE_KEY")
    return _normalize_instance_key(value)


def resolve_nextcloud_instance_key() -> str:
    value = os.getenv("NEXTCLOUD_DEFAULT_INSTANCE_KEY")
    return _normalize_instance_key(value)


def _normalize_instance_key(value: str | None) -> str:
    if value is None:
        return _DEFAULT_INSTANCE_KEY
    cleaned = value.strip()
    return cleaned or _DEFAULT_INSTANCE_KEY

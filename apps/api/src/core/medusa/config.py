from __future__ import annotations

from dataclasses import dataclass

from core.medusa.models import MedusaInstanceCredentials, MedusaInstanceMetadata

_DEFAULT_REQUEST_TIMEOUT_SECONDS = 15.0
_DEFAULT_TOKEN_LEEWAY_SECONDS = 60
_DEFAULT_TOKEN_FALLBACK_TTL_SECONDS = 3600


@dataclass(frozen=True)
class MedusaConfig:
    instance_key: str
    base_url: str
    admin_email: str
    admin_password: str
    request_timeout_seconds: float
    token_leeway_seconds: int
    token_fallback_ttl_seconds: int


def load_medusa_config(
    metadata: MedusaInstanceMetadata,
    credentials: MedusaInstanceCredentials,
) -> MedusaConfig:
    """Load Medusa configuration for the provided instance metadata and credentials."""
    instance_key = metadata.instance_key
    base_url = metadata.base_url.rstrip("/")
    request_timeout = _DEFAULT_REQUEST_TIMEOUT_SECONDS
    token_leeway = _DEFAULT_TOKEN_LEEWAY_SECONDS
    token_fallback_ttl = _DEFAULT_TOKEN_FALLBACK_TTL_SECONDS
    return MedusaConfig(
        instance_key=instance_key,
        base_url=base_url,
        admin_email=credentials.admin_email,
        admin_password=credentials.admin_password,
        request_timeout_seconds=request_timeout,
        token_leeway_seconds=token_leeway,
        token_fallback_ttl_seconds=token_fallback_ttl,
    )

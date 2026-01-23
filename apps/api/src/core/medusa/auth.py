from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timedelta, timezone

import requests

from core.cache.medusa_token_cache import MedusaTokenCacheManager
from core.medusa.config import MedusaConfig
from core.medusa.models import MedusaAuthToken

logger = logging.getLogger(__name__)


class MedusaAuthProvider:
    """Handles Medusa authentication and token caching."""

    def __init__(self, config: MedusaConfig, token_cache: MedusaTokenCacheManager) -> None:
        self.config = config
        self.token_cache = token_cache

    def get_token(self) -> str:
        """Return a cached token or fetch a new one from Medusa."""
        cached = self.token_cache.get_token(self.config.instance_key, self.config.token_leeway_seconds)
        if cached:
            return cached
        auth_token = self._request_new_token()
        self.token_cache.save_token(self.config.instance_key, auth_token.token, auth_token.expires_at)
        return auth_token.token

    def _request_new_token(self) -> MedusaAuthToken:
        url = f"{self.config.base_url}/auth/user/emailpass"
        payload = {"email": self.config.admin_email, "password": self.config.admin_password}
        logger.info("Requesting Medusa auth token for %s", self.config.instance_key)
        response = requests.post(
            url=url,
            json=payload,
            timeout=self.config.request_timeout_seconds,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            logger.error(
                "Medusa auth failed (%s) for %s: %s",
                response.status_code,
                self.config.instance_key,
                response.text,
            )
            raise exc
        response_payload = response.json()
        token_raw = response_payload.get("token")
        if not isinstance(token_raw, str) or not token_raw:
            raise ValueError("Medusa auth response missing token")
        expires_at = _resolve_token_expiry(token_raw, self.config.token_fallback_ttl_seconds)
        return MedusaAuthToken(token=token_raw, expires_at=expires_at)


def _resolve_token_expiry(token: str, fallback_ttl_seconds: int) -> datetime:
    decoded_expiry = _decode_jwt_exp(token)
    if decoded_expiry is not None:
        return decoded_expiry
    logger.warning("Unable to decode Medusa token expiry; using fallback TTL")
    return datetime.now(timezone.utc) + timedelta(seconds=fallback_ttl_seconds)


def _decode_jwt_exp(token: str) -> datetime | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload_b64 = parts[1]
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    try:
        payload_bytes = base64.urlsafe_b64decode(padded)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    exp_value = payload.get("exp")
    if not isinstance(exp_value, int):
        return None
    return datetime.fromtimestamp(exp_value, tz=timezone.utc)

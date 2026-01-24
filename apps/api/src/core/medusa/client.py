from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

import requests
from core.medusa.auth import MedusaAuthProvider
from core.medusa.config import MedusaConfig
from requests import HTTPError
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = (502, 503, 504)
_ALLOWED_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})


class MedusaClient:
    """Thin HTTP client that encapsulates Medusa's REST API semantics."""

    def __init__(self, config: MedusaConfig, auth_provider: MedusaAuthProvider) -> None:
        self.config = config
        self.auth_provider = auth_provider
        self.base_url = config.base_url
        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=_build_retry_strategy())
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def ensure_token(self) -> str:
        """Ensure a valid Medusa token is available."""
        return self.auth_provider.get_token()

    def request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None,
        query_params: dict[str, Any] | None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Issue an HTTP request and raise with contextual details when Medusa rejects it."""
        url = f"{self.base_url}{path}"
        response = self._request_with_auth(method, url, json_body, query_params)
        if not response.content:
            return {}
        return response.json()

    def _request_with_auth(
        self,
        method: str,
        url: str,
        json_body: dict[str, Any] | None,
        query_params: dict[str, Any] | None,
    ) -> requests.Response:
        try:
            return self._send_request(method, url, json_body, query_params)
        except HTTPError as error:
            if error.response is not None and error.response.status_code == 401:
                logger.info(
                    "Medusa auth failed; clearing cached token and retrying once."
                )
                self.auth_provider.clear_token()
                return self._send_request(method, url, json_body, query_params)
            raise

    def _send_request(
        self,
        method: str,
        url: str,
        json_body: dict[str, Any] | None,
        query_params: dict[str, Any] | None,
    ) -> requests.Response:
        token = self.auth_provider.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        start = perf_counter()
        response = self.session.request(
            method=method,
            url=url,
            json=json_body,
            params=query_params,
            headers=headers,
            timeout=self.config.request_timeout_seconds,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            elapsed_ms = (perf_counter() - start) * 1000
            logger.warning(
                "medusa_request_error",
                extra={
                    "method": method,
                    "path": url,
                    "status_code": response.status_code,
                    "elapsed_ms": round(elapsed_ms, 2),
                },
            )
            details = response.text.strip()
            if details:
                raise requests.HTTPError(f"{error} - {details}") from error
            raise
        elapsed_ms = (perf_counter() - start) * 1000
        logger.debug(
            "medusa_request",
            extra={
                "method": method,
                "path": url,
                "status_code": response.status_code,
                "elapsed_ms": round(elapsed_ms, 2),
            },
        )
        return response


def _build_retry_strategy() -> Retry:
    return Retry(
        total=3,
        status_forcelist=_RETRYABLE_STATUS_CODES,
        allowed_methods=_ALLOWED_METHODS,
        backoff_factor=0.5,
        raise_on_status=False,
    )

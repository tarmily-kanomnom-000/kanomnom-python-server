import requests
from core.medusa.auth import MedusaAuthProvider
from core.medusa.client import MedusaClient
from core.medusa.config import MedusaConfig


class StubTokenCache:
    def __init__(self) -> None:
        self._token = "token-1"

    def get_token(self, instance_key: str, leeway_seconds: int) -> str | None:
        return self._token

    def save_token(self, instance_key: str, token: str, expires_at) -> None:
        self._token = token

    def clear_cache(self, instance_key: str) -> None:
        self._token = "token-2"


def test_medusa_client_retries_on_401() -> None:
    config = MedusaConfig(
        instance_key="test",
        base_url="https://medusa.example.com",
        admin_email="admin@example.com",
        admin_password="password",
        request_timeout_seconds=1.0,
        token_leeway_seconds=0,
        token_fallback_ttl_seconds=60,
    )
    token_cache = StubTokenCache()
    auth_provider = MedusaAuthProvider(config, token_cache)
    client = MedusaClient(config, auth_provider)

    calls: list[str] = []
    responses = [requests.Response(), requests.Response()]
    responses[0].status_code = 401
    responses[0]._content = b"unauthorized"
    responses[0].url = "https://medusa.example.com/admin/orders/123"
    responses[0].reason = "Unauthorized"
    responses[1].status_code = 200
    responses[1]._content = b'{"ok": true}'
    responses[1].url = "https://medusa.example.com/admin/orders/123"

    def fake_request(method, url, json, params, headers, timeout):
        calls.append(headers.get("Authorization", ""))
        response = responses.pop(0)
        response.request = requests.Request(method=method, url=url).prepare()
        return response

    client.session.request = fake_request  # type: ignore[assignment]

    payload = client.request("GET", "/admin/orders/123", None, None)

    assert payload == {"ok": True}
    assert calls == ["Bearer token-1", "Bearer token-2"]

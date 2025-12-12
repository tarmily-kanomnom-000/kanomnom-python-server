from __future__ import annotations

from typing import Any

import requests

from src.core.grocy.responses import (
    GrocyLocation,
    GrocyProduct,
    GrocyProductGroup,
    GrocyQuantityUnit,
    GrocyStockEntry,
    GrocyStockLogEntry,
    parse_locations,
    parse_product_groups,
    parse_products,
    parse_quantity_units,
    parse_stock_entries,
    parse_stock_log_entries,
)


class GrocyClient:
    """Thin HTTP client that encapsulates Grocy's REST API semantics."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"GROCY-API-KEY": api_key})

    def list_quantity_units(self) -> list[GrocyQuantityUnit]:
        """Return the list of quantity units already present in Grocy."""
        payload = self._request("GET", "/api/objects/quantity_units", None)
        return parse_quantity_units(payload)

    def create_quantity_unit(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a quantity unit via Grocy's API."""
        return self._request("POST", "/api/objects/quantity_units", payload)

    def list_products(self) -> list[GrocyProduct]:
        """Fetch the available products from Grocy."""
        payload = self._request("GET", "/api/objects/products", None)
        return parse_products(payload)

    def list_stock_log(self) -> list[GrocyStockLogEntry]:
        """Fetch the raw stock log entries from Grocy."""
        payload = self._request("GET", "/api/objects/stock_log", None)
        return parse_stock_log_entries(payload)

    def list_stock(self) -> list[GrocyStockEntry]:
        """Fetch the current stock state from Grocy."""
        payload = self._request("GET", "/api/objects/stock", None)
        return parse_stock_entries(payload)

    def list_locations(self) -> list[GrocyLocation]:
        """Fetch the defined product locations from Grocy."""
        payload = self._request("GET", "/api/objects/locations", None)
        return parse_locations(payload)

    def list_product_groups(self) -> list[GrocyProductGroup]:
        """Fetch product group definitions from Grocy."""
        payload = self._request("GET", "/api/objects/product_groups", None)
        return parse_product_groups(payload)

    def _request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None,
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """Issue an HTTP request and raise with contextual details when Grocy rejects it."""
        response = self.session.request(method=method, url=f"{self.base_url}{path}", json=json_body)
        try:
            response.raise_for_status()
        except requests.HTTPError as error:  # pragma: no cover - network failure path
            details = response.text.strip()
            if details:
                raise requests.HTTPError(f"{error} - {details}") from error
            raise
        if not response.content:
            return {}
        return response.json()

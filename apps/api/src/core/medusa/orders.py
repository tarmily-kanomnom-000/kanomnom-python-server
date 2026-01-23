from __future__ import annotations

from typing import Iterable

from core.medusa.client import MedusaClient
from models.medusa.order_response import MedusaOrderResponse


def fetch_orders(client: MedusaClient, order_ids: Iterable[str]) -> dict[str, MedusaOrderResponse]:
    """Fetch Medusa order details keyed by order id."""
    results: dict[str, MedusaOrderResponse] = {}
    for order_id in order_ids:
        if not order_id:
            continue
        payload = client.request(
            method="GET",
            path=f"/admin/orders/{order_id}",
            json_body=None,
            query_params=None,
        )
        results[order_id] = MedusaOrderResponse.model_validate(payload)
    return results

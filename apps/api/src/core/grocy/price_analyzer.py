from __future__ import annotations

import logging

from core.grocy.client import GrocyClient

logger = logging.getLogger(__name__)


class PriceAnalyzer:
    """Analyze purchase history for price intelligence"""

    def __init__(self, grocy_client: GrocyClient):
        self.grocy_client = grocy_client

    def get_last_purchase_price(self, product_id: int) -> dict | None:
        """
        Get the most recent purchase price for a product.

        Returns dict with unit_price, purchase_date, shopping_location_name
        or None if no purchase history exists.
        """
        try:
            # Get all stock log entries and filter for this product's purchases
            all_stock_entries = self.grocy_client.list_stock_log()
            stock_entries = [
                entry for entry in all_stock_entries if entry.product_id == product_id and entry.transaction_type == "purchase"
            ]

            if not stock_entries:
                return None

            # Sort by purchased_date (most recent first)
            stock_entries.sort(key=lambda x: x.purchased_date or "", reverse=True)

            latest = stock_entries[0]

            # Calculate unit price
            amount = latest.amount if latest.amount > 0 else 1
            price = latest.price or 0
            unit_price = (price / amount) if amount > 0 else price

            # Get shopping location name
            location_name = "Unknown"
            if latest.shopping_location_id:
                shopping_locations = self.grocy_client.list_shopping_locations()
                for location in shopping_locations:
                    if location.id == latest.shopping_location_id:
                        location_name = location.name
                        break

            return {
                "unit_price": round(unit_price, 2),
                "purchase_date": latest.purchased_date.isoformat() if latest.purchased_date else None,
                "shopping_location_name": location_name,
            }

        except Exception as e:
            logger.warning(
                "price_fetch_error",
                extra={"product_id": product_id, "error": str(e)},
            )
            return None

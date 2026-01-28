from __future__ import annotations


class MedusaOrderFetchError(RuntimeError):
    """Raised when Medusa order lookups fail for Grist inquiries."""

    def __init__(self, instance_key: str) -> None:
        super().__init__(f"Failed to fetch Medusa orders for {instance_key}")
        self.instance_key = instance_key

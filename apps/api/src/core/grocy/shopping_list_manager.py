from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)

from models.shopping_list import BulkItemUpdate, ShoppingList
from models.shopping_list_remove import BulkRemoveRequest


class ShoppingListManager:
    """Manages file I/O and CRUD operations for shopping lists"""

    def __init__(self, base_path: Path | str) -> None:
        self.base_path = Path(base_path)

    def get_instance_dir(self, instance_index: str) -> Path:
        """Get directory for instance shopping lists"""
        instance_dir = self.base_path / instance_index
        instance_dir.mkdir(parents=True, exist_ok=True)
        return instance_dir

    @contextmanager
    def _with_lock(self, instance_index: str) -> Iterator[None]:
        """Acquire a simple filesystem lock per instance to avoid concurrent writes."""
        lock_path = self.get_instance_dir(instance_index) / "active.lock"
        fd: int | None = None
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            yield
        finally:
            if fd is not None:
                os.close(fd)
            if lock_path.exists():
                lock_path.unlink(missing_ok=True)

    def active_list_exists(self, instance_index: str) -> bool:
        """Check if active.json exists for this instance"""
        active_path = self.get_instance_dir(instance_index) / "active.json"
        return active_path.exists()

    def load_active_list(self, instance_index: str) -> dict:
        """Load active shopping list from file"""
        active_path = self.get_instance_dir(instance_index) / "active.json"
        if not active_path.exists():
            raise FileNotFoundError(f"No active list for instance {instance_index}")

        with open(active_path) as f:
            list_data: dict[str, Any] = json.load(f)

        updated = self._normalize_list_data(list_data)
        if updated:
            logger.info(
                "shopping_list_normalized",
                extra={
                    "instance_index": instance_index,
                    "fields_backfilled": list(updated.keys()) if isinstance(updated, dict) else [],
                },
            )
            # Preserve original before mutation for safety
            backup_path = active_path.with_suffix(".json.bak")
            active_path.replace(backup_path)
            self.save_active_list(instance_index, list_data)

        # Validate shape to prevent silent drift
        shopping_list = ShoppingList(**list_data)
        list_data = shopping_list.model_dump()

        return list_data

    def save_active_list(self, instance_index: str, list_data: dict | ShoppingList) -> None:
        """Save active list to file with atomic write"""
        active_path = self.get_instance_dir(instance_index) / "active.json"
        payload = list_data.model_dump() if isinstance(list_data, ShoppingList) else list_data

        # Write to temp file first
        temp_path = active_path.with_suffix(".json.tmp")
        with open(temp_path, "w") as f:
            json.dump(payload, f, indent=2)

        # Atomic rename
        temp_path.replace(active_path)

    def archive_active_list(self, instance_index: str) -> str:
        """Move active list to archive"""
        with self._with_lock(instance_index):
            instance_dir = self.get_instance_dir(instance_index)
            active_path = instance_dir / "active.json"

            if not active_path.exists():
                raise FileNotFoundError(f"No active list to archive for instance {instance_index}")

            # Create archive directory
            archive_dir = instance_dir / "archive"
            archive_dir.mkdir(exist_ok=True)

            # Generate filename from current timestamp
            timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
            archive_filename = f"{timestamp}.json"
            archive_path = archive_dir / archive_filename

            # Move file
            active_path.rename(archive_path)

            return f"archive/{archive_filename}"

    def add_item(self, instance_index: str, item_data: dict) -> dict:
        """Add a new item to the active list"""
        with self._with_lock(instance_index):
            list_data = self.load_active_list(instance_index)

            # Prevent duplicate products in the list (regardless of status)
            existing_product_ids = {item["product_id"] for item in list_data.get("items", [])}
            if item_data["product_id"] in existing_product_ids:
                raise ValueError(
                    f"Product {item_data['product_id']} already exists in the active shopping list"
                )

            list_data["items"].append(item_data)

            location_id = item_data["shopping_location_id"]
            location_key = "UNKNOWN" if location_id is None else location_id

            if location_key not in list_data["location_order"]:
                list_data["location_order"].append(location_key)

            list_data["version"] = list_data.get("version", 1) + 1
            list_data["last_modified_at"] = datetime.utcnow().isoformat() + "Z"

            self.save_active_list(instance_index, list_data)

            logger.info(
                "shopping_list_add_item",
                extra={
                    "instance_index": instance_index,
                    "product_id": item_data.get("product_id"),
                    "item_id": item_data.get("id"),
                },
            )

            return item_data

    def remove_item(self, instance_index: str, item_id: str) -> None:
        """Remove an item from the active list and track deletion"""
        with self._with_lock(instance_index):
            list_data = self.load_active_list(instance_index)

            # Find the item to get its product_id before removing
            removed_item = None
            for item in list_data["items"]:
                if item["id"] == item_id:
                    removed_item = item
                    break

            if not removed_item:
                raise ValueError(f"Item {item_id} not found in list")

            # Remove from items list
            list_data["items"] = [
                item for item in list_data["items"] if item["id"] != item_id
            ]

            # Track deleted product_id to prevent it from coming back in merge
            if "deleted_product_ids" not in list_data:
                list_data["deleted_product_ids"] = []

            product_id = removed_item["product_id"]
            if product_id not in list_data["deleted_product_ids"]:
                list_data["deleted_product_ids"].append(product_id)

            list_data["version"] = list_data.get("version", 1) + 1
            list_data["last_modified_at"] = datetime.utcnow().isoformat() + "Z"

            self.save_active_list(instance_index, list_data)

            logger.info(
                "shopping_list_remove_item",
                extra={
                    "instance_index": instance_index,
                    "product_id": product_id,
                    "item_id": item_id,
                },
            )

    def bulk_update_items(
        self,
        instance_index: str,
        updates: list[dict] | list[BulkItemUpdate],
    ) -> list[dict]:
        """Update multiple items in a single operation

        Args:
            instance_index: The instance to update
            updates: List of update dictionaries, each containing:
                - item_id: str (required)
                - status: str | None
                - quantity_purchased: float | None
                - notes: str | None
                - checked_at: str | None

        Returns:
            List of updated items
        """
        with self._with_lock(instance_index):
            list_data = self.load_active_list(instance_index)
        now = datetime.utcnow().isoformat() + "Z"

        # Create a mapping of item_id to updates for fast lookup
        updates_map = {
            (update["item_id"] if isinstance(update, dict) else update.item_id): (
                update if isinstance(update, dict) else update.model_dump(exclude_none=True)
            )
            for update in updates
        }

        # Track which items were updated
        updated_items = []
        item_ids_found = set()
        remaining_items: list[dict] = []

        # Apply updates to all matching items
        for item in list_data["items"]:
            item_id = item["id"]
            if item_id in updates_map:
                update = updates_map[item_id]
                item_ids_found.add(item_id)

                # Apply updates
                if "status" in update and update["status"] is not None:
                    item["status"] = update["status"]
                if "quantity_purchased" in update and update["quantity_purchased"] is not None:
                    item["quantity_purchased"] = update["quantity_purchased"]
                if "notes" in update and update["notes"] is not None:
                    item["notes"] = update["notes"]
                if "checked_at" in update and update["checked_at"] is not None:
                    item["checked_at"] = update["checked_at"]

                # Update modified timestamp
                item["modified_at"] = now
                updated_items.append(item.copy())
                remaining_items.append(item)
            else:
                remaining_items.append(item)

        # Check if all requested items were found (including deletions)
        missing_ids = set(updates_map.keys()) - item_ids_found
        if missing_ids:
            raise ValueError(f"Items not found: {', '.join(missing_ids)}")

        list_data["items"] = remaining_items

        # Update list metadata
        list_data["version"] = list_data.get("version", 1) + 1
        list_data["last_modified_at"] = now

        # Save updated list
        self.save_active_list(instance_index, list_data)

        return updated_items

    def bulk_remove_items(
        self, instance_index: str, request: BulkRemoveRequest
    ) -> list[dict]:
        """Remove multiple items and track deleted product_ids"""
        with self._with_lock(instance_index):
            list_data = self.load_active_list(instance_index)
            item_ids = set(request.item_ids)
            removed: list[dict] = []
            remaining: list[dict] = []
            deleted_product_ids = list_data.get("deleted_product_ids", [])

            for item in list_data["items"]:
                if item["id"] in item_ids:
                    removed.append(item)
                    if item["product_id"] not in deleted_product_ids:
                        deleted_product_ids.append(item["product_id"])
                else:
                    remaining.append(item)

            missing_ids = item_ids - {item["id"] for item in removed}
            if missing_ids:
                raise ValueError(f"Items not found: {', '.join(missing_ids)}")

            list_data["items"] = remaining
            list_data["deleted_product_ids"] = deleted_product_ids
            list_data["version"] = list_data.get("version", 1) + 1
            list_data["last_modified_at"] = datetime.utcnow().isoformat() + "Z"

            self.save_active_list(instance_index, list_data)
            return removed

    def _normalize_list_data(self, list_data: dict[str, Any]) -> dict[str, Any] | bool:
        """Backfill required fields for older shopping list files."""
        updated_fields: dict[str, Any] = {}
        now = datetime.utcnow().isoformat() + "Z"

        if "created_at" not in list_data:
            list_data["created_at"] = now
            updated_fields["created_at"] = now

        if "version" not in list_data:
            list_data["version"] = 1
            updated_fields["version"] = 1

        if "last_modified_at" not in list_data:
            list_data["last_modified_at"] = list_data.get("created_at", now)
            updated_fields["last_modified_at"] = list_data["last_modified_at"]

        if "location_order" not in list_data:
            seen_locations: list[str | int] = []
            for item in list_data.get("items", []):
                location_key = (
                    "UNKNOWN"
                    if item.get("shopping_location_id") is None
                    else item["shopping_location_id"]
                )
                if location_key not in seen_locations:
                    seen_locations.append(location_key)
            list_data["location_order"] = seen_locations
            updated_fields["location_order"] = seen_locations

        if "deleted_product_ids" not in list_data:
            list_data["deleted_product_ids"] = []
            updated_fields["deleted_product_ids"] = []

        for item in list_data.get("items", []):
            if "quantity_suggested" not in item:
                item["quantity_suggested"] = item.get("quantity_needed", 0.0)
                updated_fields["quantity_suggested"] = True
            if "quantity_purchased" not in item:
                item["quantity_purchased"] = None
                updated_fields["quantity_purchased"] = True
            if "notes" not in item:
                item["notes"] = ""
                updated_fields["notes"] = True
            if "modified_at" not in item:
                item["modified_at"] = list_data.get("last_modified_at", now)
                updated_fields["modified_at"] = True
            if "last_price" not in item:
                item["last_price"] = None
                updated_fields["last_price"] = True

        return updated_fields or False

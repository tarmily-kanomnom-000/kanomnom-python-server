from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from models.shopping_list import BulkItemUpdate, ShoppingList
from models.shopping_list_remove import BulkRemoveRequest

logger = logging.getLogger(__name__)


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
        """Acquire a simple filesystem lock per instance to avoid concurrent writes.

        Retries briefly instead of immediately throwing when another worker holds the lock,
        to avoid transient 500s during rapid offline replay bursts.
        """
        lock_path = self.get_instance_dir(instance_index) / "active.lock"
        fd: int | None = None
        # Small bounded retry to allow queued syncs to serialize
        for attempt in range(5):
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                break
            except FileExistsError:
                if attempt == 4:
                    raise
                time.sleep(0.1)
        try:
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
        added_items = self.add_items_bulk(instance_index, [item_data])
        return added_items[0]

    def add_items_bulk(self, instance_index: str, items: list[dict]) -> list[dict]:
        """Add multiple items to the active list with a single lock/write."""
        if not items:
            raise ValueError("No items provided for bulk add")

        incoming_product_ids = [item["product_id"] for item in items]
        if len(set(incoming_product_ids)) != len(incoming_product_ids):
            raise ValueError("Duplicate product_ids in bulk add request")

        with self._with_lock(instance_index):
            list_data = self.load_active_list(instance_index)

            existing_product_ids = {item["product_id"] for item in list_data.get("items", [])}
            duplicates = existing_product_ids.intersection(incoming_product_ids)
            if duplicates:
                duplicate_list = ", ".join(str(pid) for pid in sorted(duplicates))
                raise ValueError(f"Products already exist in the active shopping list: {duplicate_list}")

            list_data["items"].extend(items)
            list_data["location_order"] = self._refresh_location_order(list_data["items"], list_data.get("location_order", []))

            list_data["version"] = list_data.get("version", 1) + 1
            list_data["last_modified_at"] = datetime.utcnow().isoformat() + "Z"

            self.save_active_list(instance_index, list_data)

            logger.info(
                "shopping_list_bulk_add",
                extra={
                    "instance_index": instance_index,
                    "count": len(items),
                },
            )

            return items

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
        if not updates:
            raise ValueError("No updates provided")

        with self._with_lock(instance_index):
            list_data = self.load_active_list(instance_index)
            now = datetime.utcnow().isoformat() + "Z"

            # Create a mapping of item_id to updates for fast lookup
            updates_map = {}
            for update in updates:
                key = update["item_id"] if isinstance(update, dict) else update.item_id
                if key in updates_map:
                    raise ValueError(f"Duplicate item_id in updates: {key}")
                updates_map[key] = update if isinstance(update, dict) else update.model_dump(exclude_none=True)

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
                    if "shopping_location_id" in update:
                        item["shopping_location_id"] = update["shopping_location_id"]
                    if "shopping_location_name" in update and update["shopping_location_name"] is not None:
                        item["shopping_location_name"] = update["shopping_location_name"]
                    elif "shopping_location_id" in update:
                        item["shopping_location_name"] = (
                            "UNKNOWN" if update["shopping_location_id"] is None else item.get("shopping_location_name", "UNKNOWN")
                        )

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
            list_data["location_order"] = self._refresh_location_order(list_data["items"], list_data.get("location_order", []))

            # Update list metadata
            list_data["version"] = list_data.get("version", 1) + 1
            list_data["last_modified_at"] = now

            # Save updated list
            self.save_active_list(instance_index, list_data)

            return updated_items

    def bulk_remove_items(self, instance_index: str, request: BulkRemoveRequest) -> list[dict]:
        """Remove multiple items and track deleted product_ids"""
        if not request.item_ids:
            raise ValueError("No item_ids provided for removal")

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
            list_data["location_order"] = self._refresh_location_order(remaining, list_data.get("location_order", []))
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
                location_key = "UNKNOWN" if item.get("shopping_location_id") is None else item["shopping_location_id"]
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

    @staticmethod
    def _location_key(item: dict[str, Any]) -> str | int:
        """Return normalized location key for an item."""
        location_id = item.get("shopping_location_id")
        return "UNKNOWN" if location_id is None else location_id

    def _refresh_location_order(self, items: list[dict[str, Any]], existing_order: list[str | int]) -> list[str | int]:
        """Rebuild location_order preserving existing ordering where possible."""
        seen_keys: list[str | int] = []
        seen_key_strs: set[str] = set()

        for item in items:
            key = self._location_key(item)
            key_str = str(key)
            if key_str not in seen_key_strs:
                seen_keys.append(key)
                seen_key_strs.add(key_str)

        ordered = [loc for loc in existing_order if str(loc) in seen_key_strs]
        ordered_keys = {str(loc) for loc in ordered}
        for key in seen_keys:
            key_str = str(key)
            if key_str not in ordered_keys:
                ordered.append(key)
                ordered_keys.add(key_str)

        return ordered

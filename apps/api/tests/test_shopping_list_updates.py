from pathlib import Path

import pytest

from api.routes.grocy.shopping_list import _serialize_updates
from core.grocy.shopping_list_manager import ShoppingListManager
from models.shopping_list import BulkItemUpdate, BulkUpdateRequest
from models.shopping_list_remove import BulkRemoveRequest


def test_status_update_preserves_location_when_not_provided(tmp_path: Path) -> None:
    instance_index = "test-instance"
    manager = ShoppingListManager(tmp_path)

    item_id = "item-1"
    shopping_list = {
        "id": "list-1",
        "instance_index": instance_index,
        "version": 1,
        "created_at": "2024-01-01T00:00:00Z",
        "last_modified_at": "2024-01-01T00:00:00Z",
        "items": [
            {
                "id": item_id,
                "product_id": 1,
                "product_name": "Milk",
                "shopping_location_id": 2,
                "shopping_location_name": "Home",
                "status": "pending",
                "quantity_suggested": 1.0,
                "quantity_purchased": None,
                "quantity_unit": "unit",
                "current_stock": 0.0,
                "min_stock": 1.0,
                "last_price": None,
                "notes": "",
                "checked_at": None,
                "modified_at": "2024-01-01T00:00:00Z",
            }
        ],
        "location_order": [2],
        "deleted_product_ids": [],
    }
    manager.save_active_list(instance_index, shopping_list)

    request = BulkUpdateRequest(
        updates=[
            BulkItemUpdate(
                item_id=item_id,
                status="purchased",
                checked_at="2024-01-02T00:00:00Z",
            )
        ]
    )

    serialized_updates = _serialize_updates(request.updates)
    manager.bulk_update_items(instance_index, serialized_updates)
    updated_list = manager.load_active_list(instance_index)
    updated_item = next(item for item in updated_list["items"] if item["id"] == item_id)

    assert updated_item["status"] == "purchased"
    assert updated_item["shopping_location_id"] == 2
    assert updated_item["shopping_location_name"] == "Home"
    assert updated_list["location_order"] == [2]


def test_bulk_add_updates_location_order_once(tmp_path: Path) -> None:
    instance_index = "bulk-add"
    manager = ShoppingListManager(tmp_path)

    base_list = {
        "id": "list-1",
        "instance_index": instance_index,
        "version": 1,
        "created_at": "2024-01-01T00:00:00Z",
        "last_modified_at": "2024-01-01T00:00:00Z",
        "items": [
            {
                "id": "existing-1",
                "product_id": 1,
                "product_name": "Milk",
                "shopping_location_id": 2,
                "shopping_location_name": "Home",
                "status": "pending",
                "quantity_suggested": 1.0,
                "quantity_purchased": None,
                "quantity_unit": "unit",
                "current_stock": 0.0,
                "min_stock": 1.0,
                "last_price": None,
                "notes": "",
                "checked_at": None,
                "modified_at": "2024-01-01T00:00:00Z",
            }
        ],
        "location_order": [2],
        "deleted_product_ids": [],
    }
    manager.save_active_list(instance_index, base_list)

    items_to_add = [
        {
            "id": "new-1",
            "product_id": 2,
            "product_name": "Eggs",
            "shopping_location_id": 3,
            "shopping_location_name": "Store",
            "status": "pending",
            "quantity_suggested": 1.0,
            "quantity_purchased": None,
            "quantity_unit": "unit",
            "current_stock": 0.0,
            "min_stock": 1.0,
            "last_price": None,
            "notes": "",
            "checked_at": None,
            "modified_at": "2024-01-01T00:00:00Z",
        },
        {
            "id": "new-2",
            "product_id": 3,
            "product_name": "Bread",
            "shopping_location_id": None,
            "shopping_location_name": "UNKNOWN",
            "status": "pending",
            "quantity_suggested": 1.0,
            "quantity_purchased": None,
            "quantity_unit": "unit",
            "current_stock": 0.0,
            "min_stock": 1.0,
            "last_price": None,
            "notes": "",
            "checked_at": None,
            "modified_at": "2024-01-01T00:00:00Z",
        },
    ]

    added = manager.add_items_bulk(instance_index, items_to_add)
    assert [item["product_id"] for item in added] == [2, 3]

    updated = manager.load_active_list(instance_index)
    assert updated["version"] == 2
    assert updated["location_order"] == [2, 3, "UNKNOWN"]


def test_bulk_add_rejects_duplicate_products(tmp_path: Path) -> None:
    instance_index = "bulk-add-dup"
    manager = ShoppingListManager(tmp_path)

    base_list = {
        "id": "list-1",
        "instance_index": instance_index,
        "version": 1,
        "created_at": "2024-01-01T00:00:00Z",
        "last_modified_at": "2024-01-01T00:00:00Z",
        "items": [],
        "location_order": [],
        "deleted_product_ids": [],
    }
    manager.save_active_list(instance_index, base_list)

    items_to_add = [
        {
            "id": "dup-1",
            "product_id": 5,
            "product_name": "Cereal",
            "shopping_location_id": 1,
            "shopping_location_name": "Store",
            "status": "pending",
            "quantity_suggested": 1.0,
            "quantity_purchased": None,
            "quantity_unit": "unit",
            "current_stock": 0.0,
            "min_stock": 1.0,
            "last_price": None,
            "notes": "",
            "checked_at": None,
            "modified_at": "2024-01-01T00:00:00Z",
        },
        {
            "id": "dup-2",
            "product_id": 5,
            "product_name": "Cereal Again",
            "shopping_location_id": 1,
            "shopping_location_name": "Store",
            "status": "pending",
            "quantity_suggested": 1.0,
            "quantity_purchased": None,
            "quantity_unit": "unit",
            "current_stock": 0.0,
            "min_stock": 1.0,
            "last_price": None,
            "notes": "",
            "checked_at": None,
            "modified_at": "2024-01-01T00:00:00Z",
        },
    ]

    with pytest.raises(ValueError):
        manager.add_items_bulk(instance_index, items_to_add)


def test_bulk_remove_updates_location_order(tmp_path: Path) -> None:
    instance_index = "bulk-remove"
    manager = ShoppingListManager(tmp_path)

    base_list = {
        "id": "list-1",
        "instance_index": instance_index,
        "version": 1,
        "created_at": "2024-01-01T00:00:00Z",
        "last_modified_at": "2024-01-01T00:00:00Z",
        "items": [
            {
                "id": "keep-1",
                "product_id": 1,
                "product_name": "Milk",
                "shopping_location_id": 2,
                "shopping_location_name": "Home",
                "status": "pending",
                "quantity_suggested": 1.0,
                "quantity_purchased": None,
                "quantity_unit": "unit",
                "current_stock": 0.0,
                "min_stock": 1.0,
                "last_price": None,
                "notes": "",
                "checked_at": None,
                "modified_at": "2024-01-01T00:00:00Z",
            },
            {
                "id": "remove-1",
                "product_id": 2,
                "product_name": "Eggs",
                "shopping_location_id": 3,
                "shopping_location_name": "Store",
                "status": "pending",
                "quantity_suggested": 1.0,
                "quantity_purchased": None,
                "quantity_unit": "unit",
                "current_stock": 0.0,
                "min_stock": 1.0,
                "last_price": None,
                "notes": "",
                "checked_at": None,
                "modified_at": "2024-01-01T00:00:00Z",
            },
        ],
        "location_order": [2, 3],
        "deleted_product_ids": [],
    }
    manager.save_active_list(instance_index, base_list)

    removed = manager.bulk_remove_items(instance_index, BulkRemoveRequest(item_ids=["remove-1"]))
    assert len(removed) == 1

    updated = manager.load_active_list(instance_index)
    assert updated["version"] == 2
    assert updated["location_order"] == [2]
    assert updated["deleted_product_ids"] == [2]


def test_bulk_update_requires_unique_items(tmp_path: Path) -> None:
    instance_index = "bulk-update-validation"
    manager = ShoppingListManager(tmp_path)

    base_list = {
        "id": "list-1",
        "instance_index": instance_index,
        "version": 1,
        "created_at": "2024-01-01T00:00:00Z",
        "last_modified_at": "2024-01-01T00:00:00Z",
        "items": [
            {
                "id": "item-1",
                "product_id": 1,
                "product_name": "Milk",
                "shopping_location_id": 2,
                "shopping_location_name": "Home",
                "status": "pending",
                "quantity_suggested": 1.0,
                "quantity_purchased": None,
                "quantity_unit": "unit",
                "current_stock": 0.0,
                "min_stock": 1.0,
                "last_price": None,
                "notes": "",
                "checked_at": None,
                "modified_at": "2024-01-01T00:00:00Z",
            }
        ],
        "location_order": [2],
        "deleted_product_ids": [],
    }
    manager.save_active_list(instance_index, base_list)

    with pytest.raises(ValueError):
        manager.bulk_update_items(instance_index, [])

    with pytest.raises(ValueError):
        manager.bulk_update_items(
            instance_index,
            [
                {"item_id": "item-1", "status": "purchased"},
                {"item_id": "item-1", "status": "pending"},
            ],
        )

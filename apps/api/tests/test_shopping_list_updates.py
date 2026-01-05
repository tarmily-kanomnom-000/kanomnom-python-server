import sys
from pathlib import Path

# Ensure src/ is on the import path when tests are run from the repo root.
PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from api.routes.grocy.shopping_list import _serialize_updates
from core.grocy.shopping_list_manager import ShoppingListManager
from models.shopping_list import BulkItemUpdate, BulkUpdateRequest


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

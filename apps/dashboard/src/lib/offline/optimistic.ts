import type {
  PendingAction,
  SnapshotPayload,
} from "@/lib/offline/types";
import type { ShoppingList, ShoppingListItem } from "@/lib/grocy/shopping-list-types";

export function applyOptimisticUpdate(
  list: ShoppingList,
  action: PendingAction,
): ShoppingList {
  const updatedList = { ...list };

  switch (action.action) {
    case "add_item":
      if (
        "item" in action.payload &&
        action.payload.item &&
        typeof action.payload.item === "object" &&
        "id" in action.payload.item &&
        "product_id" in action.payload.item
      ) {
        updatedList.items = [
          ...updatedList.items,
          action.payload.item as ShoppingListItem,
        ];
      }
      break;

    case "remove_item": {
      const ids = action.payload.item_ids;
      updatedList.items = updatedList.items.filter(
        (item) => !ids.includes(item.id),
      );
      break;
    }

    case "update_item":
      updatedList.items = updatedList.items.map((item) =>
        action.payload.updates.some((update: any) => update.item_id === item.id)
          ? {
              ...item,
              ...action.payload.updates.find(
                (update: any) => update.item_id === item.id,
              ),
            }
          : item,
      );
      break;

    case "complete_list":
      return updatedList;

    case "replay_snapshot":
      return (action.payload as SnapshotPayload).list;

    default:
      return updatedList;
  }

  updatedList.version = (updatedList.version || 1) + 1;
  updatedList.last_modified_at = new Date().toISOString();

  return updatedList;
}

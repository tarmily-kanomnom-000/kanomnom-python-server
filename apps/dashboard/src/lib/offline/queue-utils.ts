import type { ShoppingListItem } from "@/lib/grocy/shopping-list-types";
import type {
  PendingAction,
  SnapshotPayload,
  UpdateItemPayload,
} from "./types";

type Update = UpdateItemPayload["updates"][number];

export function mergePendingUpdates(
  existing: Update[] = [],
  incoming: Update[] = [],
  incomingTimestamp: number,
): Update[] {
  const byId = new Map<
    string,
    {
      data: Update;
      ts: number;
    }
  >();
  for (const update of existing) {
    if (update?.item_id) {
      const ts =
        typeof update.last_modified_at === "string"
          ? Date.parse(update.last_modified_at)
          : 0;
      byId.set(update.item_id, { data: update, ts });
    }
  }
  for (const update of incoming) {
    if (update?.item_id) {
      const existingEntry = byId.get(update.item_id);
      if (!existingEntry || existingEntry.ts <= incomingTimestamp) {
        byId.set(update.item_id, {
          data: { ...(existingEntry?.data ?? {}), ...update },
          ts: incomingTimestamp,
        });
      }
    }
  }
  return Array.from(byId.values()).map((entry) => entry.data);
}

export function mergeIntoSnapshot(
  snapshot: Extract<PendingAction, { action: "replay_snapshot" }>,
  incoming: Omit<PendingAction, "id" | "timestamp">,
  timestamp: number,
): Extract<PendingAction, { action: "replay_snapshot" }> {
  const payload = { ...(snapshot.payload ?? {}) } as SnapshotPayload;
  switch (incoming.action) {
    case "update_item":
      payload.updates = mergePendingUpdates(
        payload.updates,
        "updates" in incoming.payload && Array.isArray(incoming.payload.updates)
          ? incoming.payload.updates
          : [],
        timestamp,
      );
      break;
    case "add_item":
      // Without enriched item payloads, rely on replaying server-side add.
      break;
    case "remove_item":
      if (payload.list?.items) {
        const ids =
          "item_ids" in incoming.payload &&
          Array.isArray(incoming.payload.item_ids)
            ? incoming.payload.item_ids
            : [];
        if (ids.length > 0) {
          payload.list.items = payload.list.items.filter(
            (item: ShoppingListItem) => !ids.includes(item.id),
          );
        }
      }
      break;
    default:
      break;
  }
  return {
    ...snapshot,
    payload,
    timestamp,
  };
}

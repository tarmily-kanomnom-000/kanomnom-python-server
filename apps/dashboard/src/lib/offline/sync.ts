import type { ShoppingList } from "@/lib/grocy/shopping-list-types";

import {
  markSyncDrop,
  markSyncSuccess,
  readSyncQueue,
  removeFromSyncQueue,
  writeSyncQueue,
} from "./queue";
import { mergePendingUpdates } from "./queue-utils";
import { getOnlineStatus, isOffline, notifySyncInfo } from "./status";
import {
  clearCachedShoppingList,
  readCachedShoppingList,
  writeCachedShoppingList,
} from "./storage";
import {
  incrementFailureCount,
  isPermanentFailure,
  MAX_RETRIES,
  statusFromError,
} from "./sync-utils";
import type { PendingAction } from "./types";

async function refreshActiveListCache(instanceIndex: string): Promise<void> {
  const attempts = [0, 500, 1500];
  for (const delay of attempts) {
    if (delay) {
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
    try {
      const response = await fetch(
        `/api/grocy/${instanceIndex}/shopping-list/active`,
      );
      if (!response.ok) {
        continue;
      }
      const data = (await response.json()) as ShoppingList | null;
      if (data) {
        writeCachedShoppingList(instanceIndex, data);
      }
      return;
    } catch (error) {
      console.warn("Failed to refresh active shopping list cache", {
        instanceIndex,
        error,
        attemptDelay: delay,
      });
    }
  }
}

export async function fetchShoppingListWithCache(
  instanceIndex: string,
  fetcher: () => Promise<ShoppingList | null>,
): Promise<ShoppingList | null> {
  const cached = readCachedShoppingList(instanceIndex);
  if (isOffline()) {
    return cached;
  }

  try {
    const result = await fetcher();
    if (result) {
      writeCachedShoppingList(instanceIndex, result);
    } else {
      clearCachedShoppingList(instanceIndex);
    }
    return result;
  } catch (error) {
    if (cached !== null) {
      console.warn(
        "Failed to fetch shopping list, using cached version",
        error,
      );
      return cached;
    }
    throw error;
  }
}

function batchPendingActions(actions: PendingAction[]): PendingAction[] {
  const result: PendingAction[] = [];
  for (const action of actions) {
    const last = result[result.length - 1];
    const canMerge =
      last &&
      last.instanceIndex === action.instanceIndex &&
      last.action === action.action &&
      ["add_item", "remove_item", "update_item"].includes(action.action);
    if (!canMerge) {
      result.push(action);
      continue;
    }

    const mergedFailureCount =
      action.failureCount ?? last.failureCount ?? undefined;

    if (action.action === "add_item" && last.action === "add_item") {
      const previous =
        "items" in last.payload && Array.isArray(last.payload.items)
          ? last.payload.items
          : [];
      const incoming =
        "items" in action.payload && Array.isArray(action.payload.items)
          ? action.payload.items
          : [];
      result[result.length - 1] = {
        ...last,
        payload: { items: [...previous, ...incoming] },
        timestamp: Math.max(last.timestamp, action.timestamp),
        failureCount: mergedFailureCount,
      };
      continue;
    }

    if (action.action === "remove_item" && last.action === "remove_item") {
      const previous =
        "item_ids" in last.payload && Array.isArray(last.payload.item_ids)
          ? last.payload.item_ids
          : [];
      const incoming =
        "item_ids" in action.payload && Array.isArray(action.payload.item_ids)
          ? action.payload.item_ids
          : [];
      const merged = Array.from(new Set([...previous, ...incoming]));
      result[result.length - 1] = {
        ...last,
        payload: { item_ids: merged },
        timestamp: Math.max(last.timestamp, action.timestamp),
        failureCount: mergedFailureCount,
      };
      continue;
    }

    if (action.action === "update_item" && last.action === "update_item") {
      const mergedUpdates = mergePendingUpdates(
        Array.isArray(last.payload.updates) ? last.payload.updates : [],
        Array.isArray(action.payload.updates) ? action.payload.updates : [],
        action.timestamp,
      );
      result[result.length - 1] = {
        ...last,
        payload: { updates: mergedUpdates },
        timestamp: action.timestamp,
        failureCount: mergedFailureCount,
      };
      continue;
    }

    result.push(action);
  }
  return result;
}

export async function syncPendingActions(): Promise<void> {
  if (!getOnlineStatus()) {
    return;
  }

  const queue = readSyncQueue();
  if (queue.length === 0) {
    return;
  }
  notifySyncInfo(queue.length);

  const snapshotByInstance = new Map<string, PendingAction>();
  for (const entry of queue) {
    if (entry.action === "replay_snapshot") {
      const existing = snapshotByInstance.get(entry.instanceIndex);
      if (!existing || entry.timestamp > existing.timestamp) {
        snapshotByInstance.set(entry.instanceIndex, entry);
      }
    }
  }

  if (snapshotByInstance.size > 0) {
    for (const [instanceIndex, snapshot] of snapshotByInstance.entries()) {
      const remaining = readSyncQueue().filter(
        (action) =>
          !(
            action.instanceIndex === instanceIndex &&
            action.action === "replay_snapshot"
          ),
      );
      writeSyncQueue(remaining);
      await executePendingAction(snapshot);
      console.log("Synced snapshot for instance", {
        instanceIndex,
        updates:
          "updates" in snapshot.payload &&
          Array.isArray(snapshot.payload.updates)
            ? snapshot.payload.updates.length
            : 0,
      });
    }
  }

  const refreshedQueue = readSyncQueue();
  if (refreshedQueue.length === 0) {
    return;
  }

  const batched = batchPendingActions(refreshedQueue);

  console.log(`Syncing ${batched.length} pending shopping list actions...`);
  notifySyncInfo(batched.length);

  const refreshAfter = new Set<string>();

  for (const action of batched) {
    try {
      await executePendingAction(action);
      removeFromSyncQueue(action.id);
      console.log(`Synced action: ${action.action}`, action);
      markSyncSuccess(readSyncQueue().length);
      if (
        action.action === "add_item" ||
        action.action === "remove_item" ||
        action.action === "update_item" ||
        action.action === "generate_list" ||
        action.action === "replay_snapshot"
      ) {
        refreshAfter.add(action.instanceIndex);
      }
    } catch (error) {
      const status = statusFromError(error);
      const isPermanent = isPermanentFailure(status);
      const updatedAction = incrementFailureCount(action);
      const failures = updatedAction.failureCount ?? 0;

      if (isPermanent || failures >= MAX_RETRIES) {
        console.error(
          `Dropping failed action after ${failures} attempts: ${action.action}`,
          { status, error, instanceIndex: action.instanceIndex },
        );
        removeFromSyncQueue(action.id);
        markSyncDrop(readSyncQueue().length);
        continue;
      }
      console.warn(
        `Requeueing failed action (${failures}/${MAX_RETRIES}): ${action.action}`,
        { status, error },
      );
      const remaining = readSyncQueue().filter(
        (entry) => entry.id !== action.id,
      );
      remaining.push(updatedAction);
      writeSyncQueue(remaining);
      notifySyncInfo(remaining.length, "requeued_failed_action");
    }
  }

  for (const instanceIndex of refreshAfter) {
    await refreshActiveListCache(instanceIndex);
  }
}

async function executePendingAction(action: PendingAction): Promise<void> {
  const { instanceIndex, payload } = action;

  switch (action.action) {
    case "replay_snapshot": {
      const updates =
        "updates" in payload && Array.isArray(payload.updates)
          ? payload.updates
          : [];
      if (!updates || updates.length === 0) {
        return;
      }
      const response = await fetch(
        `/api/grocy/${instanceIndex}/shopping-list/items/bulk`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ updates }),
        },
      );
      if (
        response.ok &&
        "list" in payload &&
        payload.list &&
        typeof payload.list === "object" &&
        "id" in payload.list
      ) {
        writeCachedShoppingList(instanceIndex, payload.list as ShoppingList);
      }
      return;
    }
    case "add_item": {
      const items =
        "items" in payload && Array.isArray(payload.items) ? payload.items : [];
      if (items.length === 0) {
        return;
      }
      await fetch(`/api/grocy/${instanceIndex}/shopping-list/items/bulk`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(items),
      });
      break;
    }

    case "remove_item": {
      const itemIds =
        "item_ids" in payload && Array.isArray(payload.item_ids)
          ? payload.item_ids
          : [];
      await fetch(`/api/grocy/${instanceIndex}/shopping-list/items/remove`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          item_ids: itemIds,
        }),
      });
      break;
    }

    case "update_item":
      await fetch(`/api/grocy/${instanceIndex}/shopping-list/items/bulk`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          updates:
            "updates" in payload && Array.isArray(payload.updates)
              ? payload.updates
              : [],
        }),
      });
      break;

    case "complete_list":
      try {
        const response = await fetch(
          `/api/grocy/${instanceIndex}/shopping-list/active/complete`,
          {
            method: "POST",
          },
        );
        if (!response.ok && response.status !== 404) {
          throw new Error(`Complete list failed: ${response.status}`);
        }
      } finally {
        await refreshActiveListCache(instanceIndex);
        clearCachedShoppingList(instanceIndex);
      }
      break;

    case "generate_list":
      await fetch(`/api/grocy/${instanceIndex}/shopping-list/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      break;
  }
}

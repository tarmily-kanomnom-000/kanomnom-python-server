import type { ShoppingList } from "@/lib/grocy/shopping-list-types";

import {
  markSyncDrop,
  markSyncSuccess,
  readSyncQueue,
  removeFromSyncQueue,
  writeSyncQueue,
} from "./queue";
import {
  clearCachedShoppingList,
  readCachedShoppingList,
  writeCachedShoppingList,
} from "./storage";
import { getOnlineStatus, notifySyncInfo } from "./status";
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

export function isOffline(): boolean {
  return !getOnlineStatus();
}

export function isOnline(): boolean {
  return getOnlineStatus();
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
      console.warn("Failed to fetch shopping list, using cached version", error);
      return cached;
    }
    throw error;
  }
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

  const mergeUpdates = (existing: any[] = [], incoming: any[] = []): any[] => {
    const byId = new Map<string, any>();
    for (const update of existing) {
      if (update?.item_id) {
        byId.set(update.item_id, update);
      }
    }
    for (const update of incoming) {
      if (update?.item_id) {
        byId.set(update.item_id, { ...byId.get(update.item_id), ...update });
      }
    }
    return Array.from(byId.values());
  };

  const batched: PendingAction[] = [];
  for (const action of refreshedQueue) {
    if (action.action !== "update_item") {
      batched.push(action);
      continue;
    }
    const last = batched[batched.length - 1];
    const canMergeWithLast =
      last &&
      last.action === "update_item" &&
      last.instanceIndex === action.instanceIndex;
    if (!canMergeWithLast) {
      batched.push(action);
      continue;
    }
    const mergedUpdates = mergeUpdates(
      Array.isArray(last.payload.updates) ? last.payload.updates : [],
      Array.isArray(action.payload.updates) ? action.payload.updates : [],
    );
    batched[batched.length - 1] = {
      ...last,
      payload: { updates: mergedUpdates },
      timestamp: action.timestamp,
    };
  }

  console.log(`Syncing ${batched.length} pending shopping list actions...`);
  notifySyncInfo(batched.length);

  const MAX_RETRIES = 3;
  for (const action of batched) {
    try {
      await executePendingAction(action);
      removeFromSyncQueue(action.id);
      console.log(`Synced action: ${action.action}`, action);
      markSyncSuccess(readSyncQueue().length);
    } catch (error) {
      const failures = (action.failureCount ?? 0) + 1;
      const isAxiosResponse =
        typeof error === "object" &&
        error !== null &&
        "status" in (error as any);
      const status = isAxiosResponse ? (error as any).status : undefined;
      const isPermanent = status && status >= 400 && status < 500;

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
      const remaining = readSyncQueue().filter((entry) => entry.id !== action.id);
      remaining.push({
        ...action,
        failureCount: failures,
        timestamp: Date.now(),
      });
      writeSyncQueue(remaining);
      notifySyncInfo(remaining.length, "requeued_failed_action");
    }
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
    case "add_item":
      await fetch(`/api/grocy/${instanceIndex}/shopping-list/items`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      break;

    case "remove_item":
      await fetch(`/api/grocy/${instanceIndex}/shopping-list/items/remove`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          item_ids:
            "item_ids" in payload && Array.isArray(payload.item_ids)
              ? payload.item_ids
              : [],
        }),
      });
      break;

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
      await refreshActiveListCache(instanceIndex);
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
      await refreshActiveListCache(instanceIndex);
      break;
  }
}

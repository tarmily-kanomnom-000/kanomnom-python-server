import type { ShoppingList } from "@/lib/grocy/shopping-list-types";
import { mergeIntoSnapshot, mergePendingUpdates } from "./queue-utils";
import {
  hydrateSyncSnapshot,
  notifySyncInfo,
  recordSyncDrop,
  setLastSyncAt,
} from "./status";
import { readCache, syncQueueKey, writeCache } from "./storage";
import type {
  AddItemPayload,
  PendingAction,
  SnapshotPayload,
  UpdateItemPayload,
} from "./types";

export function readSyncQueue(): PendingAction[] {
  const queue = readCache<PendingAction[]>(syncQueueKey());
  return queue ?? [];
}

export function writeSyncQueue(queue: PendingAction[]): void {
  writeCache(syncQueueKey(), queue);
  notifySyncInfo(queue.length);
}

export function removeFromSyncQueue(actionId: string): void {
  const queue = readSyncQueue();
  const filtered = queue.filter((entry) => entry.id !== actionId);
  writeSyncQueue(filtered);
}

export function clearSyncQueue(): void {
  writeSyncQueue([]);
}

export function addToSyncQueue(
  action: Omit<PendingAction, "id" | "timestamp">,
): void {
  if (action.action === "update_item" || action.action === "replay_snapshot") {
    const updates =
      "updates" in action.payload && Array.isArray(action.payload.updates)
        ? action.payload.updates
        : [];
    if (updates.some((update) => !update?.item_id)) {
      console.warn("Dropping update with missing item_id", { action });
      return;
    }
  }
  if (
    action.action === "remove_item" &&
    "item_ids" in action.payload &&
    Array.isArray(action.payload.item_ids) &&
    action.payload.item_ids.length === 0
  ) {
    console.warn("Dropping remove_item with no ids", { action });
    return;
  }

  let queue = readSyncQueue();

  if (action.action === "replay_snapshot") {
    const existingIndex = queue.findIndex(
      (entry) =>
        entry.instanceIndex === action.instanceIndex &&
        entry.action === "replay_snapshot",
    );

    if (existingIndex >= 0) {
      const existing = queue[existingIndex];
      const latestGranularTs = Math.max(
        0,
        ...queue
          .filter(
            (entry) =>
              entry.instanceIndex === action.instanceIndex &&
              entry.action === "update_item",
          )
          .flatMap((entry) =>
            "updates" in entry.payload && Array.isArray(entry.payload.updates)
              ? entry.payload.updates.map((update: any) =>
                  typeof update.last_modified_at === "string"
                    ? Date.parse(update.last_modified_at)
                    : entry.timestamp,
                )
              : [],
          ),
      );
      const incomingFiltered =
        ("updates" in action.payload && Array.isArray(action.payload.updates)
          ? action.payload.updates
          : []
        ).filter((update: any) => {
          const ts =
            typeof update.last_modified_at === "string"
              ? Date.parse(update.last_modified_at)
              : Date.now();
          return ts >= latestGranularTs;
        }) ?? [];
      const mergedUpdates = mergePendingUpdates(
        "updates" in existing.payload && Array.isArray(existing.payload.updates)
          ? existing.payload.updates
          : [],
        incomingFiltered,
        Date.now(),
      );
      const existingSnapshot = existing as Extract<
        PendingAction,
        { action: "replay_snapshot" }
      >;
      const incomingList =
        "list" in action.payload &&
        action.payload.list &&
        typeof action.payload.list === "object" &&
        "id" in action.payload.list
          ? (action.payload.list as ShoppingList)
          : existingSnapshot.payload.list;
      const mergedPayload: SnapshotPayload = {
        updates: mergedUpdates,
        list: incomingList,
      };
      queue[existingIndex] = {
        ...existingSnapshot,
        payload: mergedPayload,
        timestamp: Date.now(),
      };
      writeSyncQueue(queue);
      return;
    }

    queue = queue.filter(
      (entry) =>
        !(
          entry.instanceIndex === action.instanceIndex &&
          (entry.action === "replay_snapshot" ||
            entry.action === "update_item" ||
            entry.action === "add_item" ||
            entry.action === "remove_item")
        ),
    );
  } else {
    const existingSnapshotIndex = queue.findIndex(
      (entry) =>
        entry.instanceIndex === action.instanceIndex &&
        entry.action === "replay_snapshot",
    );
    if (existingSnapshotIndex >= 0) {
      if (!["add_item", "remove_item", "update_item"].includes(action.action)) {
        const newAction: PendingAction = {
          ...(action as any),
          id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          timestamp: Date.now(),
        };
        queue.push(newAction);
        writeSyncQueue(queue);
        return;
      }
      const incomingTs = Date.now();
      const existing = queue[existingSnapshotIndex] as Extract<
        PendingAction,
        { action: "replay_snapshot" }
      >;
      const updatedSnapshot = mergeIntoSnapshot(existing, action, incomingTs);
      const latestPayloadTs = Math.max(
        incomingTs,
        ...(existing.payload?.updates ?? []).map((update: any) =>
          typeof update.last_modified_at === "string"
            ? Date.parse(update.last_modified_at)
            : 0,
        ),
      );
      queue[existingSnapshotIndex] = {
        ...updatedSnapshot,
        timestamp: Math.max(updatedSnapshot.timestamp, latestPayloadTs),
      };
      writeSyncQueue(queue);
      return;
    }
  }

  const newAction: PendingAction =
    action.action === "complete_list" || action.action === "generate_list"
      ? {
          id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          timestamp: Date.now(),
          action: action.action,
          instanceIndex: action.instanceIndex,
          payload: action.payload as Record<string, unknown>,
          failureCount: action.failureCount,
        }
      : action.action === "add_item"
        ? {
            id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            timestamp: Date.now(),
            action: "add_item",
            instanceIndex: action.instanceIndex,
            payload: action.payload as AddItemPayload,
            failureCount: action.failureCount,
          }
        : action.action === "remove_item"
          ? {
              id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
              timestamp: Date.now(),
              action: "remove_item",
              instanceIndex: action.instanceIndex,
              payload: action.payload as { item_ids: string[] },
              failureCount: action.failureCount,
            }
          : action.action === "update_item"
            ? {
                id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                timestamp: Date.now(),
                action: "update_item",
                instanceIndex: action.instanceIndex,
                payload: action.payload as UpdateItemPayload,
                failureCount: action.failureCount,
              }
            : {
                id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                timestamp: Date.now(),
                action: "replay_snapshot",
                instanceIndex: action.instanceIndex,
                payload: action.payload as SnapshotPayload,
                failureCount: action.failureCount,
              };
  queue.push(newAction);
  writeSyncQueue(queue);

  console.log("Queued offline action", {
    action: newAction.action,
    instanceIndex: newAction.instanceIndex,
    queuedAt: newAction.timestamp,
    queueSize: queue.length,
  });
}

export function markSyncSuccess(queueSize: number): void {
  setLastSyncAt(Date.now());
  notifySyncInfo(queueSize, null);
}

export function markSyncDrop(queueSize: number): void {
  recordSyncDrop();
  notifySyncInfo(queueSize, "dropped_failed_action");
}

const initialQueueSize =
  typeof window !== "undefined" ? readSyncQueue().length : 0;
hydrateSyncSnapshot(initialQueueSize);

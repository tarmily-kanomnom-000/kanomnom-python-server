import type {
  BulkItemUpdate,
  ShoppingList,
} from "@/lib/grocy/shopping-list-types";
import {
  syncPendingActions,
  writeCachedShoppingList,
} from "@/lib/offline/shopping-list-cache";

/**
 * Persist the current list snapshot to the offline cache.
 */
export function persistShoppingListCache(
  instanceIndex: string,
  list: ShoppingList,
): void {
  writeCachedShoppingList(instanceIndex, list);
}

/**
 * Dispatch bulk updates with offline-aware behavior:
 * - Offline: queue via provided queueFn and write cache
 * - Online: PATCH to bulk endpoint and write cache
 */
export async function dispatchShoppingListUpdates(options: {
  instanceIndex: string;
  list: ShoppingList;
  updates: BulkItemUpdate[];
  isOnline: boolean;
  queueFn: (list: ShoppingList, updates: BulkItemUpdate[]) => Promise<void>;
}): Promise<void> {
  const { instanceIndex, list, updates, isOnline, queueFn } = options;
  if (!list || updates.length === 0) {
    return;
  }

  console.info("dispatchShoppingListUpdates", {
    instanceIndex,
    updates: updates.length,
    isOnline,
  });

  if (!isOnline) {
    await queueFn(list, updates);
    writeCachedShoppingList(instanceIndex, list);
    return;
  }

  try {
    const response = await fetch(
      `/api/grocy/${instanceIndex}/shopping-list/items/bulk`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ updates }),
      },
    );

    if (!response.ok) {
      const detail = await response.text();
      const error = new Error(detail || "Failed to update items") as Error & {
        status?: number;
      };
      error.status = response.status;
      throw error;
    }

    writeCachedShoppingList(instanceIndex, list);
  } catch (error) {
    const status =
      typeof error === "object" && error !== null && "status" in error
        ? Number((error as any).status)
        : undefined;
    const isNetworkError =
      error instanceof TypeError || status === 0 || Number.isNaN(status);

    // Treat transient network drops like offline: queue locally and persist.
    if (isOnline && isNetworkError) {
      console.warn("Network drop detected; queueing shopping list updates", {
        instanceIndex,
        updates: updates.length,
      });
      await queueFn(list, updates);
      writeCachedShoppingList(instanceIndex, list);
      // We still think we're "online", so proactively attempt to flush the queue.
      // If the network is still down, sync will requeue with backoff.
      void syncPendingActions();
      return;
    }

    throw error;
  }
}

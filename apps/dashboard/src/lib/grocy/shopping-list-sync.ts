import { runGrocyMutation } from "@/lib/grocy/mutation-runner";
import type {
  BulkItemUpdate,
  ShoppingList,
} from "@/lib/grocy/shopping-list-types";
import {
  syncPendingActions,
  writeCachedShoppingList,
} from "@/lib/offline/shopping-list-cache";
import { isOffline } from "@/lib/offline/status";

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
  queueFn: (list: ShoppingList, updates: BulkItemUpdate[]) => Promise<void>;
}): Promise<void> {
  const { instanceIndex, list, updates, queueFn } = options;
  if (!list || updates.length === 0) {
    return;
  }

  console.info("dispatchShoppingListUpdates", {
    instanceIndex,
    updates: updates.length,
    isOnline: !isOffline(),
  });

  await runGrocyMutation<void>({
    request: async () => {
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
    },
    offlineFallback: async () => {
      await queueFn(list, updates);
      writeCachedShoppingList(instanceIndex, list);
      void syncPendingActions();
    },
  });
}

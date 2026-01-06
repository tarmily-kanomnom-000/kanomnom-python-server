import { useCallback, useEffect } from "react";
import {
  dispatchShoppingListUpdates,
  persistShoppingListCache,
} from "@/lib/grocy/shopping-list-sync";
import type {
  BulkItemUpdate,
  ShoppingList,
  ShoppingListItem,
} from "@/lib/grocy/shopping-list-types";
import {
  addToSyncQueue,
  clearCachedShoppingList,
  fetchShoppingListWithCache,
  isOffline,
  setupOnlineEventListeners,
  syncPendingActions,
} from "@/lib/offline/shopping-list-cache";
import { useSyncStatus } from "./useSyncStatus";

export function useOfflineShoppingList(instanceIndex: string) {
  const syncStatus = useSyncStatus();

  useEffect(() => {
    // Setup the sync listeners once
    setupOnlineEventListeners();
  }, []);

  useEffect(() => {
    if (syncStatus.isOnline) {
      void syncPendingActions();
    }
  }, [syncStatus.isOnline]);

  const loadActiveListWithCache =
    useCallback(async (): Promise<ShoppingList | null> => {
      // If we have queued actions and we're online, flush them before fetching
      if (!isOffline() && syncStatus.queueSize > 0) {
        await syncPendingActions();
      }
      return fetchShoppingListWithCache(instanceIndex, async () => {
        const response = await fetch(
          `/api/grocy/${instanceIndex}/shopping-list/active`,
        );

        if (!response.ok) {
          throw new Error("Failed to load shopping list");
        }

        return await response.json();
      });
    }, [instanceIndex, syncStatus.queueSize]);

  const generateListWithCache = useCallback(
    async (merge: boolean = false): Promise<ShoppingList> => {
      if (isOffline()) {
        throw new Error("Cannot generate list while offline");
      }

      const response = await fetch(
        `/api/grocy/${instanceIndex}/shopping-list/generate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ merge_with_existing: merge }),
        },
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to generate list");
      }

      const list = await response.json();
      persistShoppingListCache(instanceIndex, list);
      return list;
    },
    [instanceIndex],
  );

  const completeListWithCache = useCallback(async (): Promise<{
    message: string;
  }> => {
    if (isOffline()) {
      // Queue for later
      addToSyncQueue({
        action: "complete_list",
        instanceIndex,
        payload: {},
      });
      clearCachedShoppingList(instanceIndex);
      return { message: "List completion queued (offline)" };
    }

    const response = await fetch(
      `/api/grocy/${instanceIndex}/shopping-list/active/complete`,
      {
        method: "POST",
      },
    );

    if (!response.ok) {
      throw new Error("Failed to complete list");
    }

    const data = await response.json();
    clearCachedShoppingList(instanceIndex);
    return data;
  }, [instanceIndex]);

  const addItemWithCache = useCallback(
    async (
      list: ShoppingList | null,
      productId: number,
      quantity: number,
      optimisticItem: ShoppingListItem | null = null,
    ): Promise<ShoppingList | null> => {
      const payload = { items: [{ product_id: productId, quantity }] };

      if (isOffline()) {
        // Queue for later sync
        addToSyncQueue({
          action: "add_item",
          instanceIndex,
          payload,
        });
        if (list && optimisticItem) {
          const optimisticList: ShoppingList = {
            ...list,
            items: [...list.items, optimisticItem],
            last_modified_at: optimisticItem.modified_at,
            version: (list.version ?? 1) + 1,
          };
          persistShoppingListCache(instanceIndex, optimisticList);
          return optimisticList;
        }
        // Attempt to return cached list if available; item will be added when online
        return await loadActiveListWithCache();
      }

      const response = await fetch(
        `/api/grocy/${instanceIndex}/shopping-list/items/bulk`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload.items),
        },
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to add item");
      }

      // Reload the list to get the updated version
      const updatedList = await loadActiveListWithCache();
      if (updatedList) {
        persistShoppingListCache(instanceIndex, updatedList);
        return updatedList;
      }

      throw new Error("Failed to reload list after adding item");
    },
    [instanceIndex, loadActiveListWithCache],
  );

  const updateItemsWithCache = useCallback(
    async (
      list: ShoppingList,
      updates: BulkItemUpdate[],
      isOnlineOverride?: boolean,
    ): Promise<void> => {
      const payload = { updates };
      const shouldSendOnline = isOnlineOverride ?? !isOffline();
      console.debug("updateItemsWithCache invoked", {
        updates: payload.updates.length,
        shouldSendOnline,
        isOffline: isOffline(),
      });

      // Offline: queue and persist optimistic cache only.
      if (!shouldSendOnline) {
        addToSyncQueue({
          action: "replay_snapshot",
          instanceIndex,
          payload: {
            list,
            updates,
          },
        });
        persistShoppingListCache(instanceIndex, list);
        return;
      }

      // Online: fire the bulk PATCH immediately.
      console.debug("Dispatching shopping list bulk update", payload);
      await dispatchShoppingListUpdates({
        instanceIndex,
        list,
        updates,
        queueFn: async (l, u) => {
          addToSyncQueue({
            action: "update_item",
            instanceIndex,
            payload: { updates: u },
          });
          persistShoppingListCache(instanceIndex, l);
        },
      });
    },
    [instanceIndex],
  );

  const deleteItemWithCache = useCallback(
    async (
      list: ShoppingList,
      itemIds: string | string[],
      isOnlineOverride?: boolean,
    ): Promise<void> => {
      // Optimistically update local state first (handled by caller)
      const ids = Array.isArray(itemIds) ? itemIds : [itemIds];
      const shouldSendOnline = isOnlineOverride ?? !isOffline();
      console.debug("deleteItemWithCache", {
        shouldSendOnline,
        ids,
        isOffline: isOffline(),
      });
      if (!shouldSendOnline) {
        // Queue for later sync
        addToSyncQueue({
          action: "remove_item",
          instanceIndex,
          payload: { item_ids: ids },
        });
        // Update cache with optimistic deletion
        if (list) {
          persistShoppingListCache(instanceIndex, list);
        }
        return;
      }

      // Online - send to server
      console.info("deleteItemWithCache sending online remove", {
        instanceIndex,
        ids,
        endpoint: `/api/grocy/${instanceIndex}/shopping-list/items/remove`,
      });
      const response = await fetch(
        `/api/grocy/${instanceIndex}/shopping-list/items/remove`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ item_ids: ids }),
        },
      );

      if (!response.ok) {
        console.error("deleteItemWithCache remove failed", {
          status: response.status,
        });
        throw new Error("Failed to delete item");
      }

      if (list) {
        persistShoppingListCache(instanceIndex, list);
      }
    },
    [instanceIndex],
  );

  return {
    isOnline: syncStatus.isOnline,
    isPersistenceDegraded: syncStatus.persistenceDegraded,
    loadActiveListWithCache,
    generateListWithCache,
    completeListWithCache,
    addItemWithCache,
    updateItemsWithCache,
    deleteItemWithCache,
  };
}

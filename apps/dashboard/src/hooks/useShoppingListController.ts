import { useCallback, useEffect, useMemo, useState } from "react";
import { useConnectivityStatus } from "@/hooks/useConnectivityStatus";
import { useLatest } from "@/hooks/useLatest";
import { fetchGrocyProducts } from "@/lib/grocy/client";
import { bulkAddShoppingListItems } from "@/lib/grocy/shopping-list-client";
import { dispatchShoppingListUpdates } from "@/lib/grocy/shopping-list-sync";
import type {
  BulkItemUpdate,
  ItemStatus,
  ItemUpdate,
  ShoppingList,
  ShoppingListItem,
} from "@/lib/grocy/shopping-list-types";
import type { GrocyProductInventoryEntry } from "@/lib/grocy/types";
import { useOfflineShoppingList } from "./useOfflineShoppingList";
import { useScrollPreserver } from "./useScrollPreserver";

export type ShoppingListSection = {
  locationKey: string;
  locationName: string;
  items: ShoppingListItem[];
  purchasedCount: number;
  totalCount: number;
  allChecked: boolean;
  someChecked: boolean;
};

type ControllerState = {
  isOnline: boolean;
  isLoading: boolean;
  error: string | null;
  status: { level: "info" | "error"; message: string } | null;
  list: ShoppingList | null;
  products: GrocyProductInventoryEntry[];
  sections: ShoppingListSection[];
  purchasedCount: number;
  totalCount: number;
  progress: number;
};

type ControllerActions = {
  clearError: () => void;
  clearStatus: () => void;
  reloadList: () => Promise<void>;
  generateList: (merge: boolean) => Promise<ShoppingList | undefined>;
  completeList: () => Promise<string>;
  updateItem: (itemId: string, updates: ItemUpdate) => Promise<void>;
  bulkCheckSection: (locationKey: string) => Promise<void>;
  bulkUncheckSection: (locationKey: string) => Promise<void>;
  bulkRemoveChecked: () => Promise<void>;
  bulkUncheckAll: () => Promise<void>;
  addItem: (productId: number, quantity: number) => Promise<void>;
  bulkAddItems: (
    items: Array<{ product_id: number; quantity: number }>,
  ) => Promise<void>;
  removeItems: (itemIds: string[]) => Promise<void>;
  appendItem: (item: ShoppingListItem) => void;
};

export function useShoppingListController(
  instanceIndex: string,
): ControllerState & ControllerActions {
  const PURCHASED_STATUS: ItemStatus = "purchased";
  const PENDING_STATUS: ItemStatus = "pending";
  const connectivity = useConnectivityStatus();

  const locationKeyForItem = useCallback(
    (item: ShoppingListItem): string =>
      item.shopping_location_id?.toString() ??
      item.shopping_location_name ??
      "UNKNOWN",
    [],
  );

  const {
    loadActiveListWithCache,
    generateListWithCache,
    completeListWithCache,
    updateItemsWithCache,
    deleteItemWithCache,
    addItemWithCache,
  } = useOfflineShoppingList(instanceIndex);
  const online = connectivity.online;

  const [products, setProducts] = useState<GrocyProductInventoryEntry[]>([]);
  const [list, setList] = useState<ShoppingList | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<{
    level: "info" | "error";
    message: string;
  } | null>(null);
  const keepScrollPosition = useScrollPreserver();
  const listRef = useLatest(list);

  const productGroupById = useMemo(() => {
    const lookup = new Map<number, string | null>();
    for (const product of products) {
      lookup.set(product.id, product.product_group_name ?? "Ungrouped");
    }
    return lookup;
  }, [products]);

  const loadProducts = useCallback(async () => {
    try {
      const data = await fetchGrocyProducts(instanceIndex);
      setProducts(data);
    } catch (err) {
      // Log for debugging but do not block UX
      console.error("Failed to load products for search:", err);
    }
  }, [instanceIndex]);

  const reloadList = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await loadActiveListWithCache();
      setList(data);
    } catch (err) {
      const message = online
        ? "Failed to load shopping list"
        : "Offline - no cached shopping list available";
      setError(message);
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [online, loadActiveListWithCache]);

  useEffect(() => {
    void reloadList();
    void loadProducts();
  }, [reloadList, loadProducts]);

  const buildItemMutations = useCallback(
    (
      baseList: ShoppingList | null,
      mutations: Array<{ id: string; updates: ItemUpdate }>,
    ): {
      nextList: ShoppingList;
      payload: BulkItemUpdate[];
    } | null => {
      if (!baseList || mutations.length === 0) {
        return null;
      }
      const timestamp = new Date().toISOString();
      const payload: BulkItemUpdate[] = mutations.map(({ id, updates }) => {
        const { quantity_purchased, ...rest } = updates;
        const normalized: BulkItemUpdate = {
          item_id: id,
          ...rest,
          last_modified_at: timestamp,
        };
        if (quantity_purchased !== undefined && quantity_purchased !== null) {
          normalized.quantity_purchased = quantity_purchased;
        }
        return normalized;
      });
      const nextList: ShoppingList = {
        ...baseList,
        items: baseList.items.map((item) => {
          const mutation = mutations.find((m) => m.id === item.id);
          return mutation
            ? { ...item, ...mutation.updates, last_modified_at: timestamp }
            : item;
        }),
      };
      return { nextList, payload };
    },
    [],
  );

  const sendBulkUpdates = useCallback(
    async (
      listSnapshot: ShoppingList | null,
      updates: BulkItemUpdate[],
      onlineOverride?: boolean,
    ) => {
      if (updates.length === 0) {
        return;
      }

      const effectiveList = listSnapshot;
      if (!effectiveList) {
        return;
      }
      const shouldSendOnline = onlineOverride ?? online;

      console.debug("sendBulkUpdates", {
        updates,
        shouldSendOnline,
        hasEffectiveList: Boolean(effectiveList),
      });

      await dispatchShoppingListUpdates({
        instanceIndex,
        list: effectiveList,
        updates,
        queueFn: async (listToQueue, updatesToQueue) =>
          updateItemsWithCache(listToQueue, updatesToQueue, false),
      });
    },
    [instanceIndex, online, updateItemsWithCache],
  );

  const generateList = useCallback(
    async (merge: boolean): Promise<ShoppingList | undefined> => {
      setIsLoading(true);
      setError(null);

      try {
        const data = await generateListWithCache(merge);
        setList(data);
        return data;
      } catch (err) {
        const errorMessage =
          err instanceof Error
            ? err.message
            : "Failed to generate shopping list";
        setError(errorMessage);
        console.error(err);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [generateListWithCache],
  );

  const completeList = useCallback(async (): Promise<string> => {
    setError(null);

    try {
      const result = await completeListWithCache();
      setList(null);
      return result.message ?? "Shopping list completed!";
    } catch (err) {
      setError("Failed to complete shopping list");
      console.error(err);
      throw err;
    }
  }, [completeListWithCache]);

  const updateItem = useCallback(
    async (itemId: string, updates: ItemUpdate) => {
      console.info("updateItem called", { itemId, updates, online });
      const current = list ?? listRef.current;
      const mutation = buildItemMutations(current, [{ id: itemId, updates }]);
      if (!mutation) {
        return;
      }
      const { nextList, payload } = mutation;
      keepScrollPosition(() => setList(nextList));

      try {
        await sendBulkUpdates(nextList, payload, online);
      } catch (err) {
        console.error("Failed to persist item update:", err);
        if (online) {
          await reloadList();
          alert("Failed to update item");
        }
      }
    },
    [
      buildItemMutations,
      keepScrollPosition,
      list,
      listRef,
      reloadList,
      sendBulkUpdates,
      online,
    ],
  );

  const removeItems = useCallback(
    async (itemIds: string[]) => {
      let optimistic: ShoppingList | null = null;

      setList((prev) => {
        if (!prev) {
          return prev;
        }
        optimistic = {
          ...prev,
          items: prev.items.filter((item) => !itemIds.includes(item.id)),
        };
        return optimistic;
      });

      if (!optimistic) {
        return;
      }

      try {
        await deleteItemWithCache(optimistic, itemIds, connectivity.online);
      } catch (err) {
        console.error("Failed to delete items:", err);
        if (online) {
          await reloadList();
          setStatus({
            level: "error",
            message: "Failed to delete items; list reloaded.",
          });
        }
      }
    },
    [deleteItemWithCache, online, reloadList, connectivity.online],
  );

  const bulkCheckSection = useCallback(
    async (locationKey: string) => {
      console.info("bulkCheckSection invoked", { locationKey, online });
      const checked_at = new Date().toISOString();
      const current = list ?? listRef.current;
      const targets =
        current?.items.filter(
          (item) =>
            locationKeyForItem(item) === locationKey &&
            item.status === "pending",
        ) ?? [];
      if (!current || targets.length === 0) {
        console.info("bulkCheckSection skipped - no pending items");
        return;
      }

      console.info("bulkCheckSection pendingItems", {
        count: targets.length,
        ids: targets.map((i) => i.id),
      });

      const mutation = buildItemMutations(
        current,
        targets.map((item) => ({
          id: item.id,
          updates: { status: PURCHASED_STATUS, checked_at },
        })),
      );
      if (!mutation) {
        return;
      }

      const { nextList, payload: updates } = mutation;
      keepScrollPosition(() => setList(nextList));
      console.debug("bulkCheckSection sending updates", updates);

      try {
        console.debug("bulkCheckSection dispatching via sendBulkUpdates");
        await sendBulkUpdates(nextList, updates, online);
      } catch (err) {
        console.error("Error bulk updating items:", err);
        if (online) {
          await reloadList();
          alert("Failed to update items");
        }
      }
    },
    [
      buildItemMutations,
      online,
      keepScrollPosition,
      list,
      listRef,
      locationKeyForItem,
      reloadList,
      sendBulkUpdates,
    ],
  );

  const bulkUncheckSection = useCallback(
    async (locationKey: string) => {
      console.info("bulkUncheckSection invoked", { locationKey, online });
      const current = list ?? listRef.current;
      const targets =
        current?.items.filter(
          (item) =>
            locationKeyForItem(item) === locationKey &&
            (item.status === "purchased" || item.status === "unavailable"),
        ) ?? [];
      if (!current || targets.length === 0) {
        console.info(
          "bulkUncheckSection skipped - no checked/unavailable items",
        );
        return;
      }

      console.info("bulkUncheckSection target items", {
        count: targets.length,
        ids: targets.map((i) => i.id),
      });

      const mutation = buildItemMutations(
        current,
        targets.map((item) => ({
          id: item.id,
          updates: { status: PENDING_STATUS, checked_at: null },
        })),
      );
      if (!mutation) {
        return;
      }

      const { nextList, payload: updates } = mutation;
      keepScrollPosition(() => setList(nextList));

      try {
        console.debug("bulkUncheckSection dispatching via sendBulkUpdates");
        await sendBulkUpdates(nextList, updates, online);
      } catch (err) {
        console.error("Error bulk unchecking items:", err);
        if (online) {
          await reloadList();
          alert("Failed to update items");
        }
      }
    },
    [
      buildItemMutations,
      online,
      keepScrollPosition,
      list,
      listRef,
      locationKeyForItem,
      reloadList,
      sendBulkUpdates,
    ],
  );

  const bulkRemoveChecked = useCallback(async () => {
    console.info("bulkRemoveChecked invoked", { online });
    const current = list;
    if (!current) {
      return;
    }
    const checkedItems = current.items.filter(
      (item) => item.status === "purchased" || item.status === "unavailable",
    );
    if (checkedItems.length === 0) {
      setStatus({
        level: "info",
        message: "No checked or unavailable items to remove.",
      });
      return;
    }
    if (
      !confirm(`Remove all ${checkedItems.length} checked/unavailable items?`)
    ) {
      return;
    }

    let optimistic: ShoppingList | null = null;
    setList((prev) => {
      if (!prev) {
        return prev;
      }
      optimistic = {
        ...prev,
        items: prev.items.filter(
          (item) => !checkedItems.some((ci) => ci.id === item.id),
        ),
      };
      return optimistic;
    });

    if (!optimistic) {
      return;
    }

    try {
      await deleteItemWithCache(
        optimistic,
        checkedItems.map((item) => item.id),
        connectivity.online,
      );
    } catch (err) {
      console.error("Error deleting items:", err);
      if (online) {
        await reloadList();
        setStatus({
          level: "error",
          message: "Failed to remove items; list reloaded.",
        });
      }
    }
  }, [deleteItemWithCache, online, list, reloadList, connectivity.online]);

  const bulkUncheckAll = useCallback(async () => {
    console.info("bulkUncheckAll invoked", { online });
    const current = list ?? listRef.current;
    if (!current) {
      return;
    }
    const checkedItems = current.items.filter(
      (item) => item.status === "purchased",
    );

    if (checkedItems.length === 0) {
      setStatus({ level: "info", message: "No checked items to uncheck." });
      return;
    }
    if (!confirm(`Uncheck all ${checkedItems.length} purchased items?`)) {
      return;
    }

    const mutation = buildItemMutations(
      current,
      checkedItems.map((item) => ({
        id: item.id,
        updates: { status: PENDING_STATUS, checked_at: null },
      })),
    );
    if (!mutation) {
      return;
    }

    const { nextList, payload: updates } = mutation;
    keepScrollPosition(() => setList(nextList));

    try {
      await sendBulkUpdates(nextList, updates, online);
    } catch (err) {
      console.error("Error bulk updating items:", err);
      if (online) {
        await reloadList();
        alert("Failed to update items");
      }
    }
  }, [
    buildItemMutations,
    online,
    keepScrollPosition,
    list,
    listRef,
    reloadList,
    sendBulkUpdates,
  ]);

  const appendItem = useCallback((item: ShoppingListItem) => {
    setList((prev) => {
      if (!prev) {
        return prev;
      }
      return { ...prev, items: [...prev.items, item] };
    });
  }, []);

  const addItem = useCallback(
    async (productId: number, quantity: number) => {
      setError(null);
      setStatus(null);
      const current = list ?? listRef.current;
      const product = products.find((p) => p.id === productId) ?? null;
      const optimisticItem: ShoppingListItem | null =
        current && product
          ? {
              id:
                typeof crypto !== "undefined" && crypto.randomUUID
                  ? crypto.randomUUID()
                  : `${Date.now()}-${productId}`,
              product_id: product.id,
              product_name: product.name,
              shopping_location_id: product.shopping_location_id ?? null,
              shopping_location_name:
                product.location_name ??
                (product.shopping_location_id !== undefined &&
                product.shopping_location_id !== null
                  ? `Location ${product.shopping_location_id}`
                  : "UNKNOWN"),
              status: "pending",
              quantity_suggested: quantity,
              quantity_purchased: null,
              quantity_unit: product.stock_quantity_unit_name || "unit",
              current_stock: product.stocks.reduce(
                (total, entry) => total + entry.amount,
                0,
              ),
              min_stock: product.min_stock_amount,
              last_price: null,
              notes: "",
              checked_at: null,
              modified_at: new Date().toISOString(),
            }
          : null;

      try {
        const updated = await addItemWithCache(
          current,
          productId,
          quantity,
          optimisticItem,
        );
        if (updated) {
          setList(updated);
        } else if (optimisticItem) {
          setList((prev) =>
            prev ? { ...prev, items: [...prev.items, optimisticItem] } : prev,
          );
        }
        if (!connectivity.online) {
          setStatus({
            level: "info",
            message: "Item added offline; will sync when online.",
          });
        }
      } catch (err) {
        console.error("Failed to add item:", err);
        const message =
          err instanceof Error ? err.message : "Failed to add item to list";
        setError(message);
        setStatus({ level: "error", message });
      }
    },
    [addItemWithCache, connectivity.online, list, listRef, products],
  );

  const bulkAddItems = useCallback(
    async (items: Array<{ product_id: number; quantity: number }>) => {
      setError(null);
      setStatus(null);
      if (items.length === 0) {
        setStatus({ level: "info", message: "No items to add." });
        return;
      }
      try {
        if (!online) {
          for (const item of items) {
            await addItem(item.product_id, item.quantity);
          }
          return;
        }
        const added = await bulkAddShoppingListItems(instanceIndex, items);
        setList((prev) =>
          prev ? { ...prev, items: [...prev.items, ...added] } : prev,
        );
        setStatus({
          level: "info",
          message: `${added.length} items added${online ? "" : " (queued)"}.`,
        });
      } catch (err) {
        console.error("Failed to bulk add items:", err);
        const message =
          err instanceof Error ? err.message : "Failed to add items";
        setError(message);
        setStatus({ level: "error", message });
      }
    },
    [addItem, instanceIndex, online],
  );

  const sections = useMemo<ShoppingListSection[]>(() => {
    if (!list) {
      return [];
    }

    const grouped = new Map<string, ShoppingListItem[]>();
    const itemsWithGroups = list.items.map((item) => {
      const productGroup =
        item.product_group_name ??
        productGroupById.get(item.product_id) ??
        "Ungrouped";
      return { ...item, product_group_name: productGroup };
    });

    for (const item of itemsWithGroups) {
      const key = locationKeyForItem(item);
      const items = grouped.get(key) ?? [];
      items.push(item);
      grouped.set(key, items);
    }

    const orderLookup = new Map(
      list.location_order.map((loc, index) => [loc.toString(), index]),
    );

    const sortedGroups = Array.from(grouped.entries()).sort((a, b) => {
      const aOrder = orderLookup.get(a[0]) ?? Number.MAX_SAFE_INTEGER;
      const bOrder = orderLookup.get(b[0]) ?? Number.MAX_SAFE_INTEGER;
      return aOrder - bOrder;
    });

    return sortedGroups.map(([locationKey, items]) => {
      const sortedItems = [...items].sort((a, b) => {
        const aPending = a.status === "pending";
        const bPending = b.status === "pending";
        if (aPending && !bPending) {
          return -1;
        }
        if (!aPending && bPending) {
          return 1;
        }
        return 0;
      });

      const purchased = sortedItems.filter(
        (item) => item.status === "purchased" || item.status === "unavailable",
      ).length;
      const total = sortedItems.length;

      return {
        locationKey,
        locationName: sortedItems[0]?.shopping_location_name ?? "Unknown",
        items: sortedItems,
        purchasedCount: purchased,
        totalCount: total,
        allChecked: purchased === total && total > 0,
        someChecked: purchased > 0 && purchased < total,
      };
    });
  }, [list, locationKeyForItem, productGroupById]);

  const purchasedCount =
    list?.items.filter(
      (i) => i.status === "purchased" || i.status === "unavailable",
    ).length ?? 0;
  const totalCount = list?.items.length ?? 0;
  const progress =
    totalCount > 0 ? Math.round((purchasedCount / totalCount) * 100) : 0;

  return {
    isOnline: connectivity.online,
    isLoading,
    error,
    status,
    list,
    products,
    sections,
    purchasedCount,
    totalCount,
    progress,
    clearError: () => setError(null),
    clearStatus: () => setStatus(null),
    reloadList,
    generateList,
    completeList,
    updateItem,
    bulkCheckSection,
    bulkUncheckSection,
    bulkRemoveChecked,
    bulkUncheckAll,
    addItem,
    bulkAddItems,
    removeItems,
    appendItem,
  };
}

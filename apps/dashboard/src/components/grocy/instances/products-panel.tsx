"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  type DateRange,
  ListControls,
  type NumericRange,
} from "@/components/grocy/list-controls";
import { useSyncedQueryState } from "@/hooks/use-synced-query-state";
import type { DashboardRole } from "@/lib/auth/types";
import { fetchBulkPurchaseEntryDefaults } from "@/lib/grocy/client";
import { GROCY_QUERY_PARAMS } from "@/lib/grocy/query-params";
import type {
  GrocyProductInventoryEntry,
  PurchaseEntryDefaults,
} from "@/lib/grocy/types";

import {
  isDateRangeActive,
  isNumericRangeActive,
  matchesDateRange,
  matchesNumericRange,
  resolveProductGroup,
  resolveQuantityOnHand,
} from "./helpers";
import {
  areArraysEqual,
  areDateRangesEqual,
  areNumericRangesEqual,
  areSortStatesEqual,
  buildDefaultSortState,
  PRODUCT_SORT_OPTIONS,
  parseDateRangeParam,
  parseNumericRangeParam,
  parseSortStateParam,
  parseStockStatusParam,
  parseStringArrayParam,
  serializeDateRangeParam,
  serializeNumericRangeParam,
  serializeSortStateParam,
  serializeStringArrayParam,
} from "./inventory-query-state";
import { ProductActionDialog } from "./product-action-dialog";
import type { ProductActionType } from "./product-actions";
import { ProductDetailsDialog } from "./product-details-dialog";
import {
  compareProducts,
  ProductSortState,
  ProductStockCategory,
  resolveDaysSinceUpdate,
  resolveProductStockCategory,
  STOCK_STATUS_CATEGORY_BY_LABEL,
  STOCK_STATUS_FILTER_OPTIONS,
  STOCK_STATUS_LABEL_BY_CATEGORY,
} from "./product-metrics";
import { ProductsTable } from "./products-table";
import { ShoppingListButton } from "./shopping-list-button";

const PRODUCT_SEARCH_PARAM = GROCY_QUERY_PARAMS.inventorySearch;
const PRODUCT_GROUPS_PARAM = GROCY_QUERY_PARAMS.inventoryGroups;
const PRODUCT_STATUSES_PARAM = GROCY_QUERY_PARAMS.inventoryStatuses;
const PRODUCT_QUANTITY_PARAM = GROCY_QUERY_PARAMS.inventoryQuantityRange;
const PRODUCT_STALENESS_PARAM = GROCY_QUERY_PARAMS.inventoryStalenessRange;
const PRODUCT_UPDATED_PARAM = GROCY_QUERY_PARAMS.inventoryUpdatedRange;
const PRODUCT_SORT_PARAM = GROCY_QUERY_PARAMS.inventorySort;

const PURCHASE_DEFAULTS_BATCH_SIZE = 25;
const PURCHASE_DEFAULT_PREFETCH_CONCURRENCY = 4;
const PURCHASE_DEFAULT_PREFETCH_RETRY_BASE_DELAY_MS = 5_000;
const PURCHASE_DEFAULT_PREFETCH_RETRY_MAX_DELAY_MS = 60_000;

type ProductInteractionMode = "details" | "purchase" | "inventory";

const PRODUCT_MODE_OPTIONS: Array<{
  value: ProductInteractionMode;
  label: string;
}> = [
  { value: "details", label: "Normal" },
  { value: "purchase", label: "Purchase" },
  { value: "inventory", label: "Inventory" },
];

const parseSearchQueryParam = (rawValue: string | null): string =>
  rawValue ?? "";

const serializeSearchQueryParam = (value: string): string | null => {
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
};

const buildPurchaseDefaultsCacheKey = (
  productId: number,
  shoppingLocationId: number | null,
): string => `${productId}:${shoppingLocationId ?? "__none__"}`;

const buildDateInputValue = (): string => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return today.toISOString().slice(0, 10);
};
function chunkArray<T>(items: T[], size: number): T[][] {
  if (size <= 0) {
    return [items.slice()];
  }
  const chunks: T[][] = [];
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size));
  }
  return chunks;
}

type ProductsPanelProps = {
  isLoading: boolean;
  errorMessage: string | null;
  products: GrocyProductInventoryEntry[];
  activeInstanceId: string | null;
  locationNamesById: Record<number, string>;
  shoppingLocationNamesById: Record<number, string>;
  userRole: DashboardRole;
  onProductUpdate?: (product: GrocyProductInventoryEntry) => void;
  onRefresh?: () => void;
};

export function ProductsPanel({
  isLoading,
  errorMessage,
  products,
  activeInstanceId,
  locationNamesById,
  shoppingLocationNamesById,
  userRole,
  onProductUpdate,
  onRefresh,
}: ProductsPanelProps) {
  const [searchQuery, setSearchQuery] = useSyncedQueryState<string>({
    key: PRODUCT_SEARCH_PARAM,
    parse: parseSearchQueryParam,
    serialize: serializeSearchQueryParam,
  });
  const [selectedGroups, setSelectedGroups] = useSyncedQueryState<string[]>({
    key: PRODUCT_GROUPS_PARAM,
    parse: parseStringArrayParam,
    serialize: serializeStringArrayParam,
    isEqual: areArraysEqual,
  });
  const [sortState, setSortState] = useSyncedQueryState<ProductSortState>({
    key: PRODUCT_SORT_PARAM,
    parse: parseSortStateParam,
    serialize: serializeSortStateParam,
    isEqual: areSortStatesEqual,
  });
  const [quantityRange, setQuantityRange] =
    useSyncedQueryState<NumericRange | null>({
      key: PRODUCT_QUANTITY_PARAM,
      parse: parseNumericRangeParam,
      serialize: serializeNumericRangeParam,
      isEqual: areNumericRangesEqual,
    });
  const [updatedDateRange, setUpdatedDateRange] =
    useSyncedQueryState<DateRange | null>({
      key: PRODUCT_UPDATED_PARAM,
      parse: parseDateRangeParam,
      serialize: serializeDateRangeParam,
      isEqual: areDateRangesEqual,
    });
  const [stalenessRange, setStalenessRange] =
    useSyncedQueryState<NumericRange | null>({
      key: PRODUCT_STALENESS_PARAM,
      parse: parseNumericRangeParam,
      serialize: serializeNumericRangeParam,
      isEqual: areNumericRangesEqual,
    });
  const [selectedStockStatuses, setSelectedStockStatuses] = useSyncedQueryState<
    ProductStockCategory[]
  >({
    key: PRODUCT_STATUSES_PARAM,
    parse: parseStockStatusParam,
    serialize: serializeStringArrayParam,
    isEqual: areArraysEqual,
  });
  const [purchaseDefaultsByProductId, setPurchaseDefaultsByProductId] =
    useState<Record<number, PurchaseEntryDefaults>>({});
  const [purchaseDefaultsError, setPurchaseDefaultsError] = useState<
    string | null
  >(null);
  const prefetchedDefaultsRef = useRef<Set<string>>(new Set());
  const prefetchRetryAttemptsRef = useRef(0);
  const prefetchRetryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [prefetchRetrySignal, setPrefetchRetrySignal] = useState(0);
  const isAdmin = userRole === "admin";

  const instanceDefaultsResetKey = activeInstanceId ?? "__none__";

  useEffect(() => {
    void instanceDefaultsResetKey;
    prefetchedDefaultsRef.current = new Set();
    setPurchaseDefaultsByProductId({});
    setPurchaseDefaultsError(null);
    prefetchRetryAttemptsRef.current = 0;
    if (prefetchRetryTimeoutRef.current) {
      clearTimeout(prefetchRetryTimeoutRef.current);
      prefetchRetryTimeoutRef.current = null;
    }
    setPrefetchRetrySignal((value) => value + 1);
  }, [instanceDefaultsResetKey]);

  useEffect(() => {
    // Force effect reruns whenever the retry signal increments without depending on other state.
    void prefetchRetrySignal;
    if (!isAdmin) {
      if (prefetchRetryTimeoutRef.current) {
        clearTimeout(prefetchRetryTimeoutRef.current);
        prefetchRetryTimeoutRef.current = null;
      }
      return;
    }
    if (!activeInstanceId) {
      return;
    }
    const shoppingLocationId: number | null = null;
    const missingProductIds = products
      .map((product) => ({
        id: product.id,
        key: buildPurchaseDefaultsCacheKey(product.id, shoppingLocationId),
      }))
      .filter((entry) => !prefetchedDefaultsRef.current.has(entry.key))
      .map((entry) => entry.id);
    if (missingProductIds.length === 0) {
      prefetchRetryAttemptsRef.current = 0;
      setPurchaseDefaultsError(null);
      if (prefetchRetryTimeoutRef.current) {
        clearTimeout(prefetchRetryTimeoutRef.current);
        prefetchRetryTimeoutRef.current = null;
      }
      return;
    }
    setPurchaseDefaultsError(null);
    let cancelled = false;
    const batches = chunkArray(missingProductIds, PURCHASE_DEFAULTS_BATCH_SIZE);

    const runPrefetch = async () => {
      const workerCount = Math.min(
        PURCHASE_DEFAULT_PREFETCH_CONCURRENCY,
        batches.length,
      );
      const runWorker = async (workerIndex: number) => {
        for (
          let batchIndex = workerIndex;
          batchIndex < batches.length;
          batchIndex += workerCount
        ) {
          const batch = batches[batchIndex];
          const defaults = await fetchBulkPurchaseEntryDefaults(
            activeInstanceId,
            batch,
            shoppingLocationId,
          );
          if (cancelled) {
            return;
          }
          setPurchaseDefaultsByProductId((current) => {
            const next = { ...current };
            defaults.forEach((entry) => {
              next[entry.productId] = entry;
              prefetchedDefaultsRef.current.add(
                buildPurchaseDefaultsCacheKey(
                  entry.productId,
                  entry.shoppingLocationId ?? null,
                ),
              );
            });
            return next;
          });
        }
      };

      await Promise.all(
        Array.from({ length: workerCount }, (_, index) => runWorker(index)),
      );
    };

    const loadDefaults = async () => {
      try {
        await runPrefetch();
        if (cancelled) {
          return;
        }
        prefetchRetryAttemptsRef.current = 0;
        if (prefetchRetryTimeoutRef.current) {
          clearTimeout(prefetchRetryTimeoutRef.current);
          prefetchRetryTimeoutRef.current = null;
        }
        setPurchaseDefaultsError(null);
      } catch (error) {
        if (cancelled) {
          return;
        }
        console.warn("Failed to prefetch purchase entry defaults", error);
        const attempt = prefetchRetryAttemptsRef.current + 1;
        prefetchRetryAttemptsRef.current = attempt;
        const delay = Math.min(
          PURCHASE_DEFAULT_PREFETCH_RETRY_MAX_DELAY_MS,
          PURCHASE_DEFAULT_PREFETCH_RETRY_BASE_DELAY_MS * attempt,
        );
        setPurchaseDefaultsError(
          `Unable to preload purchase metadata. We'll retry automatically in ${Math.round(delay / 1000)} seconds.`,
        );
        if (prefetchRetryTimeoutRef.current) {
          clearTimeout(prefetchRetryTimeoutRef.current);
        }
        prefetchRetryTimeoutRef.current = setTimeout(() => {
          setPrefetchRetrySignal((value) => value + 1);
        }, delay);
      }
    };

    void loadDefaults();
    return () => {
      cancelled = true;
      if (prefetchRetryTimeoutRef.current) {
        clearTimeout(prefetchRetryTimeoutRef.current);
        prefetchRetryTimeoutRef.current = null;
      }
    };
  }, [activeInstanceId, isAdmin, products, prefetchRetrySignal]);

  const [activeProduct, setActiveProduct] =
    useState<GrocyProductInventoryEntry | null>(null);
  const [activeAction, setActiveAction] = useState<{
    product: GrocyProductInventoryEntry;
    action: ProductActionType;
  } | null>(null);
  const [notification, setNotification] = useState<string | null>(null);
  const notificationTimeout = useRef<NodeJS.Timeout | null>(null);
  const lastInstanceId = useRef<string | null>(null);
  const [productInteractionMode, setProductInteractionMode] =
    useState<ProductInteractionMode>("details");
  const [purchaseDateOverride, setPurchaseDateOverride] = useState<
    string | null
  >(() => buildDateInputValue());

  useEffect(() => {
    if (isAdmin) {
      return;
    }
    setProductInteractionMode("details");
    setActiveAction(null);
    setActiveProduct(null);
    setPurchaseDefaultsByProductId({});
    setPurchaseDefaultsError(null);
    prefetchedDefaultsRef.current = new Set();
  }, [isAdmin]);

  useEffect(() => {
    if (!activeInstanceId) {
      lastInstanceId.current = null;
      return;
    }
    if (lastInstanceId.current === null) {
      lastInstanceId.current = activeInstanceId;
      return;
    }
    if (lastInstanceId.current === activeInstanceId) {
      return;
    }
    lastInstanceId.current = activeInstanceId;
    setSearchQuery("");
    setSelectedGroups([]);
    setSortState(buildDefaultSortState());
    setQuantityRange(null);
    setUpdatedDateRange(null);
    setStalenessRange(null);
    setSelectedStockStatuses([]);
    setActiveProduct(null);
  }, [
    activeInstanceId,
    setQuantityRange,
    setSearchQuery,
    setSelectedGroups,
    setSelectedStockStatuses,
    setSortState,
    setStalenessRange,
    setUpdatedDateRange,
  ]);

  useEffect(() => {
    if (!activeAction) {
      return;
    }
    const updated = products.find(
      (product) => product.id === activeAction.product.id,
    );
    if (updated && updated !== activeAction.product) {
      setActiveAction({ product: updated, action: activeAction.action });
    }
  }, [products, activeAction]);

  useEffect(() => {
    if (!activeProduct) {
      return;
    }
    const updated = products.find((product) => product.id === activeProduct.id);
    if (updated && updated !== activeProduct) {
      setActiveProduct(updated);
    }
  }, [products, activeProduct]);

  useEffect(() => {
    if (!notification) {
      return;
    }
    if (notificationTimeout.current) {
      clearTimeout(notificationTimeout.current);
    }
    notificationTimeout.current = setTimeout(() => {
      setNotification(null);
      notificationTimeout.current = null;
    }, 4000);
    return () => {
      if (notificationTimeout.current) {
        clearTimeout(notificationTimeout.current);
        notificationTimeout.current = null;
      }
    };
  }, [notification]);

  useEffect(() => {
    if (productInteractionMode === "details") {
      setActiveAction(null);
      return;
    }
    setActiveProduct(null);
  }, [productInteractionMode]);

  const productGroups = useMemo(() => {
    const uniqueGroups = new Set<string>();
    products.forEach((product) => {
      uniqueGroups.add(resolveProductGroup(product));
    });
    return Array.from(uniqueGroups).sort((a, b) => a.localeCompare(b));
  }, [products]);

  useEffect(() => {
    setSelectedGroups((current) => {
      const next = current.filter((group) => productGroups.includes(group));
      return next.length === current.length ? current : next;
    });
  }, [productGroups, setSelectedGroups]);

  const toggleGroup = (group: string) => {
    setSelectedGroups((current) =>
      current.includes(group)
        ? current.filter((value) => value !== group)
        : [...current, group],
    );
  };

  const toggleStockStatus = (label: string) => {
    const category = STOCK_STATUS_CATEGORY_BY_LABEL[label];
    if (!category) {
      return;
    }
    setSelectedStockStatuses((current) =>
      current.includes(category)
        ? current.filter((value) => value !== category)
        : [...current, category],
    );
  };

  const clearAllFilters = () => {
    setSearchQuery("");
    setSelectedGroups([]);
    setSelectedStockStatuses([]);
    setQuantityRange(null);
    setStalenessRange(null);
    setUpdatedDateRange(null);
  };

  const filteredProducts = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();
    return products.filter((product) => {
      const group = resolveProductGroup(product);
      const quantityOnHand = resolveQuantityOnHand(product);
      const stockCategory = resolveProductStockCategory(product);
      const matchesQuery =
        normalizedQuery.length === 0 ||
        product.name.toLowerCase().includes(normalizedQuery) ||
        group.toLowerCase().includes(normalizedQuery);
      const matchesGroup =
        selectedGroups.length === 0 || selectedGroups.includes(group);
      const matchesStatus =
        selectedStockStatuses.length === 0 ||
        selectedStockStatuses.includes(stockCategory);
      const matchesQuantity = matchesNumericRange(
        quantityOnHand,
        quantityRange,
      );
      const matchesStaleness = matchesNumericRange(
        resolveDaysSinceUpdate(product),
        stalenessRange,
      );
      const matchesUpdated = matchesDateRange(
        product.last_stock_updated_at,
        updatedDateRange,
      );
      return (
        matchesQuery &&
        matchesGroup &&
        matchesStatus &&
        matchesQuantity &&
        matchesStaleness &&
        matchesUpdated
      );
    });
  }, [
    products,
    searchQuery,
    selectedGroups,
    selectedStockStatuses,
    quantityRange,
    stalenessRange,
    updatedDateRange,
  ]);

  const sortedProducts = useMemo(() => {
    const sorted = [...filteredProducts];
    sorted.sort((a, b) => compareProducts(a, b, sortState));
    return sorted;
  }, [filteredProducts, sortState]);

  const hasProductFilters =
    searchQuery.trim().length > 0 ||
    selectedGroups.length > 0 ||
    selectedStockStatuses.length > 0 ||
    isNumericRangeActive(quantityRange) ||
    isNumericRangeActive(stalenessRange) ||
    isDateRangeActive(updatedDateRange);

  const selectedStockStatusLabels = selectedStockStatuses.map(
    (category) => STOCK_STATUS_LABEL_BY_CATEGORY[category],
  );

  const productFilters = {
    fields: [
      ...(productGroups.length > 0
        ? [
            {
              id: "product_groups" as const,
              label: "Product groups",
              type: "text" as const,
              values: productGroups,
              selectedValues: selectedGroups,
              onToggle: toggleGroup,
              onClear: () => setSelectedGroups([]),
            },
          ]
        : []),
      {
        id: "stock_status" as const,
        label: "Stock status",
        type: "text" as const,
        values: STOCK_STATUS_FILTER_OPTIONS.map((option) => option.label),
        selectedValues: selectedStockStatusLabels,
        onToggle: toggleStockStatus,
        onClear: () => setSelectedStockStatuses([]),
      },
      {
        id: "quantity_on_hand" as const,
        label: "Quantity on hand",
        type: "number" as const,
        range: quantityRange,
        onRangeChange: setQuantityRange,
        onClear: () => setQuantityRange(null),
      },
      {
        id: "days_since_update" as const,
        label: "Days since last update",
        type: "number" as const,
        range: stalenessRange,
        onRangeChange: setStalenessRange,
        onClear: () => setStalenessRange(null),
      },
      {
        id: "last_updated" as const,
        label: "Last updated",
        type: "date" as const,
        range: updatedDateRange,
        onRangeChange: setUpdatedDateRange,
        onClear: () => setUpdatedDateRange(null),
      },
    ],
    buttonLabel: "Filters +",
  };

  const handleActionSuccess = (message: string) => {
    setNotification(message);
  };

  const handlePrimaryProductSelection = (
    product: GrocyProductInventoryEntry,
  ) => {
    if (!isAdmin) {
      setActiveProduct(product);
      return;
    }
    if (productInteractionMode === "purchase") {
      setActiveAction({ product, action: "purchaseEntry" });
      return;
    }
    if (productInteractionMode === "inventory") {
      setActiveAction({ product, action: "inventoryCorrection" });
      return;
    }
    setActiveProduct(product);
  };

  const allowedModes = useMemo(
    () =>
      isAdmin
        ? PRODUCT_MODE_OPTIONS
        : PRODUCT_MODE_OPTIONS.filter((option) => option.value === "details"),
    [isAdmin],
  );

  const renderModeButtons = () => (
    <div className="flex flex-col items-center gap-2 lg:flex-1 lg:flex-row lg:items-center lg:justify-center">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
        Mode
      </p>
      <div className="flex flex-wrap items-center justify-center gap-2">
        {allowedModes.map((option) => {
          const isActive = option.value === productInteractionMode;
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => setProductInteractionMode(option.value)}
              aria-pressed={isActive}
              className={`rounded-full px-4 py-1.5 text-xs font-semibold transition ${
                isActive
                  ? "bg-neutral-900 text-white shadow"
                  : "border border-neutral-300 text-neutral-600 hover:border-neutral-900 hover:text-neutral-900"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );

  const renderPurchaseModeDefaults = () => {
    if (!isAdmin || productInteractionMode !== "purchase") {
      return null;
    }
    return (
      <div className="rounded-3xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-4 text-sm text-neutral-700 shadow-inner">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Default purchase date
            </p>
            <p className="text-xs text-neutral-500">
              New purchase entries open with this date pre-filled so you can
              batch receipts for a given day.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <input
              type="date"
              value={purchaseDateOverride ?? ""}
              onChange={(event) => {
                const value = event.target.value;
                setPurchaseDateOverride(value ? value : null);
              }}
              className="rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none"
            />
            <button
              type="button"
              onClick={() => setPurchaseDateOverride(buildDateInputValue())}
              className="rounded-full border border-neutral-300 px-4 py-2 text-xs font-semibold text-neutral-700 transition hover:border-neutral-900 hover:text-neutral-900"
            >
              Use today
            </button>
          </div>
        </div>
      </div>
    );
  };

  if (errorMessage) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
        {errorMessage}
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white px-4 py-6 text-sm text-neutral-600">
        Loading inventory…
      </div>
    );
  }

  if (products.length === 0) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white px-4 py-6 text-sm text-neutral-600">
        This instance does not have any synced products yet.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {notification ? (
        <div className="fixed right-6 top-6 z-50 w-80 rounded-3xl border border-emerald-300 bg-emerald-50 px-6 py-4 text-base font-semibold text-emerald-900 shadow-2xl">
          {notification}
        </div>
      ) : null}
      {purchaseDefaultsError ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-900">
          {purchaseDefaultsError}
        </div>
      ) : null}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-sm font-medium text-neutral-700">
            Products ({filteredProducts.length}
            {products.length !== filteredProducts.length
              ? ` of ${products.length}`
              : ""}
            )
          </p>
          {hasProductFilters ? (
            <p className="text-xs text-neutral-500">
              Filters and search applied to the inventory list.
            </p>
          ) : null}
        </div>
        {renderModeButtons()}
        {onRefresh || activeInstanceId ? (
          <div className="flex gap-2 justify-start lg:justify-end">
            {activeInstanceId ? (
              <ShoppingListButton instanceIndex={activeInstanceId} />
            ) : null}
            {onRefresh ? (
              <button
                type="button"
                onClick={onRefresh}
                disabled={!activeInstanceId || isLoading}
                className="inline-flex items-center justify-center rounded-full border border-neutral-300 px-4 py-1.5 text-sm font-semibold text-neutral-700 transition hover:bg-neutral-100 disabled:cursor-not-allowed disabled:border-neutral-200 disabled:text-neutral-400"
              >
                Refresh data
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      {renderPurchaseModeDefaults()}

      <ListControls
        searchLabel="Search products"
        searchPlaceholder="Search products or groups…"
        searchValue={searchQuery}
        onSearchChange={setSearchQuery}
        filters={productFilters}
        sortOptions={PRODUCT_SORT_OPTIONS}
        sortState={sortState}
        maxSortLevels={3}
        onSortChange={setSortState}
        className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"
      />

      {sortedProducts.length > 0 ? (
        <ProductsTable
          products={sortedProducts}
          onSelectProduct={handlePrimaryProductSelection}
          onSelectAction={(product, action) =>
            setActiveAction({ product, action })
          }
        />
      ) : (
        <div className="rounded-2xl border border-dashed border-neutral-300 bg-neutral-50 px-4 py-6 text-sm text-neutral-600">
          No products match the current filters.
          {hasProductFilters ? (
            <button
              type="button"
              onClick={clearAllFilters}
              className="ml-2 text-neutral-700 underline-offset-2 hover:underline"
            >
              Clear filters
            </button>
          ) : null}
        </div>
      )}

      {activeProduct ? (
        <ProductDetailsDialog
          product={activeProduct}
          onClose={() => setActiveProduct(null)}
          locationNamesById={locationNamesById}
          shoppingLocationNamesById={shoppingLocationNamesById}
        />
      ) : null}
      {activeAction ? (
        <ProductActionDialog
          product={activeAction.product}
          action={activeAction.action}
          onClose={() => setActiveAction(null)}
          instanceIndex={activeInstanceId}
          locationNamesById={locationNamesById}
          shoppingLocationNamesById={shoppingLocationNamesById}
          onProductUpdate={onProductUpdate}
          prefetchedPurchaseDefaults={purchaseDefaultsByProductId}
          defaultPurchasedDate={purchaseDateOverride}
          onSuccess={(message) => {
            handleActionSuccess(message);
            setActiveAction(null);
          }}
        />
      ) : null}
    </div>
  );
}

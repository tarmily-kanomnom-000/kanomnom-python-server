"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  type DateRange,
  ListControls,
  type NumericRange,
} from "@/components/grocy/list-controls";
import { useSyncedQueryState } from "@/hooks/use-synced-query-state";
import type { DashboardRole } from "@/lib/auth/types";
import { submitInventoryCorrection } from "@/lib/grocy/client";
import { GROCY_QUERY_PARAMS } from "@/lib/grocy/query-params";
import type {
  GrocyProductInventoryEntry,
  InventoryCorrectionRequestPayload,
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
import {
  ModeButtons,
  type ProductInteractionMode,
  PurchaseModeDefaults,
  parseProductModeParam,
  parsePurchaseDateParam,
  serializeProductModeParam,
  serializePurchaseDateParam,
} from "./mode-controls";
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
import { usePurchaseDefaultsPrefetch } from "./purchase-defaults";
import { ShoppingListButton } from "./shopping-list-button";

const PRODUCT_SEARCH_PARAM = GROCY_QUERY_PARAMS.inventorySearch;
const PRODUCT_GROUPS_PARAM = GROCY_QUERY_PARAMS.inventoryGroups;
const PRODUCT_STATUSES_PARAM = GROCY_QUERY_PARAMS.inventoryStatuses;
const PRODUCT_QUANTITY_PARAM = GROCY_QUERY_PARAMS.inventoryQuantityRange;
const PRODUCT_STALENESS_PARAM = GROCY_QUERY_PARAMS.inventoryStalenessRange;
const PRODUCT_UPDATED_PARAM = GROCY_QUERY_PARAMS.inventoryUpdatedRange;
const PRODUCT_SORT_PARAM = GROCY_QUERY_PARAMS.inventorySort;
const PRODUCT_MODE_PARAM = GROCY_QUERY_PARAMS.inventoryMode;
const PRODUCT_PURCHASE_DATE_PARAM = GROCY_QUERY_PARAMS.inventoryPurchaseDate;

const parseSearchQueryParam = (rawValue: string | null): string =>
  rawValue ?? "";

const serializeSearchQueryParam = (value: string): string | null => {
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
};

type ProductsPanelProps = {
  isLoading: boolean;
  errorMessage: string | null;
  instanceErrorMessage?: string | null;
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
  instanceErrorMessage,
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
  const isAdmin = userRole === "admin";
  const { defaultsByProductId, error: purchaseDefaultsError } =
    usePurchaseDefaultsPrefetch({
      isAdmin,
      activeInstanceId,
      products,
    });

  const [activeProduct, setActiveProduct] =
    useState<GrocyProductInventoryEntry | null>(null);
  const [activeAction, setActiveAction] = useState<{
    product: GrocyProductInventoryEntry;
    action: ProductActionType;
  } | null>(null);
  const [notification, setNotification] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);
  const notificationTimeout = useRef<NodeJS.Timeout | null>(null);
  const lastInstanceId = useRef<string | null>(null);
  const [quickActionPendingIds, setQuickActionPendingIds] = useState(
    () => new Set<number>(),
  );
  const [productInteractionMode, setProductInteractionMode] =
    useSyncedQueryState<ProductInteractionMode>({
      key: PRODUCT_MODE_PARAM,
      parse: parseProductModeParam,
      serialize: serializeProductModeParam,
    });
  const [purchaseDateOverride, setPurchaseDateOverride] =
    useSyncedQueryState<string>({
      key: PRODUCT_PURCHASE_DATE_PARAM,
      parse: parsePurchaseDateParam,
      serialize: serializePurchaseDateParam,
    });

  useEffect(() => {
    if (isAdmin) {
      return;
    }
    setProductInteractionMode("details");
    setActiveAction(null);
    setActiveProduct(null);
  }, [isAdmin, setProductInteractionMode]);

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
      setActiveAction({
        product: updated,
        action: activeAction.action,
      });
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
    setNotification({ type: "success", message });
  };

  const handleQuickSetZero = useCallback(
    async (product: GrocyProductInventoryEntry) => {
      if (!activeInstanceId) {
        return;
      }
      setQuickActionPendingIds((current) => {
        const next = new Set(current);
        next.add(product.id);
        return next;
      });
      try {
        const tareWeight =
          Number.isFinite(product.tare_weight) && product.tare_weight > 0
            ? product.tare_weight
            : 0;
        const payload: InventoryCorrectionRequestPayload = {
          newAmount: tareWeight,
          bestBeforeDate: null,
          locationId: product.location_id ?? null,
          note: null,
          metadata: null,
        };
        const updatedProduct = await submitInventoryCorrection(
          activeInstanceId,
          product.id,
          payload,
        );
        onProductUpdate?.(updatedProduct);
        setNotification({ type: "success", message: "Stock set to 0." });
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Failed to set stock to 0.";
        setNotification({ type: "error", message });
      } finally {
        setQuickActionPendingIds((current) => {
          const next = new Set(current);
          next.delete(product.id);
          return next;
        });
      }
    },
    [activeInstanceId, onProductUpdate],
  );

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
        <div
          className={`fixed right-6 top-6 z-50 w-80 rounded-3xl border px-6 py-4 text-base font-semibold shadow-2xl ${
            notification.type === "success"
              ? "border-emerald-300 bg-emerald-50 text-emerald-900"
              : "border-rose-300 bg-rose-50 text-rose-900"
          }`}
        >
          {notification.message}
        </div>
      ) : null}
      {purchaseDefaultsError ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-900">
          {purchaseDefaultsError}
        </div>
      ) : null}
      {instanceErrorMessage ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-900">
          {instanceErrorMessage}
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
        <ModeButtons
          isAdmin={isAdmin}
          productInteractionMode={productInteractionMode}
          onChange={setProductInteractionMode}
        />
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

      <PurchaseModeDefaults
        isAdmin={isAdmin}
        productInteractionMode={productInteractionMode}
        purchaseDateOverride={purchaseDateOverride}
        setPurchaseDateOverride={setPurchaseDateOverride}
      />

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
          productInteractionMode={productInteractionMode}
          onQuickSetZero={handleQuickSetZero}
          quickActionPendingIds={quickActionPendingIds}
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
          instanceIndex={activeInstanceId}
          isAdmin={isAdmin}
          onProductUpdate={onProductUpdate}
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
          prefetchedPurchaseDefaults={defaultsByProductId}
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

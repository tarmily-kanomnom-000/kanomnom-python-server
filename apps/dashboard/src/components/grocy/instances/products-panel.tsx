"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  type DateRange,
  ListControls,
  type NumericRange,
} from "@/components/grocy/list-controls";
import { useQueryParamUpdater } from "@/hooks/use-query-param-updater";
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
import { ProductActionDialog } from "./product-action-dialog";
import type { ProductActionType } from "./product-actions";
import { ProductDetailsDialog } from "./product-details-dialog";
import {
  compareProducts,
  ProductSortField,
  ProductSortState,
  ProductStockCategory,
  resolveDaysSinceUpdate,
  resolveProductStockCategory,
  STOCK_STATUS_CATEGORY_BY_LABEL,
  STOCK_STATUS_FILTER_OPTIONS,
  STOCK_STATUS_LABEL_BY_CATEGORY,
  STOCK_STATUS_PRIORITY,
} from "./product-metrics";
import { ProductsTable } from "./products-table";

const PRODUCT_SEARCH_PARAM = GROCY_QUERY_PARAMS.inventorySearch;
const PRODUCT_GROUPS_PARAM = GROCY_QUERY_PARAMS.inventoryGroups;
const PRODUCT_STATUSES_PARAM = GROCY_QUERY_PARAMS.inventoryStatuses;
const PRODUCT_QUANTITY_PARAM = GROCY_QUERY_PARAMS.inventoryQuantityRange;
const PRODUCT_STALENESS_PARAM = GROCY_QUERY_PARAMS.inventoryStalenessRange;
const PRODUCT_UPDATED_PARAM = GROCY_QUERY_PARAMS.inventoryUpdatedRange;
const PRODUCT_SORT_PARAM = GROCY_QUERY_PARAMS.inventorySort;

const NUMERIC_RANGE_MODES: NumericRange["mode"][] = [
  "exact",
  "lt",
  "gt",
  "between",
];
const DATE_RANGE_MODES: DateRange["mode"][] = [
  "on",
  "before",
  "after",
  "between",
];
const DEFAULT_SORT_STATE: ProductSortState = [
  { field: "name", direction: "asc" },
];

const PRODUCT_SORT_OPTIONS: Array<{ label: string; value: ProductSortField }> =
  [
    { label: "Product name", value: "name" },
    { label: "Stock status", value: "status" },
    { label: "Amount in stock", value: "quantity" },
    { label: "Days since last update", value: "daysSinceUpdate" },
    { label: "Last updated", value: "updated" },
  ];

const PURCHASE_DEFAULTS_BATCH_SIZE = 25;

type ProductInteractionMode = "details" | "purchase" | "inventory";

const PRODUCT_MODE_OPTIONS: Array<{
  value: ProductInteractionMode;
  label: string;
}> = [
  { value: "details", label: "Normal" },
  { value: "purchase", label: "Purchase" },
  { value: "inventory", label: "Inventory" },
];

function buildDefaultSortState(): ProductSortState {
  return DEFAULT_SORT_STATE.map((rule) => ({ ...rule }));
}

function parseStringArrayParam(raw: string | null): string[] {
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed.filter((value) => typeof value === "string");
    }
  } catch {
    // fall through to default
  }
  return [];
}

function parseStockStatusParam(raw: string | null): ProductStockCategory[] {
  const values = parseStringArrayParam(raw);
  return values.filter(
    (value): value is ProductStockCategory => value in STOCK_STATUS_PRIORITY,
  );
}

function parseNumericRangeParam(raw: string | null): NumericRange | null {
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw);
    if (
      parsed &&
      typeof parsed === "object" &&
      NUMERIC_RANGE_MODES.includes(parsed.mode)
    ) {
      return {
        mode: parsed.mode,
        min:
          typeof parsed.min === "number" || parsed.min === null
            ? parsed.min
            : undefined,
        max:
          typeof parsed.max === "number" || parsed.max === null
            ? parsed.max
            : undefined,
      };
    }
  } catch {
    // ignore malformed values
  }
  return null;
}

function parseDateRangeParam(raw: string | null): DateRange | null {
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw);
    if (
      parsed &&
      typeof parsed === "object" &&
      DATE_RANGE_MODES.includes(parsed.mode)
    ) {
      const isValidValue = (value: unknown) =>
        typeof value === "string" ||
        value === null ||
        typeof value === "undefined";
      if (isValidValue(parsed.start) && isValidValue(parsed.end)) {
        return {
          mode: parsed.mode,
          start:
            typeof parsed.start === "string" || parsed.start === null
              ? parsed.start
              : undefined,
          end:
            typeof parsed.end === "string" || parsed.end === null
              ? parsed.end
              : undefined,
        };
      }
    }
  } catch {
    // ignore malformed values
  }
  return null;
}

function parseSortStateParam(raw: string | null): ProductSortState {
  if (!raw) {
    return buildDefaultSortState();
  }
  try {
    const parsed = JSON.parse(raw);
    if (
      Array.isArray(parsed) &&
      parsed.every(
        (rule) =>
          rule &&
          typeof rule === "object" &&
          PRODUCT_SORT_OPTIONS.some((option) => option.value === rule.field) &&
          (rule.direction === "asc" || rule.direction === "desc"),
      )
    ) {
      return parsed.length > 0 ? parsed : buildDefaultSortState();
    }
  } catch {
    // ignore malformed values
  }
  return buildDefaultSortState();
}

function areArraysEqual<T>(a: T[], b: T[]): boolean {
  if (a.length !== b.length) {
    return false;
  }
  return a.every((value, index) => value === b[index]);
}

function areNumericRangesEqual(
  a: NumericRange | null,
  b: NumericRange | null,
): boolean {
  if (a === b) {
    return true;
  }
  if (!a || !b) {
    return false;
  }
  return (
    a.mode === b.mode &&
    (a.min ?? null) === (b.min ?? null) &&
    (a.max ?? null) === (b.max ?? null)
  );
}

function areDateRangesEqual(a: DateRange | null, b: DateRange | null): boolean {
  if (a === b) {
    return true;
  }
  if (!a || !b) {
    return false;
  }
  return (
    a.mode === b.mode &&
    (a.start ?? null) === (b.start ?? null) &&
    (a.end ?? null) === (b.end ?? null)
  );
}

function areSortStatesEqual(a: ProductSortState, b: ProductSortState): boolean {
  if (a.length !== b.length) {
    return false;
  }
  return a.every(
    (rule, index) =>
      rule.field === b[index]?.field && rule.direction === b[index]?.direction,
  );
}

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
  onProductUpdate,
  onRefresh,
}: ProductsPanelProps) {
  const searchParams = useSearchParams();
  const updateQueryParams = useQueryParamUpdater();
  const [searchQuery, setSearchQuery] = useState<string>(
    () => searchParams.get(PRODUCT_SEARCH_PARAM) ?? "",
  );
  const [selectedGroups, setSelectedGroups] = useState<string[]>(() =>
    parseStringArrayParam(searchParams.get(PRODUCT_GROUPS_PARAM)),
  );
  const [sortState, setSortState] = useState<ProductSortState>(() =>
    parseSortStateParam(searchParams.get(PRODUCT_SORT_PARAM)),
  );
  const [quantityRange, setQuantityRange] = useState<NumericRange | null>(() =>
    parseNumericRangeParam(searchParams.get(PRODUCT_QUANTITY_PARAM)),
  );
  const [updatedDateRange, setUpdatedDateRange] = useState<DateRange | null>(
    () => parseDateRangeParam(searchParams.get(PRODUCT_UPDATED_PARAM)),
  );
  const [stalenessRange, setStalenessRange] = useState<NumericRange | null>(
    () => parseNumericRangeParam(searchParams.get(PRODUCT_STALENESS_PARAM)),
  );
  const [selectedStockStatuses, setSelectedStockStatuses] = useState<
    ProductStockCategory[]
  >(() => parseStockStatusParam(searchParams.get(PRODUCT_STATUSES_PARAM)));
  const [purchaseDefaultsByProductId, setPurchaseDefaultsByProductId] =
    useState<Record<number, PurchaseEntryDefaults>>({});
  const prefetchedDefaultsRef = useRef<Set<number>>(new Set());

  useEffect(() => {
    const nextValue = searchParams.get(PRODUCT_SEARCH_PARAM) ?? "";
    setSearchQuery((current) => (current === nextValue ? current : nextValue));
  }, [searchParams]);

  useEffect(() => {
    const nextGroups = parseStringArrayParam(
      searchParams.get(PRODUCT_GROUPS_PARAM),
    );
    setSelectedGroups((current) =>
      areArraysEqual(current, nextGroups) ? current : nextGroups,
    );
  }, [searchParams]);

  useEffect(() => {
    const nextStatuses = parseStockStatusParam(
      searchParams.get(PRODUCT_STATUSES_PARAM),
    );
    setSelectedStockStatuses((current) =>
      areArraysEqual(current, nextStatuses) ? current : nextStatuses,
    );
  }, [searchParams]);

  useEffect(() => {
    const nextQuantityRange = parseNumericRangeParam(
      searchParams.get(PRODUCT_QUANTITY_PARAM),
    );
    setQuantityRange((current) =>
      areNumericRangesEqual(current, nextQuantityRange)
        ? current
        : nextQuantityRange,
    );
  }, [searchParams]);

  useEffect(() => {
    const nextStalenessRange = parseNumericRangeParam(
      searchParams.get(PRODUCT_STALENESS_PARAM),
    );
    setStalenessRange((current) =>
      areNumericRangesEqual(current, nextStalenessRange)
        ? current
        : nextStalenessRange,
    );
  }, [searchParams]);

  useEffect(() => {
    const nextUpdatedRange = parseDateRangeParam(
      searchParams.get(PRODUCT_UPDATED_PARAM),
    );
    setUpdatedDateRange((current) =>
      areDateRangesEqual(current, nextUpdatedRange)
        ? current
        : nextUpdatedRange,
    );
  }, [searchParams]);

  useEffect(() => {
    const nextSortState = parseSortStateParam(
      searchParams.get(PRODUCT_SORT_PARAM),
    );
    setSortState((current) =>
      areSortStatesEqual(current, nextSortState) ? current : nextSortState,
    );
  }, [searchParams]);

  const instanceDefaultsResetKey = activeInstanceId ?? "__none__";

  useEffect(() => {
    void instanceDefaultsResetKey;
    prefetchedDefaultsRef.current = new Set();
    setPurchaseDefaultsByProductId({});
  }, [instanceDefaultsResetKey]);

  useEffect(() => {
    if (!activeInstanceId) {
      return;
    }
    const missingProductIds = products
      .map((product) => product.id)
      .filter((id) => !prefetchedDefaultsRef.current.has(id));
    if (missingProductIds.length === 0) {
      return;
    }
    let cancelled = false;
    const batches = chunkArray(missingProductIds, PURCHASE_DEFAULTS_BATCH_SIZE);

    const loadDefaults = async () => {
      for (const batch of batches) {
        try {
          const defaults = await fetchBulkPurchaseEntryDefaults(
            activeInstanceId,
            batch,
            null,
          );
          if (cancelled) {
            return;
          }
          setPurchaseDefaultsByProductId((current) => {
            const next = { ...current };
            defaults.forEach((entry) => {
              next[entry.productId] = entry;
              prefetchedDefaultsRef.current.add(entry.productId);
            });
            return next;
          });
        } catch {
          if (cancelled) {
            return;
          }
          // Ignore errors to avoid interrupting other batches; we'll refetch on next render.
        }
      }
    };

    void loadDefaults();
    return () => {
      cancelled = true;
    };
  }, [activeInstanceId, products]);

  useEffect(() => {
    const normalized = searchQuery.trim();
    updateQueryParams({
      [PRODUCT_SEARCH_PARAM]: normalized.length > 0 ? searchQuery : null,
    });
  }, [searchQuery, updateQueryParams]);

  useEffect(() => {
    updateQueryParams({
      [PRODUCT_GROUPS_PARAM]:
        selectedGroups.length > 0 ? JSON.stringify(selectedGroups) : null,
    });
  }, [selectedGroups, updateQueryParams]);

  useEffect(() => {
    updateQueryParams({
      [PRODUCT_STATUSES_PARAM]:
        selectedStockStatuses.length > 0
          ? JSON.stringify(selectedStockStatuses)
          : null,
    });
  }, [selectedStockStatuses, updateQueryParams]);

  useEffect(() => {
    updateQueryParams({
      [PRODUCT_QUANTITY_PARAM]: quantityRange
        ? JSON.stringify(quantityRange)
        : null,
    });
  }, [quantityRange, updateQueryParams]);

  useEffect(() => {
    updateQueryParams({
      [PRODUCT_STALENESS_PARAM]: stalenessRange
        ? JSON.stringify(stalenessRange)
        : null,
    });
  }, [stalenessRange, updateQueryParams]);

  useEffect(() => {
    updateQueryParams({
      [PRODUCT_UPDATED_PARAM]: updatedDateRange
        ? JSON.stringify(updatedDateRange)
        : null,
    });
  }, [updatedDateRange, updateQueryParams]);

  useEffect(() => {
    const serialized = areSortStatesEqual(sortState, buildDefaultSortState())
      ? null
      : JSON.stringify(sortState);
    updateQueryParams({
      [PRODUCT_SORT_PARAM]: serialized,
    });
  }, [sortState, updateQueryParams]);
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
  }, [activeInstanceId]);

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
  }, [productGroups]);

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

  const renderModeButtons = () => (
    <div className="flex flex-col items-center gap-2 lg:flex-1 lg:flex-row lg:items-center lg:justify-center">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
        Mode
      </p>
      <div className="flex flex-wrap items-center justify-center gap-2">
        {PRODUCT_MODE_OPTIONS.map((option) => {
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
        {onRefresh ? (
          <div className="flex justify-start lg:justify-end">
            <button
              type="button"
              onClick={onRefresh}
              disabled={!activeInstanceId || isLoading}
              className="inline-flex items-center justify-center rounded-full border border-neutral-300 px-4 py-1.5 text-sm font-semibold text-neutral-700 transition hover:bg-neutral-100 disabled:cursor-not-allowed disabled:border-neutral-200 disabled:text-neutral-400"
            >
              Refresh data
            </button>
          </div>
        ) : null}
      </div>

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
          onSuccess={(message) => {
            handleActionSuccess(message);
            setActiveAction(null);
          }}
        />
      ) : null}
    </div>
  );
}

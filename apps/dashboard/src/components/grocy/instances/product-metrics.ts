"use client";

import type { SortRule } from "@/components/grocy/list-controls";
import type { GrocyProductInventoryEntry } from "@/lib/grocy/types";
import { resolveQuantityOnHand, resolveQuantityUnit } from "./helpers";

export type ProductSortField =
  | "name"
  | "quantity"
  | "updated"
  | "status"
  | "daysSinceUpdate";

export type ProductSortState = SortRule<ProductSortField>[];

export type ProductStockCategory =
  | "critical"
  | "warning"
  | "caution"
  | "healthy"
  | "unconfigured";

export type ProductStockStatus = {
  tone: "critical" | "warning" | "caution" | "healthy" | "muted";
  label: string;
};

export const STOCK_STATUS_FILTER_OPTIONS: Array<{
  value: ProductStockCategory;
  label: string;
}> = [
  { value: "critical", label: "Out of stock" },
  { value: "warning", label: "Below minimum" },
  { value: "caution", label: "Near minimum" },
  { value: "healthy", label: "Healthy" },
  { value: "unconfigured", label: "Minimum not set" },
];

export const STOCK_STATUS_LABEL_BY_CATEGORY: Record<
  ProductStockCategory,
  string
> = STOCK_STATUS_FILTER_OPTIONS.reduce(
  (acc, option) => {
    acc[option.value] = option.label;
    return acc;
  },
  {} as Record<ProductStockCategory, string>,
);

export const STOCK_STATUS_CATEGORY_BY_LABEL: Record<
  string,
  ProductStockCategory
> = STOCK_STATUS_FILTER_OPTIONS.reduce(
  (acc, option) => {
    acc[option.label] = option.value;
    return acc;
  },
  {} as Record<string, ProductStockCategory>,
);

const STOCK_STATUS_PRIORITY: Record<ProductStockCategory, number> = {
  critical: 0,
  warning: 1,
  caution: 2,
  healthy: 3,
  unconfigured: 4,
};

export const STOCK_STATUS_TONE_BY_CATEGORY: Record<
  ProductStockCategory,
  ProductStockStatus["tone"]
> = {
  critical: "critical",
  warning: "warning",
  caution: "caution",
  healthy: "healthy",
  unconfigured: "muted",
};

export { STOCK_STATUS_PRIORITY };

export function resolveProductStockCategory(
  product: GrocyProductInventoryEntry,
): ProductStockCategory {
  const minimumRequired =
    Number.isFinite(product.min_stock_amount) && product.min_stock_amount > 0
      ? product.min_stock_amount
      : 0;
  const quantityOnHand = resolveQuantityOnHand(product);
  if (minimumRequired === 0) {
    return "unconfigured";
  }
  if (quantityOnHand <= 0) {
    return "critical";
  }
  if (quantityOnHand < minimumRequired) {
    return "warning";
  }
  if (quantityOnHand <= minimumRequired * 1.15) {
    return "caution";
  }
  return "healthy";
}

export function resolveProductStockStatus(
  product: GrocyProductInventoryEntry,
): ProductStockStatus {
  const category = resolveProductStockCategory(product);
  return {
    tone: STOCK_STATUS_TONE_BY_CATEGORY[category],
    label: STOCK_STATUS_LABEL_BY_CATEGORY[category],
  };
}

export function resolveDaysSinceUpdate(
  product: GrocyProductInventoryEntry,
): number {
  const now = Date.now();
  const lastUpdated = product.last_stock_updated_at.getTime();
  const diff = Math.max(0, now - lastUpdated);
  return Math.floor(diff / (1000 * 60 * 60 * 24));
}

export function compareProducts(
  a: GrocyProductInventoryEntry,
  b: GrocyProductInventoryEntry,
  sortState: ProductSortState,
): number {
  const appliedRules =
    sortState.length > 0 ? sortState : [{ field: "name", direction: "asc" }];

  for (const rule of appliedRules) {
    const directionMultiplier = rule.direction === "asc" ? 1 : -1;
    if (rule.field === "quantity") {
      const difference = resolveQuantityOnHand(a) - resolveQuantityOnHand(b);
      if (difference !== 0) {
        return difference * directionMultiplier;
      }
      continue;
    }
    if (rule.field === "status") {
      const difference =
        STOCK_STATUS_PRIORITY[resolveProductStockCategory(a)] -
        STOCK_STATUS_PRIORITY[resolveProductStockCategory(b)];
      if (difference !== 0) {
        return difference * directionMultiplier;
      }
      continue;
    }
    if (rule.field === "daysSinceUpdate") {
      const difference = resolveDaysSinceUpdate(a) - resolveDaysSinceUpdate(b);
      if (difference !== 0) {
        return difference * directionMultiplier;
      }
      continue;
    }
    if (rule.field === "updated") {
      const difference =
        a.last_stock_updated_at.getTime() - b.last_stock_updated_at.getTime();
      if (difference !== 0) {
        return difference * directionMultiplier;
      }
      continue;
    }
    const nameComparison = a.name.localeCompare(b.name) * directionMultiplier;
    if (nameComparison !== 0) {
      return nameComparison;
    }
  }

  return a.name.localeCompare(b.name);
}

export function formatMinimumStock(
  product: GrocyProductInventoryEntry,
): string {
  const { min_stock_amount: amount } = product;
  if (!Number.isFinite(amount) || amount < 0) {
    return "Not specified";
  }
  const formatted = amount.toLocaleString();
  const unit = resolveQuantityUnit(product);
  return unit ? `${formatted} ${unit}` : formatted;
}

export function formatBestBeforeDays(value: number): string {
  if (!Number.isFinite(value) || value <= 0) {
    return "Not specified";
  }
  const formatted = value.toLocaleString();
  return `${formatted} day${value === 1 ? "" : "s"}`;
}

export function formatTareWeight(
  product: GrocyProductInventoryEntry,
): string | null {
  const weight = product.tare_weight;
  if (!Number.isFinite(weight) || weight <= 0) {
    return null;
  }
  const formatted = weight.toLocaleString();
  const unit = resolveQuantityUnit(product);
  return unit ? `${formatted} ${unit}` : formatted;
}

export function normalizeDescription(description: string): string {
  return description
    .replace(/<\/p>\s*<p>/gi, "\n\n")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/?p>/gi, "")
    .replace(/<[^>]+>/g, "")
    .trim();
}

export function formatStockEntryAmount(
  amount: number,
  unit: string | null,
): string {
  const formatted = amount.toLocaleString(undefined, {
    maximumFractionDigits: 3,
  });
  return unit ? `${formatted} ${unit}` : formatted;
}

export function formatStockEntryDate(value: Date | null): string {
  if (!value) {
    return "—";
  }
  return value.toLocaleDateString(undefined, { dateStyle: "medium" });
}

export function formatStockEntryUnitPrice(
  pricePerUnit: number | null,
  unit: string | null,
): string {
  if (typeof pricePerUnit !== "number") {
    return "—";
  }
  const formatted = pricePerUnit.toLocaleString(undefined, {
    minimumFractionDigits: 6,
    maximumFractionDigits: 6,
  });
  return unit ? `${formatted} / ${unit}` : formatted;
}

export function formatStockEntryTotalPrice(
  pricePerUnit: number | null,
  amount: number,
): string {
  if (typeof pricePerUnit !== "number") {
    return "—";
  }
  const total = pricePerUnit * amount;
  return total.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatStockEntryLocation(
  locationId: number | null,
  locationNamesById: Record<number, string>,
): string {
  if (locationId == null) {
    return "—";
  }
  const name = locationNamesById[locationId];
  if (!name) {
    return `Location #${locationId}`;
  }
  return name;
}

export function formatShoppingLocationName(
  shoppingLocationId: number | null,
  shoppingLocationNamesById: Record<number, string>,
): string {
  if (shoppingLocationId == null) {
    return "—";
  }
  const name = shoppingLocationNamesById[shoppingLocationId];
  if (!name) {
    return `Shopping location #${shoppingLocationId}`;
  }
  return name;
}

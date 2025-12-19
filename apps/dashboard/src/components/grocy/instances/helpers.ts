import type { DateRange, NumericRange } from "@/components/grocy/list-controls";
import type {
  GrocyInstanceSummary,
  GrocyProductInventoryEntry,
} from "@/lib/grocy/types";

export function buildInstanceLabel(instance: GrocyInstanceSummary): string {
  return instance.location_name ?? `Instance ${instance.instance_index}`;
}

export function buildSearchTarget(instance: GrocyInstanceSummary): string {
  const addressParts = instance.address
    ? [
        instance.address.line1,
        instance.address.line2,
        instance.address.city,
        instance.address.state,
        instance.address.postal_code,
        instance.address.country,
      ].filter(Boolean)
    : [];

  const fields = [
    instance.instance_index,
    instance.location_name ?? "",
    ...instance.location_types,
    ...addressParts,
  ];

  return fields.join(" ").toLowerCase();
}

export function resolveProductGroup(
  product: GrocyProductInventoryEntry,
): string {
  return product.product_group_name ?? "Ungrouped";
}

export function resolveQuantityUnit(
  product: GrocyProductInventoryEntry,
): string | null {
  return (
    product.stock_quantity_unit_name ??
    product.purchase_quantity_unit_name ??
    product.consume_quantity_unit_name ??
    product.price_quantity_unit_name ??
    null
  );
}

export function resolveQuantityOnHand(
  product: GrocyProductInventoryEntry,
): number {
  return product.stocks.reduce((total, entry) => total + entry.amount, 0);
}

export function formatQuantityWithUnit(
  product: GrocyProductInventoryEntry,
): string {
  const quantity = resolveQuantityOnHand(product).toLocaleString();
  const unit = resolveQuantityUnit(product);
  return unit ? `${quantity} ${unit}` : quantity;
}

export function formatLastUpdated(timestamp: Date): string {
  return timestamp.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function matchesNumericRange(
  value: number,
  range: NumericRange | null,
): boolean {
  if (!range || !isNumericRangeActive(range)) {
    return true;
  }
  if (range.mode === "between") {
    if (typeof range.min !== "number" || typeof range.max !== "number") {
      return true;
    }
    return value >= range.min && value <= range.max;
  }
  if (range.mode === "lt") {
    if (typeof range.max !== "number") {
      return true;
    }
    return value < range.max;
  }
  if (range.mode === "gt") {
    if (typeof range.min !== "number") {
      return true;
    }
    return value > range.min;
  }
  if (typeof range.min !== "number") {
    return true;
  }
  return value === range.min;
}

export function matchesDateRange(
  value: Date,
  range: DateRange | null,
): boolean {
  if (!range || !isDateRangeActive(range)) {
    return true;
  }
  const valueDay = formatLocalDateKey(value);

  if (range.mode === "between") {
    if (!range.start || !range.end) {
      return true;
    }
    return valueDay >= range.start && valueDay <= range.end;
  }

  if (range.mode === "before") {
    if (!range.end) {
      return true;
    }
    return valueDay < range.end;
  }

  if (range.mode === "after") {
    if (!range.start) {
      return true;
    }
    return valueDay > range.start;
  }

  if (!range.start) {
    return true;
  }
  return valueDay === range.start;
}

export function isNumericRangeActive(range: NumericRange | null): boolean {
  if (!range) {
    return false;
  }
  if (range.mode === "between") {
    return typeof range.min === "number" && typeof range.max === "number";
  }
  if (range.mode === "lt") {
    return typeof range.max === "number";
  }
  return typeof range.min === "number";
}

export function isDateRangeActive(range: DateRange | null): boolean {
  if (!range) {
    return false;
  }
  if (range.mode === "between") {
    return Boolean(range.start && range.end);
  }
  if (range.mode === "before") {
    return Boolean(range.end);
  }
  return Boolean(range.start);
}

export function formatLocalDateKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

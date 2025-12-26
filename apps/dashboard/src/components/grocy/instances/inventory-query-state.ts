"use client";

import type { DateRange, NumericRange } from "@/components/grocy/list-controls";
import type {
  ProductSortField,
  ProductSortState,
  ProductStockCategory,
} from "./product-metrics";
import { STOCK_STATUS_PRIORITY } from "./product-metrics";

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

export const DEFAULT_SORT_STATE: ProductSortState = [
  { field: "name", direction: "asc" },
];

export const PRODUCT_SORT_OPTIONS: Array<{
  label: string;
  value: ProductSortField;
}> = [
  { label: "Product name", value: "name" },
  { label: "Stock status", value: "status" },
  { label: "Amount in stock", value: "quantity" },
  { label: "Days since last update", value: "daysSinceUpdate" },
  { label: "Last updated", value: "updated" },
];

export function buildDefaultSortState(): ProductSortState {
  return DEFAULT_SORT_STATE.map((rule) => ({ ...rule }));
}

export function parseStringArrayParam(raw: string | null): string[] {
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

export function serializeStringArrayParam(value: string[]): string | null {
  return value.length > 0 ? JSON.stringify(value) : null;
}

export function parseStockStatusParam(
  raw: string | null,
): ProductStockCategory[] {
  const values = parseStringArrayParam(raw);
  return values.filter(
    (value): value is ProductStockCategory => value in STOCK_STATUS_PRIORITY,
  );
}

export function parseNumericRangeParam(
  raw: string | null,
): NumericRange | null {
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

export function serializeNumericRangeParam(
  value: NumericRange | null,
): string | null {
  return value ? JSON.stringify(value) : null;
}

export function parseDateRangeParam(raw: string | null): DateRange | null {
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

export function serializeDateRangeParam(
  value: DateRange | null,
): string | null {
  return value ? JSON.stringify(value) : null;
}

export function parseSortStateParam(raw: string | null): ProductSortState {
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

export function serializeSortStateParam(
  value: ProductSortState,
): string | null {
  return areSortStatesEqual(value, buildDefaultSortState())
    ? null
    : JSON.stringify(value);
}

export function areArraysEqual<T>(a: T[], b: T[]): boolean {
  if (a.length !== b.length) {
    return false;
  }
  return a.every((value, index) => value === b[index]);
}

export function areNumericRangesEqual(
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

export function areDateRangesEqual(
  a: DateRange | null,
  b: DateRange | null,
): boolean {
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

export function areSortStatesEqual(
  a: ProductSortState,
  b: ProductSortState,
): boolean {
  if (a.length !== b.length) {
    return false;
  }
  return a.every(
    (rule, index) =>
      rule.field === b[index]?.field && rule.direction === b[index]?.direction,
  );
}

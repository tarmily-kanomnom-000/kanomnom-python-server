import type {
  GrocyInstanceSummary,
  GrocyLocation,
  GrocyProductInventoryEntry,
  GrocyShoppingLocation,
  GrocyStockEntry,
} from "@/lib/grocy/types";

type GrocyLocationPayload = Omit<GrocyLocation, "row_created_timestamp"> & {
  row_created_timestamp: string;
};

type GrocyInstanceSummaryPayload = Omit<GrocyInstanceSummary, "locations"> & {
  locations: GrocyLocationPayload[];
  shopping_locations: GrocyShoppingLocationPayload[];
};

type GrocyShoppingLocationPayload = Omit<
  GrocyShoppingLocation,
  "row_created_timestamp"
> & {
  row_created_timestamp: string;
};

export type ListInstancesResponsePayload = {
  instances: GrocyInstanceSummaryPayload[];
};

type GrocyStockEntryPayload = Omit<
  GrocyStockEntry,
  | "best_before_date"
  | "purchased_date"
  | "opened_date"
  | "row_created_timestamp"
> & {
  best_before_date: string | null;
  purchased_date: string | null;
  opened_date: string | null;
  row_created_timestamp: string;
};

type GrocyProductInventoryEntryPayload = Omit<
  GrocyProductInventoryEntry,
  "last_stock_updated_at" | "stocks"
> & {
  last_stock_updated_at: string;
  stocks: GrocyStockEntryPayload[];
};

export type GrocyProductsResponsePayload = {
  instance_index: string;
  products: GrocyProductInventoryEntryPayload[];
};

export function deserializeGrocyLocation(
  location: GrocyLocationPayload,
): GrocyLocation {
  return {
    ...location,
    row_created_timestamp: new Date(location.row_created_timestamp),
  };
}

export function deserializeGrocyInstanceSummary(
  summary: GrocyInstanceSummaryPayload,
): GrocyInstanceSummary {
  return {
    ...summary,
    locations: summary.locations.map(deserializeGrocyLocation),
    shopping_locations: summary.shopping_locations.map(
      deserializeGrocyShoppingLocation,
    ),
  };
}

function deserializeGrocyShoppingLocation(
  location: GrocyShoppingLocationPayload,
): GrocyShoppingLocation {
  return {
    ...location,
    row_created_timestamp: new Date(location.row_created_timestamp),
  };
}

export function deserializeGrocyInstanceSummaries(
  payload: ListInstancesResponsePayload,
): GrocyInstanceSummary[] {
  return payload.instances.map(deserializeGrocyInstanceSummary);
}

export function deserializeGrocyStockEntry(
  entry: GrocyStockEntryPayload,
): GrocyStockEntry {
  return {
    ...entry,
    best_before_date: entry.best_before_date
      ? new Date(entry.best_before_date)
      : null,
    purchased_date: entry.purchased_date
      ? new Date(entry.purchased_date)
      : null,
    opened_date: entry.opened_date ? new Date(entry.opened_date) : null,
    row_created_timestamp: new Date(entry.row_created_timestamp),
    note_metadata: entry.note_metadata ?? null,
  };
}

export function deserializeGrocyProductInventoryEntry(
  product: GrocyProductInventoryEntryPayload,
): GrocyProductInventoryEntry {
  return {
    ...product,
    last_stock_updated_at: new Date(product.last_stock_updated_at),
    stocks: product.stocks?.map(deserializeGrocyStockEntry) ?? [],
  };
}

export function deserializeGrocyProducts(
  payload: GrocyProductsResponsePayload,
): GrocyProductInventoryEntry[] {
  return payload.products.map(deserializeGrocyProductInventoryEntry);
}

import type { ShoppingListItem } from "./shopping-list-types";
import type { GrocyProductInventoryEntry } from "./types";

export function buildOptimisticItem(
  product: GrocyProductInventoryEntry,
  quantity: number,
): ShoppingListItem {
  const now = new Date().toISOString();
  return {
    id:
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `${Date.now()}-${product.id}`,
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
    modified_at: now,
  };
}

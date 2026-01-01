import type {
  AddItemRequest,
  ShoppingListItem,
} from "@/lib/grocy/shopping-list-types";

export async function bulkAddShoppingListItems(
  instanceIndex: string,
  items: AddItemRequest[],
): Promise<ShoppingListItem[]> {
  const response = await fetch(
    `/api/grocy/${instanceIndex}/shopping-list/items/bulk`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(items),
    },
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || "Failed to bulk add shopping list items");
  }
  return (await response.json()) as ShoppingListItem[];
}

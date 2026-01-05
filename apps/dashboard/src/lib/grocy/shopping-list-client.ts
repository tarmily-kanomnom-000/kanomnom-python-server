import { runGrocyMutation } from "@/lib/grocy/mutation-runner";
import type {
  AddItemRequest,
  ShoppingListItem,
} from "@/lib/grocy/shopping-list-types";

export async function bulkAddShoppingListItems(
  instanceIndex: string,
  items: AddItemRequest[],
): Promise<ShoppingListItem[]> {
  return runGrocyMutation<ShoppingListItem[]>({
    request: async () => {
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
        const message =
          (data as { error?: string }).error ||
          (data as { detail?: string }).detail ||
          response.statusText ||
          "Failed to bulk add shopping list items";
        const error = new Error(message) as Error & { status?: number };
        error.status = response.status;
        throw error;
      }
      return (await response.json()) as ShoppingListItem[];
    },
  });
}

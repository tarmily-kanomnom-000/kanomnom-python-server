import type { ShoppingList } from "@/lib/grocy/shopping-list-types";
import { shoppingListKey, shoppingSyncQueueKey } from "./cache-keys";
import {
  clearStoredPayload,
  readStoredPayload,
  writeStoredPayload,
} from "./local-storage";

export function readCachedShoppingList(
  instanceIndex: string,
): ShoppingList | null {
  return readCache<ShoppingList>(shoppingListCacheKey(instanceIndex));
}

export function writeCachedShoppingList(
  instanceIndex: string,
  list: ShoppingList,
): boolean {
  return writeCache(shoppingListCacheKey(instanceIndex), list);
}

export function clearCachedShoppingList(instanceIndex: string): void {
  clearCache(shoppingListCacheKey(instanceIndex));
}

export function shoppingListCacheKey(instanceIndex: string): string {
  return shoppingListKey(instanceIndex);
}

export function syncQueueKey(): string {
  return shoppingSyncQueueKey();
}

export function readCache<T>(key: string): T | null {
  return readStoredPayload<T>(key);
}

export function writeCache<T>(key: string, data: T): boolean {
  return writeStoredPayload<T>(key, data);
}

export function clearCache(key: string): void {
  clearStoredPayload(key);
}

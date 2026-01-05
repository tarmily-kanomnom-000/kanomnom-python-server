import type { ShoppingList } from "@/lib/grocy/shopping-list-types";

import type { StoredPayload } from "./types";
import { notifyPersistenceFailure } from "./status";

const STORAGE_PREFIX = "kanomnom:pwa";

export function shoppingListCacheKey(instanceIndex: string): string {
  return buildKey(["shopping-list", "active", instanceIndex]);
}

export function syncQueueKey(): string {
  return buildKey(["shopping-list", "sync-queue"]);
}

function buildKey(segments: string[]): string {
  return [STORAGE_PREFIX, ...segments].join(":");
}

function getLocalStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage;
  } catch (error) {
    console.warn("localStorage unavailable; offline cache disabled.", error);
    return null;
  }
}

export function readCache<T>(key: string): T | null {
  const storage = getLocalStorage();
  if (!storage) {
    return null;
  }
  const raw = storage.getItem(key);
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as StoredPayload<T>;
    return parsed.data;
  } catch (error) {
    storage.removeItem(key);
    console.warn("Cleared corrupted offline cache entry", { key, error });
    return null;
  }
}

export function writeCache<T>(key: string, data: T): boolean {
  const storage = getLocalStorage();
  if (!storage) {
    return false;
  }
  const payload: StoredPayload<T> = {
    storedAt: Date.now(),
    data,
  };
  try {
    storage.setItem(key, JSON.stringify(payload));
    return true;
  } catch (error) {
    console.warn("Failed to persist offline cache entry", { key, error });
    notifyPersistenceFailure();
    return false;
  }
}

export function clearCache(key: string): void {
  const storage = getLocalStorage();
  if (!storage) {
    return;
  }
  storage.removeItem(key);
}

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

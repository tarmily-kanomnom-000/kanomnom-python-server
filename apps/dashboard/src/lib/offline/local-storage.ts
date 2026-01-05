import { notifyPersistenceFailure } from "./status";
import type { StoredPayload } from "./types";

export const STORAGE_PREFIX = "kanomnom:pwa";

export function buildStorageKey(segments: string[]): string {
  return [STORAGE_PREFIX, ...segments].join(":");
}

export function getLocalStorage(): Storage | null {
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

export function readStoredPayload<T>(key: string): T | null {
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

export function writeStoredPayload<T>(key: string, data: T): boolean {
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

export function clearStoredPayload(key: string): void {
  const storage = getLocalStorage();
  if (!storage) {
    return;
  }
  storage.removeItem(key);
}

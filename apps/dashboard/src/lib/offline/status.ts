import type {
  ConnectivityListener,
  PersistenceListener,
  SyncListener,
} from "./types";

let persistenceFailed = false;
const persistenceListeners = new Set<PersistenceListener>();
const syncListeners = new Set<SyncListener>();
const connectivityListeners = new Set<ConnectivityListener>();

let lastSyncAt: number | null = null;
let hadSyncDrop = false;
let currentOnline: boolean | null = null;

export function subscribePersistenceFailure(
  listener: PersistenceListener,
): () => void {
  persistenceListeners.add(listener);
  return () => persistenceListeners.delete(listener);
}

export function notifyPersistenceFailure(): void {
  persistenceFailed = true;
  for (const listener of persistenceListeners) {
    listener(true);
  }
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("offline-persistence-failed"));
  }
}

export function hasPersistenceFailure(): boolean {
  return persistenceFailed;
}

export function getOnlineStatus(): boolean {
  if (currentOnline === null) {
    if (typeof navigator === "undefined") {
      return true;
    }
    currentOnline = navigator.onLine !== false;
  }
  return currentOnline;
}

export function setOnlineStatus(online: boolean): void {
  currentOnline = online;
}

export function subscribeOnlineStatus(
  listener: ConnectivityListener,
): () => void {
  connectivityListeners.add(listener);
  listener(getOnlineStatus());
  return () => connectivityListeners.delete(listener);
}

export function notifyConnectivityStatus(online: boolean): void {
  for (const listener of connectivityListeners) {
    listener(online);
  }
}

export function subscribeSyncInfo(listener: SyncListener): () => void {
  syncListeners.add(listener);
  return () => syncListeners.delete(listener);
}

export function notifySyncInfo(
  queueSize: number,
  lastError: string | null = null,
): void {
  const info = { lastSyncAt, queueSize, hadSyncDrop, lastError };
  for (const listener of syncListeners) {
    listener(info);
  }
}

export function recordSyncDrop(): void {
  hadSyncDrop = true;
}

export function setLastSyncAt(timestamp: number | null): void {
  lastSyncAt = timestamp;
}

export function getSyncState(): {
  lastSyncAt: number | null;
  hadSyncDrop: boolean;
} {
  return { lastSyncAt, hadSyncDrop };
}

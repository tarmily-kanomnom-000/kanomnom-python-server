import type {
  ConnectivityListener,
  PersistenceListener,
  SyncInfo,
  SyncListener,
} from "./types";

let persistenceFailed = false;
const persistenceListeners = new Set<PersistenceListener>();
const syncListeners = new Set<SyncListener>();
const connectivityListeners = new Set<ConnectivityListener>();

let lastSyncAt: number | null = null;
let hadSyncDrop = false;
let currentOnline: boolean | null = null;
let queueSize = 0;
let lastSyncError: string | null = null;

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
  listener(getSyncInfo());
  return () => syncListeners.delete(listener);
}

export function notifySyncInfo(
  queueSizeValue: number,
  lastError: string | null = null,
): void {
  queueSize = Number.isFinite(queueSizeValue) ? queueSizeValue : 0;
  lastSyncError = lastError;
  const info = getSyncInfo();
  for (const listener of syncListeners) {
    listener(info);
  }
}

export function hydrateSyncSnapshot(
  queueSizeValue: number,
  error: string | null = null,
): void {
  queueSize = Number.isFinite(queueSizeValue) ? queueSizeValue : 0;
  lastSyncError = error;
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

export function getSyncInfo(): SyncInfo {
  return {
    lastSyncAt,
    queueSize,
    hadSyncDrop,
    lastError: lastSyncError,
  };
}

export function getConnectivitySnapshot(): {
  online: boolean;
  persistenceDegraded: boolean;
  sync: SyncInfo;
} {
  return {
    online: getOnlineStatus(),
    persistenceDegraded: hasPersistenceFailure(),
    sync: getSyncInfo(),
  };
}

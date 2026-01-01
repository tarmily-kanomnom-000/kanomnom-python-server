import { useEffect, useState } from "react";
import {
  getOnlineStatus,
  hasPersistenceFailure,
  readSyncQueue,
  subscribeOnlineStatus,
  subscribePersistenceFailure,
  subscribeSyncInfo,
} from "@/lib/offline/shopping-list-cache";

type SyncStatus = {
  isOnline: boolean;
  queueSize: number;
  lastSyncAt: number | null;
  persistenceDegraded: boolean;
  hadSyncDrop: boolean;
  lastError?: string | null;
};

export function useSyncStatus(): SyncStatus {
  const [status, setStatus] = useState<SyncStatus>({
    isOnline: getOnlineStatus(),
    queueSize: readSyncQueue().length,
    lastSyncAt: null,
    persistenceDegraded: hasPersistenceFailure(),
    hadSyncDrop: false,
    lastError: null,
  });

  useEffect(() => {
    const unsubscribeOnline = subscribeOnlineStatus((online) =>
      setStatus((prev) => ({ ...prev, isOnline: online })),
    );

    const unsubscribePersistence = subscribePersistenceFailure(() => {
      setStatus((prev) => ({ ...prev, persistenceDegraded: true }));
    });
    const unsubscribeSync = subscribeSyncInfo((info) => {
      setStatus((prev) => ({
        ...prev,
        queueSize: info.queueSize,
        lastSyncAt: info.lastSyncAt,
        hadSyncDrop: info.hadSyncDrop,
        lastError: info.lastError ?? prev.lastError,
      }));
    });

    // Initial snapshot
    setStatus((prev) => ({
      ...prev,
      isOnline: getOnlineStatus(),
      queueSize: readSyncQueue().length,
      persistenceDegraded: hasPersistenceFailure(),
      lastError: null,
    }));

    return () => {
      unsubscribeOnline();
      unsubscribePersistence();
      unsubscribeSync();
    };
  }, []);

  return status;
}

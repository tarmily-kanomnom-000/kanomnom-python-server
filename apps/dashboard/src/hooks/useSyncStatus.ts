import { useEffect, useState } from "react";
import {
  getOnlineStatus,
  hasPersistenceFailure,
  getSyncInfo,
  subscribeOnlineStatus,
  subscribePersistenceFailure,
  subscribeSyncInfo,
} from "@/lib/offline/shopping-list-cache";

const initialSyncSnapshot = getSyncInfo();

type SyncStatus = {
  isOnline: boolean;
  queueSize: number;
  lastSyncAt: number | null;
  persistenceDegraded: boolean;
  hadSyncDrop: boolean;
  lastError: string | null;
};

export function useSyncStatus(): SyncStatus {
  const [status, setStatus] = useState<SyncStatus>({
    isOnline: getOnlineStatus(),
    queueSize: initialSyncSnapshot.queueSize,
    lastSyncAt: initialSyncSnapshot.lastSyncAt,
    persistenceDegraded: hasPersistenceFailure(),
    hadSyncDrop: initialSyncSnapshot.hadSyncDrop,
    lastError: initialSyncSnapshot.lastError,
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
        lastError: info.lastError,
      }));
    });

    // Initial snapshot
    const syncSnapshot = getSyncInfo();
    setStatus((prev) => ({
      ...prev,
      isOnline: getOnlineStatus(),
      queueSize: syncSnapshot.queueSize,
      lastSyncAt: syncSnapshot.lastSyncAt,
      hadSyncDrop: syncSnapshot.hadSyncDrop,
      persistenceDegraded: hasPersistenceFailure(),
      lastError: syncSnapshot.lastError,
    }));

    return () => {
      unsubscribeOnline();
      unsubscribePersistence();
      unsubscribeSync();
    };
  }, []);

  return status;
}

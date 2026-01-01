import { useMemo } from "react";
import { useSyncStatus } from "./useSyncStatus";

export type ConnectivitySnapshot = {
  online: boolean;
  offlineReason: "offline" | "persistence" | "sync_drop" | null;
  queueSize: number;
};

export function useConnectivityStatus(): ConnectivitySnapshot {
  const { isOnline, persistenceDegraded, hadSyncDrop, queueSize } =
    useSyncStatus();

  return useMemo<ConnectivitySnapshot>(() => {
    if (!isOnline) {
      return { online: false, offlineReason: "offline", queueSize };
    }
    if (persistenceDegraded) {
      return { online: true, offlineReason: "persistence", queueSize };
    }
    if (hadSyncDrop) {
      return { online: true, offlineReason: "sync_drop", queueSize };
    }
    return { online: true, offlineReason: null, queueSize };
  }, [hadSyncDrop, isOnline, persistenceDegraded, queueSize]);
}

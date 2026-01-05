import { readSyncQueue, writeSyncQueue } from "./queue";
import { syncPendingActions } from "./sync";
import {
  getOnlineStatus,
  notifyConnectivityStatus,
  notifySyncInfo,
  setOnlineStatus,
} from "./status";

let listenersAttached = false;

export function setupOnlineEventListeners(): void {
  if (typeof window === "undefined" || listenersAttached) {
    return;
  }
  listenersAttached = true;

  window.addEventListener("online", () => {
    setOnlineStatus(true);
    notifyConnectivityStatus(true);
    notifySyncInfo(readSyncQueue().length, null);
    console.log("Back online - syncing pending actions...");
    void syncPendingActions();
  });

  window.addEventListener("offline", () => {
    setOnlineStatus(false);
    notifyConnectivityStatus(false);
    console.log("Gone offline - shopping list will use cached data");
    const queue = readSyncQueue();
    writeSyncQueue(queue);
  });
}

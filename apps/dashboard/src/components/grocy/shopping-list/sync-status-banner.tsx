"use client";

import { useSyncStatus } from "@/hooks/useSyncStatus";

type Props = {
  className?: string;
};

export function SyncStatusBanner({ className }: Props) {
  const { isOnline, queueSize, persistenceDegraded, hadSyncDrop, lastError } =
    useSyncStatus();

  const isPending = queueSize > 0;

  if (isOnline && !isPending && !persistenceDegraded && !hadSyncDrop) {
    return null;
  }

  const bg = !isOnline
    ? "bg-yellow-100 border-yellow-300 text-yellow-900"
    : persistenceDegraded
      ? "bg-red-100 border-red-300 text-red-900"
      : hadSyncDrop
        ? "bg-orange-100 border-orange-300 text-orange-900"
        : "bg-blue-100 border-blue-300 text-blue-900";

  const message = !isOnline
    ? "Offline: changes will sync when back online"
    : persistenceDegraded
      ? "Offline storage limited: changes may not persist"
      : hadSyncDrop
        ? "Some changes failed to sync; please retry."
        : lastError
          ? `Sync issue: ${lastError}`
          : `Syncing pending changes (${queueSize})...`;

  return (
    <div
      className={`${bg} border px-3 py-2 text-sm ${className ?? ""}`.trim()}
      role="status"
      aria-live="polite"
    >
      {message}
    </div>
  );
}

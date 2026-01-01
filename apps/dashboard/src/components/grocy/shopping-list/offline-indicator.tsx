"use client";

interface OfflineIndicatorProps {
  isOnline: boolean;
}

export function OfflineIndicator({ isOnline }: OfflineIndicatorProps) {
  if (isOnline) {
    return null;
  }

  return (
    <div className="fixed bottom-4 left-1/2 z-50 -translate-x-1/2 transform">
      <div className="flex items-center gap-2 rounded-full bg-orange-100 border border-orange-300 px-4 py-2 shadow-lg">
        <div className="h-2 w-2 rounded-full bg-orange-500 animate-pulse"></div>
        <span className="text-sm font-medium text-orange-900">
          Offline Mode - Changes will sync when online
        </span>
      </div>
    </div>
  );
}

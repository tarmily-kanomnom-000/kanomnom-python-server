"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useOfflineShoppingList } from "@/hooks/useOfflineShoppingList";
import { readCachedShoppingList } from "@/lib/offline/shopping-list-cache";

interface ShoppingListButtonProps {
  instanceIndex: string;
}

export function ShoppingListButton({ instanceIndex }: ShoppingListButtonProps) {
  const router = useRouter();
  const [hasActiveList, setHasActiveList] = useState<boolean | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [hasPrefetched, setHasPrefetched] = useState(false);
  const { isOnline, loadActiveListWithCache } =
    useOfflineShoppingList(instanceIndex);
  const prefetchShoppingList = useCallback(() => {
    void router.prefetch(`/inventory/${instanceIndex}/shopping-list`);
  }, [instanceIndex, router]);

  useEffect(() => {
    let isMounted = true;
    setHasActiveList(null);
    const load = async () => {
      const cached = readCachedShoppingList(instanceIndex);
      if (cached && isMounted) {
        setHasActiveList(true);
      }
      try {
        const list = await loadActiveListWithCache();
        if (!isMounted) {
          return;
        }
        setHasActiveList(list !== null);
      } catch (error) {
        console.error("Failed to load shopping list for instance", error);
        if (isMounted) {
          setHasActiveList(Boolean(cached));
        }
      }
    };
    void load();

    // Preload the shopping list route when online so it works offline.
    if (isOnline) {
      prefetchShoppingList();
    }
    return () => {
      isMounted = false;
    };
  }, [instanceIndex, isOnline, loadActiveListWithCache, prefetchShoppingList]);

  useEffect(() => {
    if (!hasActiveList || !isOnline || hasPrefetched) {
      return;
    }
    setHasPrefetched(true);
    prefetchShoppingList();
    // Ask the service worker to cache the shopping list page for offline navigation.
    if ("serviceWorker" in navigator && navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage({
        type: "CACHE_URLS",
        urls: [`/inventory/${instanceIndex}/shopping-list`],
      });
    } else if ("serviceWorker" in navigator) {
      navigator.serviceWorker.ready
        .then((reg) => {
          reg.active?.postMessage({
            type: "CACHE_URLS",
            urls: [`/inventory/${instanceIndex}/shopping-list`],
          });
        })
        .catch((error) => {
          console.warn("Service worker not ready for prefetch", error);
          setHasPrefetched(false);
        });
    }
  }, [
    hasActiveList,
    hasPrefetched,
    instanceIndex,
    isOnline,
    prefetchShoppingList,
  ]);

  const handleGenerate = async () => {
    if (!isOnline) {
      alert("Generating a shopping list requires an internet connection.");
      return;
    }
    setIsGenerating(true);
    try {
      const response = await fetch(
        `/api/grocy/${instanceIndex}/shopping-list/generate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ merge_with_existing: false }),
        },
      );

      if (!response.ok) {
        const errorData = await response.json();
        alert(errorData.detail || "Failed to generate shopping list");
        return;
      }

      // Navigate to the shopping list page
      router.push(`/inventory/${instanceIndex}/shopping-list`);
    } catch (error) {
      console.error("Error generating shopping list:", error);
      alert("Failed to generate shopping list");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleView = () => {
    const targetUrl = `/inventory/${instanceIndex}/shopping-list`;
    // In offline mode, force a full navigation so the service worker can serve cached page.
    if (!isOnline) {
      window.location.assign(targetUrl);
      return;
    }
    router.push(targetUrl);
  };

  if (hasActiveList === null) {
    return null; // Still checking
  }

  if (hasActiveList) {
    return (
      <button
        type="button"
        onClick={handleView}
        className="inline-flex items-center justify-center rounded-full border border-blue-300 bg-blue-50 px-4 py-1.5 text-sm font-semibold text-blue-700 transition hover:bg-blue-100"
      >
        View Shopping List
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={handleGenerate}
      disabled={isGenerating}
      className="inline-flex items-center justify-center rounded-full border border-green-300 bg-green-50 px-4 py-1.5 text-sm font-semibold text-green-700 transition hover:bg-green-100 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400"
    >
      {isGenerating ? "Generating..." : "Generate Shopping List"}
    </button>
  );
}

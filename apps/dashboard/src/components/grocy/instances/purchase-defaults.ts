import { useEffect, useRef, useState } from "react";

import { fetchBulkPurchaseEntryDefaults } from "@/lib/grocy/client";
import type {
  GrocyProductInventoryEntry,
  PurchaseEntryDefaults,
} from "@/lib/grocy/types";

const PURCHASE_DEFAULTS_BATCH_SIZE = 25;
const PURCHASE_DEFAULT_PREFETCH_CONCURRENCY = 4;
const PURCHASE_DEFAULT_PREFETCH_RETRY_BASE_DELAY_MS = 5_000;
const PURCHASE_DEFAULT_PREFETCH_RETRY_MAX_DELAY_MS = 60_000;

const buildPurchaseDefaultsCacheKey = (
  productId: number,
  shoppingLocationId: number | null,
): string => `${productId}:${shoppingLocationId ?? "__none__"}`;

function chunkArray<T>(items: T[], size: number): T[][] {
  if (size <= 0) {
    return [items.slice()];
  }
  const chunks: T[][] = [];
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size));
  }
  return chunks;
}

export function usePurchaseDefaultsPrefetch({
  isAdmin,
  activeInstanceId,
  products,
}: {
  isAdmin: boolean;
  activeInstanceId: string | null;
  products: GrocyProductInventoryEntry[];
}): {
  defaultsByProductId: Record<number, PurchaseEntryDefaults>;
  error: string | null;
  resetKey: string;
} {
  const [purchaseDefaultsByProductId, setPurchaseDefaultsByProductId] =
    useState<Record<number, PurchaseEntryDefaults>>({});
  const [purchaseDefaultsError, setPurchaseDefaultsError] = useState<
    string | null
  >(null);
  const prefetchedDefaultsRef = useRef<Set<string>>(new Set());
  const prefetchRetryAttemptsRef = useRef(0);
  const prefetchRetryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [prefetchRetrySignal, setPrefetchRetrySignal] = useState(0);
  const instanceDefaultsResetKey = activeInstanceId ?? "__none__";

  useEffect(() => {
    void instanceDefaultsResetKey;
    prefetchedDefaultsRef.current = new Set();
    setPurchaseDefaultsByProductId({});
    setPurchaseDefaultsError(null);
    prefetchRetryAttemptsRef.current = 0;
    if (prefetchRetryTimeoutRef.current) {
      clearTimeout(prefetchRetryTimeoutRef.current);
      prefetchRetryTimeoutRef.current = null;
    }
    setPrefetchRetrySignal((value) => value + 1);
  }, [instanceDefaultsResetKey]);

  useEffect(() => {
    void prefetchRetrySignal;
    if (!isAdmin) {
      if (prefetchRetryTimeoutRef.current) {
        clearTimeout(prefetchRetryTimeoutRef.current);
        prefetchRetryTimeoutRef.current = null;
      }
      return;
    }
    if (!activeInstanceId) {
      return;
    }
    const shoppingLocationId: number | null = null;
    const missingProductIds = products
      .map((product) => ({
        id: product.id,
        key: buildPurchaseDefaultsCacheKey(product.id, shoppingLocationId),
      }))
      .filter((entry) => !prefetchedDefaultsRef.current.has(entry.key))
      .map((entry) => entry.id);
    if (missingProductIds.length === 0) {
      prefetchRetryAttemptsRef.current = 0;
      setPurchaseDefaultsError(null);
      if (prefetchRetryTimeoutRef.current) {
        clearTimeout(prefetchRetryTimeoutRef.current);
        prefetchRetryTimeoutRef.current = null;
      }
      return;
    }
    setPurchaseDefaultsError(null);
    let cancelled = false;
    const batches = chunkArray(missingProductIds, PURCHASE_DEFAULTS_BATCH_SIZE);

    const runPrefetch = async () => {
      const workerCount = Math.min(
        PURCHASE_DEFAULT_PREFETCH_CONCURRENCY,
        batches.length,
      );
      const runWorker = async (workerIndex: number) => {
        for (
          let batchIndex = workerIndex;
          batchIndex < batches.length;
          batchIndex += workerCount
        ) {
          const batch = batches[batchIndex];
          const defaults = await fetchBulkPurchaseEntryDefaults(
            activeInstanceId,
            batch,
            shoppingLocationId,
          );
          if (cancelled) {
            return;
          }
          setPurchaseDefaultsByProductId((current) => {
            const next = { ...current };
            defaults.forEach((entry) => {
              next[entry.productId] = entry;
              prefetchedDefaultsRef.current.add(
                buildPurchaseDefaultsCacheKey(
                  entry.productId,
                  entry.shoppingLocationId ?? null,
                ),
              );
            });
            return next;
          });
        }
      };

      await Promise.all(
        Array.from({ length: workerCount }, (_, index) => runWorker(index)),
      );
    };

    const loadDefaults = async () => {
      try {
        await runPrefetch();
        if (cancelled) {
          return;
        }
        prefetchRetryAttemptsRef.current = 0;
        if (prefetchRetryTimeoutRef.current) {
          clearTimeout(prefetchRetryTimeoutRef.current);
          prefetchRetryTimeoutRef.current = null;
        }
        setPurchaseDefaultsError(null);
      } catch (error) {
        if (cancelled) {
          return;
        }
        console.warn("Failed to prefetch purchase entry defaults", error);
        const attempt = prefetchRetryAttemptsRef.current + 1;
        prefetchRetryAttemptsRef.current = attempt;
        const delay = Math.min(
          PURCHASE_DEFAULT_PREFETCH_RETRY_MAX_DELAY_MS,
          PURCHASE_DEFAULT_PREFETCH_RETRY_BASE_DELAY_MS * attempt,
        );
        setPurchaseDefaultsError(
          `Unable to preload purchase metadata. We'll retry automatically in ${Math.round(delay / 1000)} seconds.`,
        );
        if (prefetchRetryTimeoutRef.current) {
          clearTimeout(prefetchRetryTimeoutRef.current);
        }
        prefetchRetryTimeoutRef.current = setTimeout(() => {
          setPrefetchRetrySignal((value) => value + 1);
        }, delay);
      }
    };

    void loadDefaults();
    return () => {
      cancelled = true;
      if (prefetchRetryTimeoutRef.current) {
        clearTimeout(prefetchRetryTimeoutRef.current);
        prefetchRetryTimeoutRef.current = null;
      }
    };
  }, [activeInstanceId, isAdmin, products, prefetchRetrySignal]);

  return {
    defaultsByProductId: purchaseDefaultsByProductId,
    error: purchaseDefaultsError,
    resetKey: instanceDefaultsResetKey,
  };
}

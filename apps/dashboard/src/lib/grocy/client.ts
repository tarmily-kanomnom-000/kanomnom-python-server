import axios from "axios";

import {
  deserializeGrocyProductInventoryEntry,
  deserializeGrocyProducts,
  deserializeGrocyStockEntry,
  type GrocyProductInventoryEntryPayload,
  type GrocyProductsResponsePayload,
  type GrocyStockEntryPayload,
} from "@/lib/grocy/transformers";
import type {
  GrocyProductInventoryEntry,
  GrocyStockEntry,
  InventoryAdjustmentRequestPayload,
  InventoryCorrectionRequestPayload,
  PurchaseEntryCalculation,
  PurchaseEntryDefaults,
  PurchaseEntryRequestPayload,
} from "@/lib/grocy/types";
import {
  fetchWithOfflineCache,
  grocyProductsCacheKey,
  readCachedProducts,
  upsertCachedProduct,
} from "@/lib/offline/grocy-cache";
import { isOnline } from "@/lib/offline/shopping-list-cache";

const productCache = new Map<string, Promise<GrocyProductInventoryEntry[]>>();

export function invalidateGrocyProductsClientCache(
  instanceIndex: string,
): void {
  productCache.delete(instanceIndex);
}

type FetchOptions = {
  forceRefresh?: boolean;
};

export type PurchaseSubmissionResult = {
  product: GrocyProductInventoryEntry;
  newEntries: GrocyStockEntry[];
};

export async function fetchGrocyProduct(
  instanceIndex: string,
  productId: number,
): Promise<GrocyProductInventoryEntry> {
  const cachedProducts = readCachedProducts(instanceIndex);
  const cachedProduct =
    cachedProducts?.find((entry) => entry.id === productId) ?? null;
  try {
    const response = await axios.get(
      `/api/grocy/${instanceIndex}/products/${productId}`,
      {
        adapter: "fetch",
        fetchOptions: { cache: "no-store" },
      },
    );
    const entry = deserializeGrocyProductInventoryEntry(
      response.data as GrocyProductInventoryEntryPayload,
    );
    upsertCachedProduct(instanceIndex, entry);
    return entry;
  } catch (error) {
    if (
      cachedProduct &&
      (!isOnline() || (axios.isAxiosError(error) && !error.response))
    ) {
      return cachedProduct;
    }
    throw error;
  }
}

export async function fetchGrocyProducts(
  instanceIndex: string,
  { forceRefresh = false }: FetchOptions = {},
): Promise<GrocyProductInventoryEntry[]> {
  const cached = productCache.get(instanceIndex);
  if (!forceRefresh && cached) {
    return cached;
  }

  const path = `/api/grocy/${instanceIndex}/products${
    forceRefresh ? "?forceRefresh=1" : ""
  }`;
  const pending = fetchWithOfflineCache<GrocyProductInventoryEntry[]>({
    cacheKey: grocyProductsCacheKey(instanceIndex),
    fetcher: async () => {
      const response = await axios.get(path, {
        adapter: "fetch",
        fetchOptions: { cache: "no-store" },
      });
      const payload = response.data as GrocyProductsResponsePayload;
      return deserializeGrocyProducts(payload);
    },
  });

  productCache.set(instanceIndex, pending);

  try {
    return await pending;
  } catch (error) {
    productCache.delete(instanceIndex);
    throw error;
  }
}

export async function submitInventoryCorrection(
  instanceIndex: string,
  productId: number,
  payload: InventoryCorrectionRequestPayload,
): Promise<GrocyProductInventoryEntry> {
  try {
    const response = await axios.post(
      `/api/grocy/${instanceIndex}/products/${productId}/inventory`,
      payload,
      {
        adapter: "fetch",
        fetchOptions: { cache: "no-store" },
      },
    );
    const entry = deserializeGrocyProductInventoryEntry(
      response.data as GrocyProductInventoryEntryPayload,
    );
    invalidateGrocyProductsClientCache(instanceIndex);
    upsertCachedProduct(instanceIndex, entry);
    return entry;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const detail =
        (
          error.response?.data as
            | { error?: string; detail?: string }
            | undefined
        )?.error ??
        (
          error.response?.data as
            | { error?: string; detail?: string }
            | undefined
        )?.detail ??
        error.response?.statusText ??
        error.message;
      throw new Error(detail);
    }
    throw error;
  }
}

export async function submitInventoryAdjustment(
  instanceIndex: string,
  productId: number,
  payload: InventoryAdjustmentRequestPayload,
): Promise<GrocyProductInventoryEntry> {
  try {
    const response = await axios.post(
      `/api/grocy/${instanceIndex}/products/${productId}/inventory/adjust`,
      payload,
      {
        adapter: "fetch",
        fetchOptions: { cache: "no-store" },
      },
    );
    const entry = deserializeGrocyProductInventoryEntry(
      response.data as GrocyProductInventoryEntryPayload,
    );
    invalidateGrocyProductsClientCache(instanceIndex);
    upsertCachedProduct(instanceIndex, entry);
    return entry;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const detail =
        (
          error.response?.data as
            | { error?: string; detail?: string }
            | undefined
        )?.error ??
        (
          error.response?.data as
            | { error?: string; detail?: string }
            | undefined
        )?.detail ??
        error.response?.statusText ??
        error.message;
      throw new Error(detail);
    }
    throw error;
  }
}

export async function submitPurchaseEntry(
  instanceIndex: string,
  productId: number,
  payload: PurchaseEntryRequestPayload,
): Promise<PurchaseSubmissionResult> {
  try {
    const response = await axios.post(
      `/api/grocy/${instanceIndex}/products/${productId}/purchase`,
      payload,
      {
        adapter: "fetch",
        fetchOptions: { cache: "no-store" },
      },
    );
    const payloadEntries = response.data;
    if (!Array.isArray(payloadEntries)) {
      throw new Error(
        "Unexpected purchase response. Expected stock entry list.",
      );
    }
    const newEntries = (payloadEntries as GrocyStockEntryPayload[]).map(
      deserializeGrocyStockEntry,
    );
    invalidateGrocyProductsClientCache(instanceIndex);
    const updatedProduct = await fetchGrocyProduct(instanceIndex, productId);
    return { product: updatedProduct, newEntries };
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const detail =
        (
          error.response?.data as
            | { error?: string; detail?: string }
            | undefined
        )?.error ??
        (
          error.response?.data as
            | { error?: string; detail?: string }
            | undefined
        )?.detail ??
        error.response?.statusText ??
        error.message;
      throw new Error(detail);
    }
    throw error;
  }
}

export async function fetchPurchaseEntryDefaults(
  instanceIndex: string,
  productId: number,
  shoppingLocationId: number | null,
): Promise<PurchaseEntryDefaults> {
  const params = new URLSearchParams();
  if (typeof shoppingLocationId === "number") {
    params.set("shoppingLocationId", String(shoppingLocationId));
  }
  const query = params.toString();
  const path = `/api/grocy/${instanceIndex}/products/${productId}/purchase/defaults${
    query ? `?${query}` : ""
  }`;
  const response = await axios.get(path, {
    adapter: "fetch",
    fetchOptions: { cache: "no-store" },
  });
  return response.data as PurchaseEntryDefaults;
}

export async function fetchBulkPurchaseEntryDefaults(
  instanceIndex: string,
  productIds: number[],
  shoppingLocationId: number | null,
): Promise<PurchaseEntryDefaults[]> {
  const response = await axios.post(
    `/api/grocy/${instanceIndex}/purchases/defaults`,
    {
      productIds,
      shoppingLocationId,
    },
    {
      adapter: "fetch",
      fetchOptions: { cache: "no-store" },
    },
  );
  return (response.data as { defaults: PurchaseEntryDefaults[] }).defaults;
}

export async function fetchPurchaseEntryCalculation(
  instanceIndex: string,
  productId: number,
  metadata: PurchaseEntryRequestPayload["metadata"],
): Promise<PurchaseEntryCalculation> {
  const response = await axios.post(
    `/api/grocy/${instanceIndex}/products/${productId}/purchase/derive`,
    { metadata },
    {
      adapter: "fetch",
      fetchOptions: { cache: "no-store" },
    },
  );
  return response.data as PurchaseEntryCalculation;
}

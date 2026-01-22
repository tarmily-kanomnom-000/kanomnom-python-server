import axios from "axios";

import { runGrocyMutation } from "@/lib/grocy/mutation-runner";
import {
  deserializeGrocyInstanceSummaries,
  deserializeGrocyProductInventoryEntry,
  deserializeGrocyProducts,
  deserializeGrocyStockEntry,
  type GrocyProductInventoryEntryPayload,
  type GrocyProductsResponsePayload,
  type GrocyStockEntryPayload,
  type ListInstancesResponsePayload,
} from "@/lib/grocy/transformers";
import type {
  GrocyInstanceSummary,
  GrocyProductInventoryEntry,
  GrocyQuantityUnit,
  GrocyQuantityUnitConversion,
  GrocyStockEntry,
  InventoryAdjustmentRequestPayload,
  InventoryCorrectionRequestPayload,
  ProductDescriptionMetadataBatchRequestPayload,
  ProductUnitConversionDefinition,
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

const productCache = new Map<string, Promise<GrocyProductInventoryEntry[]>>();
const quantityUnitConversionsCache: {
  promise: Promise<ProductUnitConversionDefinition[]> | null;
} = { promise: null };

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

export async function fetchGrocyInstances({
  forceRefresh = false,
}: FetchOptions = {}): Promise<GrocyInstanceSummary[]> {
  const path = `/api/grocy/instances${forceRefresh ? "?forceRefresh=1" : ""}`;
  const response = await axios.get(path, {
    adapter: "fetch",
    fetchOptions: { cache: "no-store" },
  });
  const payload = response.data as ListInstancesResponsePayload;
  return deserializeGrocyInstanceSummaries(payload);
}

export async function fetchGrocyProduct(
  instanceIndex: string,
  productId: number,
): Promise<GrocyProductInventoryEntry> {
  const cachedProducts = readCachedProducts(instanceIndex);
  const cachedProduct =
    cachedProducts?.find((entry) => entry.id === productId) ?? null;
  return runGrocyMutation<GrocyProductInventoryEntry>({
    request: async () => {
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
    },
    offlineFallback: cachedProduct ? () => cachedProduct : null,
  });
}

type GrocyQuantityUnitsResponsePayload = {
  instance_index: string;
  quantity_units: GrocyQuantityUnit[];
};

type GrocyQuantityUnitConversionsResponsePayload = {
  conversions: GrocyQuantityUnitConversion[];
};

export async function fetchGrocyQuantityUnits(
  instanceIndex: string,
): Promise<GrocyQuantityUnit[]> {
  const response = await axios.get(
    `/api/grocy/${instanceIndex}/quantity-units`,
    {
      adapter: "fetch",
      fetchOptions: { cache: "no-store" },
    },
  );
  const payload = response.data as GrocyQuantityUnitsResponsePayload;
  return payload.quantity_units ?? [];
}

export async function fetchGrocyQuantityUnitConversions(): Promise<
  ProductUnitConversionDefinition[]
> {
  if (quantityUnitConversionsCache.promise) {
    return quantityUnitConversionsCache.promise;
  }
  const request = axios
    .get("/api/grocy/quantity-unit-conversions", {
      adapter: "fetch",
      fetchOptions: { cache: "no-store" },
    })
    .then((response) => {
      const payload =
        response.data as GrocyQuantityUnitConversionsResponsePayload;
      return (payload.conversions ?? []).map((conversion) => ({
        from_unit: conversion.from_unit_name,
        to_unit: conversion.to_unit_name,
        factor: conversion.factor,
        source: "universal" as const,
      }));
    })
    .finally(() => {
      quantityUnitConversionsCache.promise = null;
    });
  quantityUnitConversionsCache.promise = request;
  return request;
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
  return runGrocyMutation<GrocyProductInventoryEntry>({
    request: async () => {
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
    },
  });
}

export async function submitInventoryAdjustment(
  instanceIndex: string,
  productId: number,
  payload: InventoryAdjustmentRequestPayload,
): Promise<GrocyProductInventoryEntry> {
  return runGrocyMutation<GrocyProductInventoryEntry>({
    request: async () => {
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
    },
  });
}

export async function submitPurchaseEntry(
  instanceIndex: string,
  productId: number,
  payload: PurchaseEntryRequestPayload,
): Promise<PurchaseSubmissionResult> {
  return runGrocyMutation<PurchaseSubmissionResult>({
    request: async () => {
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
    },
  });
}

export async function submitProductDescriptionMetadata(
  instanceIndex: string,
  payload: ProductDescriptionMetadataBatchRequestPayload,
): Promise<GrocyProductInventoryEntry[]> {
  return runGrocyMutation<GrocyProductInventoryEntry[]>({
    request: async () => {
      const response = await axios.post(
        `/api/grocy/${instanceIndex}/products/description-metadata`,
        payload,
        {
          adapter: "fetch",
          fetchOptions: { cache: "no-store" },
        },
      );
      const responsePayload = response.data as GrocyProductsResponsePayload;
      const products = deserializeGrocyProducts(responsePayload);
      invalidateGrocyProductsClientCache(instanceIndex);
      products.forEach((product) => {
        upsertCachedProduct(instanceIndex, product);
      });
      return products;
    },
  });
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

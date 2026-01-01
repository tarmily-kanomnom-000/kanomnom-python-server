import "server-only";

import { cache } from "react";
import {
  deserializeGrocyInstanceSummaries,
  deserializeGrocyProducts,
  type GrocyProductsResponsePayload,
  type ListInstancesResponsePayload,
} from "@/lib/grocy/transformers";
import type {
  GrocyInstanceSummary,
  GrocyProductInventoryEntry,
} from "@/lib/grocy/types";
import { safeReadResponseText } from "@/lib/http";
import { environmentVariables } from "@/utils/environmentVariables";

function resolveApiBaseUrl(): string {
  const apiBaseUrl = environmentVariables.apiBaseUrl?.trim();
  if (!apiBaseUrl) {
    throw new Error(
      "KANOMNOM_API_BASE_URL is not configured. Set it in your dashboard env file.",
    );
  }
  return apiBaseUrl;
}

const loadGrocyInstances = cache(async (): Promise<GrocyInstanceSummary[]> => {
  const apiBaseUrl = resolveApiBaseUrl();
  const url = new URL("/grocy/instances", apiBaseUrl);
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    next: { revalidate: 120 },
  });

  if (!response.ok) {
    const errorDetail = await safeReadResponseText(response);
    throw new Error(
      `Failed to load Grocy instances (${response.status}): ${errorDetail}`,
    );
  }

  const payload = (await response.json()) as ListInstancesResponsePayload;
  return deserializeGrocyInstanceSummaries(payload);
});

export async function fetchGrocyInstances(): Promise<GrocyInstanceSummary[]> {
  return loadGrocyInstances();
}

type FetchGrocyProductsOptions = {
  forceRefresh?: boolean;
};

type GrocyVersionMap = Map<string, number>;
const globalGrocyVersionMap = globalThis as typeof globalThis & {
  __grocyProductCacheVersions?: GrocyVersionMap;
};
const productCacheVersions: GrocyVersionMap =
  globalGrocyVersionMap.__grocyProductCacheVersions ?? new Map();
if (!globalGrocyVersionMap.__grocyProductCacheVersions) {
  globalGrocyVersionMap.__grocyProductCacheVersions = productCacheVersions;
}

function getProductsCacheVersion(instanceIndex: string): number {
  return productCacheVersions.get(instanceIndex) ?? 0;
}

export function invalidateGrocyProductsCache(instanceIndex: string): void {
  const nextVersion = getProductsCacheVersion(instanceIndex) + 1;
  productCacheVersions.set(instanceIndex, nextVersion);
}

const loadGrocyProducts = cache(
  async (
    instanceIndex: string,
    version: number,
  ): Promise<GrocyProductInventoryEntry[]> => {
    return requestGrocyProducts(instanceIndex, { cacheVersion: version });
  },
);

type RequestOptions = FetchGrocyProductsOptions & { cacheVersion?: number };

async function requestGrocyProducts(
  instanceIndex: string,
  options?: RequestOptions,
): Promise<GrocyProductInventoryEntry[]> {
  const apiBaseUrl = resolveApiBaseUrl();
  const url = new URL(`/grocy/${instanceIndex}/products`, apiBaseUrl);
  if (options?.forceRefresh) {
    url.searchParams.set("force_refresh", "true");
  }
  // Only append cache_buster when explicitly refreshing or a version bump occurred.
  if (
    typeof options?.cacheVersion === "number" &&
    (options.forceRefresh || options.cacheVersion > 0)
  ) {
    url.searchParams.set("cache_buster", String(options.cacheVersion));
  }
  const requestInit: RequestInit & { next?: { revalidate?: number } } = {
    headers: { Accept: "application/json" },
  };
  if (options?.forceRefresh) {
    requestInit.cache = "no-store";
  } else {
    requestInit.next = { revalidate: 60 };
  }
  const response = await fetch(url, requestInit);

  if (!response.ok) {
    const errorDetail = await safeReadResponseText(response);
    throw new Error(
      `Failed to load Grocy products (${response.status}): ${errorDetail}`,
    );
  }

  const payload = (await response.json()) as GrocyProductsResponsePayload;
  return deserializeGrocyProducts(payload);
}

export async function fetchGrocyProductsForInstance(
  instanceIndex: string,
  options?: FetchGrocyProductsOptions,
): Promise<GrocyProductInventoryEntry[]> {
  if (options?.forceRefresh) {
    return requestGrocyProducts(instanceIndex, options);
  }
  const version = getProductsCacheVersion(instanceIndex);
  return loadGrocyProducts(instanceIndex, version);
}

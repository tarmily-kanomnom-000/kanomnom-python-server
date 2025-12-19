import axios from "axios";

import type { GrocyProductInventoryEntry } from "@/lib/grocy/types";

type ProductsQueryOptions = {
  instanceIndex: string;
  useForceCache?: boolean;
};

export function getGrocyProductsQuery({
  instanceIndex,
  useForceCache = false,
}: ProductsQueryOptions) {
  return {
    queryKey: ["grocy", "products", instanceIndex, useForceCache],
    queryFn: () => fetchGrocyProducts(instanceIndex, useForceCache),
    staleTime: 1000 * 60 * 2,
    enabled: instanceIndex.length > 0,
  };
}

async function fetchGrocyProducts(
  instanceIndex: string,
  useForceCache: boolean,
): Promise<GrocyProductInventoryEntry[]> {
  const response = await axios.get(`/api/grocy/${instanceIndex}/products`, {
    adapter: "fetch",
    fetchOptions: useForceCache
      ? { cache: "force-cache" }
      : { cache: "no-store" },
  });

  const payload = response.data as {
    products: GrocyProductInventoryEntry[];
  };

  return payload.products;
}

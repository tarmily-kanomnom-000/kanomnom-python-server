import axios from "axios";

import type { GrocyInstanceSummary } from "@/lib/grocy/types";
import {
  fetchWithOfflineCache,
  grocyInstancesCacheKey,
} from "@/lib/offline/grocy-cache";

type InstancesQueryOptions = {
  useForceCache?: boolean;
};

export function getGrocyInstancesQuery(options: InstancesQueryOptions = {}) {
  return {
    queryKey: ["grocy", "instances", options.useForceCache],
    queryFn: () => fetchGrocyInstances(options),
    staleTime: 1000 * 60 * 5,
  };
}

async function fetchGrocyInstances({
  useForceCache = false,
}: InstancesQueryOptions): Promise<GrocyInstanceSummary[]> {
  const payload = await fetchWithOfflineCache<{
    instances: GrocyInstanceSummary[];
  }>({
    cacheKey: grocyInstancesCacheKey(),
    fetcher: async () => {
      const response = await axios.get("/api/grocy/instances", {
        adapter: "fetch",
        fetchOptions: useForceCache
          ? { cache: "force-cache" }
          : { cache: "default" },
      });
      return response.data as {
        instances: GrocyInstanceSummary[];
      };
    },
  });

  return payload.instances;
}

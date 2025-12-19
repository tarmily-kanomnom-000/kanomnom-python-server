import axios from "axios";

import type { GrocyInstanceSummary } from "@/lib/grocy/types";

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
  const response = await axios.get("/api/grocy/instances", {
    adapter: "fetch",
    fetchOptions: useForceCache
      ? { cache: "force-cache" }
      : { cache: "default" },
  });

  const payload = response.data as {
    instances: GrocyInstanceSummary[];
  };

  return payload.instances;
}

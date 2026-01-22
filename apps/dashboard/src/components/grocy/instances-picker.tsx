"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useTransition,
} from "react";

import { InstanceSelector } from "@/components/grocy/instances/instance-selector";
import { ProductsPanel } from "@/components/grocy/instances/products-panel";
import { useBrowserSearchParams } from "@/hooks/use-browser-search-params";
import { useQueryParamUpdater } from "@/hooks/use-query-param-updater";
import type { DashboardRole } from "@/lib/auth/types";
import {
  fetchGrocyInstances,
  fetchGrocyProduct,
  fetchGrocyProducts,
} from "@/lib/grocy/client";
import {
  GROCY_QUERY_PARAMS,
  INVENTORY_QUERY_PARAM_KEYS,
} from "@/lib/grocy/query-params";
import type {
  GrocyInstanceSummary,
  GrocyProductInventoryEntry,
} from "@/lib/grocy/types";

type InstancesPickerProps = {
  instances: GrocyInstanceSummary[];
  userRole: DashboardRole;
};

export function InstancesPicker({ instances, userRole }: InstancesPickerProps) {
  const [instanceSummaries, setInstanceSummaries] =
    useState<GrocyInstanceSummary[]>(instances);
  const searchParams = useBrowserSearchParams();
  const updateQueryParams = useQueryParamUpdater();
  const [selectedInstanceId, setSelectedInstanceId] = useState<string | null>(
    () =>
      resolveInstanceSelection(
        searchParams.get(GROCY_QUERY_PARAMS.instance),
        instanceSummaries,
      ),
  );
  const [products, setProducts] = useState<GrocyProductInventoryEntry[]>([]);
  const [productError, setProductError] = useState<string | null>(null);
  const [instanceError, setInstanceError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const latestRequestIdRef = useRef(0);
  const latestInstanceRequestIdRef = useRef(0);

  const selectedInstance = useMemo(
    () =>
      instanceSummaries.find(
        (instance) => instance.instance_index === selectedInstanceId,
      ) ?? null,
    [instanceSummaries, selectedInstanceId],
  );

  const locationNamesById = useMemo(() => {
    const map: Record<number, string> = {};
    selectedInstance?.locations.forEach((location) => {
      map[location.id] = location.name;
    });
    return map;
  }, [selectedInstance]);

  const shoppingLocationNamesById = useMemo(() => {
    const map: Record<number, string> = {};
    selectedInstance?.shopping_locations?.forEach((location) => {
      map[location.id] = location.name;
    });
    return map;
  }, [selectedInstance]);

  useEffect(() => {
    const queryInstanceId = searchParams.get(GROCY_QUERY_PARAMS.instance);
    const browserInstanceId =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get(
            GROCY_QUERY_PARAMS.instance,
          )
        : null;
    const resolvedSelection = resolveInstanceSelection(
      browserInstanceId ?? queryInstanceId,
      instanceSummaries,
    );
    setSelectedInstanceId((current) =>
      current === resolvedSelection ? current : resolvedSelection,
    );
    if (!browserInstanceId && resolvedSelection) {
      updateQueryParams({ [GROCY_QUERY_PARAMS.instance]: resolvedSelection });
    }
  }, [instanceSummaries, searchParams, updateQueryParams]);

  const loadProducts = useCallback(
    (options?: { forceRefresh?: boolean }) => {
      if (!selectedInstance) {
        setProducts([]);
        setProductError(null);
        return;
      }

      const requestId = latestRequestIdRef.current + 1;
      latestRequestIdRef.current = requestId;
      const instanceIndex = selectedInstance.instance_index;

      setProductError(null);
      startTransition(() => {
        fetchGrocyProducts(instanceIndex, {
          forceRefresh: options?.forceRefresh ?? false,
        })
          .then((items) => {
            if (latestRequestIdRef.current !== requestId) {
              return;
            }
            setProducts(items);
          })
          .catch((error: unknown) => {
            if (latestRequestIdRef.current !== requestId) {
              return;
            }
            setProductError(
              error instanceof Error
                ? error.message
                : "Failed to load products for the selected instance.",
            );
            setProducts([]);
          });
      });
    },
    [selectedInstance],
  );

  const loadInstances = useCallback((options?: { forceRefresh?: boolean }) => {
    const requestId = latestInstanceRequestIdRef.current + 1;
    latestInstanceRequestIdRef.current = requestId;

    setInstanceError(null);
    startTransition(() => {
      fetchGrocyInstances({ forceRefresh: options?.forceRefresh ?? false })
        .then((items) => {
          if (latestInstanceRequestIdRef.current !== requestId) {
            return;
          }
          setInstanceSummaries(items);
        })
        .catch((error: unknown) => {
          if (latestInstanceRequestIdRef.current !== requestId) {
            return;
          }
          setInstanceError(
            error instanceof Error
              ? error.message
              : "Failed to refresh Grocy instance data.",
          );
        });
    });
  }, []);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  useEffect(() => {
    setInstanceSummaries(instances);
  }, [instances]);

  const handleProductUpdate = useCallback(
    async (updatedProduct: GrocyProductInventoryEntry) => {
      if (!selectedInstance) {
        return;
      }
      try {
        const latestProduct = await fetchGrocyProduct(
          selectedInstance.instance_index,
          updatedProduct.id,
        );
        setProducts((current) =>
          current.map((product) =>
            product.id === latestProduct.id ? latestProduct : product,
          ),
        );
      } catch (error) {
        // Fall back to optimistic update if the single fetch fails.
        setProducts((current) =>
          current.map((product) =>
            product.id === updatedProduct.id ? updatedProduct : product,
          ),
        );
      }
    },
    [selectedInstance],
  );

  const handleInstanceChange = (nextInstanceId: string | null) => {
    setSelectedInstanceId(nextInstanceId);
    const updates: Record<string, string | null> = {
      [GROCY_QUERY_PARAMS.instance]: nextInstanceId,
    };
    if (nextInstanceId !== selectedInstanceId) {
      INVENTORY_QUERY_PARAM_KEYS.forEach((key) => {
        updates[key] = null;
      });
    }
    updateQueryParams(updates);
  };

  const handleRefreshProducts = useCallback(() => {
    loadProducts({ forceRefresh: true });
    loadInstances({ forceRefresh: true });
  }, [loadInstances, loadProducts]);

  return (
    <section className="space-y-6">
      <InstanceSelector
        instances={instanceSummaries}
        selectedInstanceId={selectedInstanceId}
        onInstanceChange={handleInstanceChange}
      />
      <ProductsPanel
        isLoading={isPending}
        errorMessage={productError}
        instanceErrorMessage={instanceError}
        products={products}
        activeInstanceId={selectedInstance?.instance_index ?? null}
        locationNamesById={locationNamesById}
        shoppingLocationNamesById={shoppingLocationNamesById}
        userRole={userRole}
        onProductUpdate={handleProductUpdate}
        onRefresh={handleRefreshProducts}
      />
    </section>
  );
}

function resolveInstanceSelection(
  queryValue: string | null,
  instances: GrocyInstanceSummary[],
): string | null {
  if (queryValue) {
    const matched = instances.find(
      (instance) => instance.instance_index === queryValue,
    );
    return matched ? matched.instance_index : queryValue;
  }
  return instances[0]?.instance_index ?? null;
}

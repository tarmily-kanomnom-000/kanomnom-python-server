"use client";

import { useSearchParams } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  useTransition,
} from "react";

import { InstanceSelector } from "@/components/grocy/instances/instance-selector";
import { ProductsPanel } from "@/components/grocy/instances/products-panel";
import { useQueryParamUpdater } from "@/hooks/use-query-param-updater";
import { fetchGrocyProduct, fetchGrocyProducts } from "@/lib/grocy/client";
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
};

export function InstancesPicker({ instances }: InstancesPickerProps) {
  const searchParams = useSearchParams();
  const updateQueryParams = useQueryParamUpdater();
  const [selectedInstanceId, setSelectedInstanceId] = useState<string | null>(
    () =>
      resolveInstanceSelection(
        searchParams.get(GROCY_QUERY_PARAMS.instance),
        instances,
      ),
  );
  const [products, setProducts] = useState<GrocyProductInventoryEntry[]>([]);
  const [productError, setProductError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const selectedInstance = useMemo(
    () =>
      instances.find(
        (instance) => instance.instance_index === selectedInstanceId,
      ) ?? null,
    [instances, selectedInstanceId],
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
    const resolvedSelection = resolveInstanceSelection(
      queryInstanceId,
      instances,
    );
    setSelectedInstanceId((current) =>
      current === resolvedSelection ? current : resolvedSelection,
    );
    if (resolvedSelection !== queryInstanceId) {
      updateQueryParams({ [GROCY_QUERY_PARAMS.instance]: resolvedSelection });
    }
  }, [instances, searchParams, updateQueryParams]);

  const loadProducts = useCallback(
    (options?: { forceRefresh?: boolean }) => {
      if (!selectedInstance) {
        setProducts([]);
        setProductError(null);
        return;
      }

      setProductError(null);
      startTransition(() => {
        fetchGrocyProducts(selectedInstance.instance_index, {
          forceRefresh: options?.forceRefresh ?? false,
        })
          .then((items) => setProducts(items))
          .catch((error: unknown) => {
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

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

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
  }, [loadProducts]);

  return (
    <section className="space-y-6">
      <InstanceSelector
        instances={instances}
        selectedInstanceId={selectedInstanceId}
        onInstanceChange={handleInstanceChange}
      />
      <ProductsPanel
        isLoading={isPending}
        errorMessage={productError}
        products={products}
        activeInstanceId={selectedInstance?.instance_index ?? null}
        locationNamesById={locationNamesById}
        shoppingLocationNamesById={shoppingLocationNamesById}
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
    if (matched) {
      return matched.instance_index;
    }
  }
  return instances[0]?.instance_index ?? null;
}

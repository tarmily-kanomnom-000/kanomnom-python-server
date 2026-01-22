import type { ProductUnitConversionDefinition } from "@/lib/grocy/types";

export type UnitConversionRequest = {
  from_unit: string;
  to_unit: string;
};

export function resolveUnitConversionFactor(
  conversions: ProductUnitConversionDefinition[],
  fromUnit: string,
  toUnit: string,
): number | null {
  const [result] = resolveUnitConversionFactors(conversions, [
    { from_unit: fromUnit, to_unit: toUnit },
  ]);
  return result ?? null;
}

export function resolveUnitConversionFactors(
  conversions: ProductUnitConversionDefinition[],
  requests: UnitConversionRequest[],
): Array<number | null> {
  if (requests.length === 0) {
    return [];
  }
  const { productEdges, universalEdges } = splitConversionEdges(conversions);
  return requests.map((request) => {
    const fromUnit = normalizeUnitName(request.from_unit);
    const toUnit = normalizeUnitName(request.to_unit);
    if (!fromUnit || !toUnit) {
      return null;
    }
    if (fromUnit === toUnit) {
      return 1;
    }
    const direct = resolveDirectUniversal(universalEdges, fromUnit, toUnit);
    if (direct !== null) {
      return direct;
    }
    return resolveConversionFactor(
      productEdges,
      universalEdges,
      fromUnit,
      toUnit,
    );
  });
}

function splitConversionEdges(
  conversions: ProductUnitConversionDefinition[],
): {
  productEdges: Map<string, Array<[string, number]>>;
  universalEdges: Map<string, Array<[string, number]>>;
} {
  const productEdges = new Map<string, Array<[string, number]>>();
  const universalEdges = new Map<string, Array<[string, number]>>();
  for (const conversion of conversions) {
    const fromKey = normalizeUnitName(conversion.from_unit);
    const toKey = normalizeUnitName(conversion.to_unit);
    if (!fromKey || !toKey || conversion.factor <= 0) {
      continue;
    }
    if (conversion.source === "universal") {
      addConversionEdge(universalEdges, fromKey, toKey, conversion.factor);
      continue;
    }
    addConversionEdge(productEdges, fromKey, toKey, conversion.factor);
    addConversionEdge(productEdges, toKey, fromKey, 1 / conversion.factor);
  }
  return { productEdges, universalEdges };
}

function addConversionEdge(
  graph: Map<string, Array<[string, number]>>,
  fromUnit: string,
  toUnit: string,
  factor: number,
): void {
  const edges = graph.get(fromUnit);
  if (edges) {
    edges.push([toUnit, factor]);
  } else {
    graph.set(fromUnit, [[toUnit, factor]]);
  }
}

function resolveDirectUniversal(
  universalEdges: Map<string, Array<[string, number]>>,
  fromUnit: string,
  toUnit: string,
): number | null {
  const edges = universalEdges.get(fromUnit);
  if (!edges) {
    return null;
  }
  for (const [nextUnit, edgeFactor] of edges) {
    if (nextUnit === toUnit) {
      return edgeFactor;
    }
  }
  return null;
}

function resolveConversionFactor(
  productEdges: Map<string, Array<[string, number]>>,
  universalEdges: Map<string, Array<[string, number]>>,
  fromUnit: string,
  toUnit: string,
): number | null {
  const visited = new Set([fromUnit]);
  const queue: Array<[string, number]> = [[fromUnit, 1]];
  while (queue.length > 0) {
    const entry = queue.shift();
    if (!entry) {
      continue;
    }
    const [current, factor] = entry;
    const combinedEdges = [
      ...(productEdges.get(current) ?? []),
      ...(universalEdges.get(current) ?? []),
    ];
    for (const [nextUnit, edgeFactor] of combinedEdges) {
      if (visited.has(nextUnit)) {
        continue;
      }
      const nextFactor = factor * edgeFactor;
      if (nextUnit === toUnit) {
        return nextFactor;
      }
      visited.add(nextUnit);
      queue.push([nextUnit, nextFactor]);
    }
  }
  return null;
}

function normalizeUnitName(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  return value.trim().toLowerCase();
}

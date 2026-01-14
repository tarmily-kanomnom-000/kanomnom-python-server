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
  const graph = buildConversionGraph(conversions);
  return requests.map((request) =>
    resolveConversionFactor(
      graph,
      normalizeUnitName(request.from_unit),
      normalizeUnitName(request.to_unit),
    ),
  );
}

function buildConversionGraph(
  conversions: ProductUnitConversionDefinition[],
): Map<string, Array<[string, number]>> {
  const graph = new Map<string, Array<[string, number]>>();
  for (const conversion of conversions) {
    const fromKey = normalizeUnitName(conversion.from_unit);
    const toKey = normalizeUnitName(conversion.to_unit);
    if (!fromKey || !toKey || conversion.factor <= 0) {
      continue;
    }
    addConversionEdge(graph, fromKey, toKey, conversion.factor);
    addConversionEdge(graph, toKey, fromKey, 1 / conversion.factor);
  }
  return graph;
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

function resolveConversionFactor(
  graph: Map<string, Array<[string, number]>>,
  fromUnit: string,
  toUnit: string,
): number | null {
  if (!fromUnit || !toUnit) {
    return null;
  }
  if (fromUnit === toUnit) {
    return 1;
  }
  const visited = new Set([fromUnit]);
  const queue: Array<[string, number]> = [[fromUnit, 1]];
  while (queue.length > 0) {
    const entry = queue.shift();
    if (!entry) {
      continue;
    }
    const [current, factor] = entry;
    const edges = graph.get(current);
    if (!edges) {
      continue;
    }
    for (const [nextUnit, edgeFactor] of edges) {
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

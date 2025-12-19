import { NextResponse } from "next/server";

import { deserializeGrocyProductInventoryEntry } from "@/lib/grocy/transformers";
import type { GrocyProductInventoryEntry } from "@/lib/grocy/types";
import { safeReadResponseText } from "@/lib/http";
import { environmentVariables } from "@/utils/environmentVariables";

type RouteContext = {
  params: Promise<{
    instance_index: string;
    product_id: string;
  }>;
};

function resolveApiBaseUrl(): string {
  const apiBaseUrl = environmentVariables.apiBaseUrl?.trim();
  if (!apiBaseUrl) {
    throw new Error(
      "KANOMNOM_API_BASE_URL is not configured. Set it in your dashboard env file.",
    );
  }
  return apiBaseUrl;
}

export async function GET(
  _request: Request,
  context: RouteContext,
): Promise<Response> {
  const { instance_index, product_id } = await context.params;
  if (!instance_index || !product_id) {
    return NextResponse.json(
      { error: "instance_index and product_id are required" },
      { status: 400 },
    );
  }

  const apiBaseUrl = resolveApiBaseUrl();
  const url = new URL(
    `/grocy/${instance_index}/products/${product_id}`,
    apiBaseUrl,
  );
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await safeReadResponseText(response);
    return NextResponse.json(
      { error: detail || "Failed to load Grocy product." },
      { status: response.status || 502 },
    );
  }

  const payload = (await response.json()) as GrocyProductInventoryEntry;
  return NextResponse.json(deserializeGrocyProductInventoryEntry(payload));
}

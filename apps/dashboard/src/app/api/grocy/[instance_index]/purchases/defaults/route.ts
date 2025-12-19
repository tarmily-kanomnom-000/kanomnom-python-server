import { NextResponse } from "next/server";
import { parseOptionalNonNegativeNumber } from "@/app/api/grocy/utils";
import { safeReadResponseText } from "@/lib/http";
import { environmentVariables } from "@/utils/environmentVariables";

type RouteContext = {
  params: Promise<{
    instance_index: string;
    // Using snake_case to reflect canonical API path segments.
    product_id?: string;
  }>;
};

type PurchaseDefaultsRequest = {
  productIds: number[];
  shoppingLocationId: number | null;
};

type UpstreamDefaultsEntry = {
  product_id: number;
  shopping_location_id: number | null;
  metadata: {
    shipping_cost?: number | null;
    tax_rate?: number | null;
    brand?: string | null;
  } | null;
};

type UpstreamDefaultsResponse = {
  defaults: UpstreamDefaultsEntry[];
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

function parseRequestPayload(value: unknown): PurchaseDefaultsRequest {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Request body must be an object.");
  }
  const record = value as Record<string, unknown>;
  const rawIds = record.productIds;
  if (!Array.isArray(rawIds) || rawIds.length === 0) {
    throw new Error("productIds must be a non-empty array.");
  }
  const productIds = Array.from(
    new Set(
      rawIds
        .map((item) => {
          const parsed = Number(item);
          return Number.isFinite(parsed) ? Math.trunc(parsed) : null;
        })
        .filter((item): item is number => item !== null),
    ),
  );
  if (productIds.length === 0) {
    throw new Error("productIds must contain at least one valid identifier.");
  }
  let shoppingLocationId: number | null = null;
  if ("shoppingLocationId" in record) {
    shoppingLocationId = parseOptionalNonNegativeNumber(
      record.shoppingLocationId,
      "shoppingLocationId",
    );
    if (shoppingLocationId !== null && !Number.isInteger(shoppingLocationId)) {
      throw new Error("shoppingLocationId must be an integer.");
    }
  }
  return { productIds, shoppingLocationId };
}

export async function POST(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  const { instance_index } = await context.params;
  if (!instance_index) {
    return NextResponse.json(
      { error: "instance_index is required" },
      { status: 400 },
    );
  }

  let payload: PurchaseDefaultsRequest;
  try {
    const rawPayload = await request.json();
    payload = parseRequestPayload(rawPayload);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Invalid request payload.";
    return NextResponse.json({ error: message }, { status: 400 });
  }

  const apiBaseUrl = resolveApiBaseUrl();
  const upstreamUrl = new URL(
    `/grocy/${instance_index}/purchases/defaults`,
    apiBaseUrl,
  );
  const upstreamResponse = await fetch(upstreamUrl, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      product_ids: payload.productIds,
      shopping_location_id: payload.shoppingLocationId,
    }),
    cache: "no-store",
  });

  if (!upstreamResponse.ok) {
    const detail = await safeReadResponseText(upstreamResponse);
    return NextResponse.json(
      {
        error:
          detail ||
          `Failed to load purchase defaults (${upstreamResponse.status}).`,
      },
      { status: upstreamResponse.status || 502 },
    );
  }

  const data =
    (await upstreamResponse.json()) as UpstreamDefaultsResponse | null;
  const defaults = data?.defaults ?? [];

  return NextResponse.json({
    defaults: defaults.map((entry) => ({
      productId: entry.product_id,
      shoppingLocationId:
        typeof entry.shopping_location_id === "number"
          ? entry.shopping_location_id
          : null,
      metadata: {
        shippingCost:
          typeof entry.metadata?.shipping_cost === "number"
            ? entry.metadata.shipping_cost
            : null,
        taxRate:
          typeof entry.metadata?.tax_rate === "number"
            ? entry.metadata.tax_rate
            : null,
        brand:
          typeof entry.metadata?.brand === "string" &&
          entry.metadata.brand.trim().length
            ? entry.metadata.brand
            : null,
        packageSize:
          typeof entry.metadata?.package_size === "number"
            ? entry.metadata.package_size
            : null,
        packagePrice:
          typeof entry.metadata?.package_price === "number"
            ? entry.metadata.package_price
            : null,
        quantity:
          typeof entry.metadata?.package_quantity === "number"
            ? entry.metadata.package_quantity
            : null,
        currency:
          typeof entry.metadata?.currency === "string" &&
          entry.metadata.currency.trim().length
            ? entry.metadata.currency
            : null,
        conversionRate:
          typeof entry.metadata?.conversion_rate === "number"
            ? entry.metadata.conversion_rate
            : null,
      },
    })),
  });
}

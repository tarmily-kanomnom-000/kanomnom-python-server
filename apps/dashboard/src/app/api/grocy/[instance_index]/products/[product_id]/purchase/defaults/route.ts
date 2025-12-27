import { NextResponse } from "next/server";
import { parseOptionalNonNegativeNumber } from "@/app/api/grocy/utils";
import { buildRoleHeaders, requireUser } from "@/lib/auth/authorization";
import { safeReadResponseText } from "@/lib/http";
import { environmentVariables } from "@/utils/environmentVariables";

type RouteContext = {
  params: Promise<{
    instance_index: string;
    product_id: string;
  }>;
};

type UpstreamPurchaseDefaultsMetadata = {
  shipping_cost?: number | null;
  tax_rate?: number | null;
  brand?: string | null;
  package_size?: number | null;
  package_price?: number | null;
  package_quantity?: number | null;
  currency?: string | null;
  conversion_rate?: number | null;
  on_sale?: boolean | null;
};

type UpstreamDefaultsResponse = {
  product_id: number;
  shopping_location_id: number | null;
  metadata: UpstreamPurchaseDefaultsMetadata | null;
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

function normalizeShoppingLocationParam(value: string | null): number | null {
  if (!value) {
    return null;
  }
  try {
    const parsed = parseOptionalNonNegativeNumber(value, "shoppingLocationId");
    if (parsed === null) {
      return null;
    }
    if (!Number.isInteger(parsed)) {
      throw new Error("shoppingLocationId must be an integer.");
    }
    return parsed;
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Invalid shoppingLocationId.";
    throw new Error(message);
  }
}

export async function GET(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  const authResult = await requireUser({ allowedRoles: ["admin"] });
  if ("response" in authResult) {
    return authResult.response;
  }
  const roleHeaders = buildRoleHeaders(authResult.role);
  const { instance_index, product_id } = await context.params;
  if (!instance_index || !product_id) {
    return NextResponse.json(
      { error: "instance_index and product_id are required" },
      { status: 400 },
    );
  }

  const url = new URL(request.url);
  const shoppingLocationParam =
    url.searchParams.get("shoppingLocationId") ??
    url.searchParams.get("shopping_location_id");

  let shoppingLocationId: number | null = null;
  try {
    shoppingLocationId = normalizeShoppingLocationParam(shoppingLocationParam);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Invalid shoppingLocationId.";
    return NextResponse.json({ error: message }, { status: 400 });
  }

  const apiBaseUrl = resolveApiBaseUrl();
  const upstreamUrl = new URL(
    `/grocy/${instance_index}/products/${product_id}/purchase/defaults`,
    apiBaseUrl,
  );
  if (shoppingLocationId !== null) {
    upstreamUrl.searchParams.set(
      "shopping_location_id",
      shoppingLocationId.toString(),
    );
  }

  const upstreamResponse = await fetch(upstreamUrl, {
    method: "GET",
    headers: {
      Accept: "application/json",
      ...roleHeaders,
    },
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
  const metadata = data?.metadata ?? null;
  return NextResponse.json({
    productId: data?.product_id ?? Number(product_id),
    shoppingLocationId:
      typeof data?.shopping_location_id === "number"
        ? data?.shopping_location_id
        : null,
    metadata: {
      shippingCost:
        typeof metadata?.shipping_cost === "number"
          ? metadata.shipping_cost
          : null,
      taxRate:
        typeof metadata?.tax_rate === "number" ? metadata.tax_rate : null,
      brand:
        typeof metadata?.brand === "string" && metadata.brand.trim().length
          ? metadata.brand
          : null,
      packageSize:
        typeof metadata?.package_size === "number"
          ? metadata.package_size
          : null,
      packagePrice:
        typeof metadata?.package_price === "number"
          ? metadata.package_price
          : null,
      quantity:
        typeof metadata?.package_quantity === "number"
          ? metadata.package_quantity
          : null,
      currency:
        typeof metadata?.currency === "string" &&
        metadata.currency.trim().length
          ? metadata.currency
          : null,
      conversionRate:
        typeof metadata?.conversion_rate === "number"
          ? metadata.conversion_rate
          : null,
      onSale: metadata?.on_sale === true,
    },
  });
}

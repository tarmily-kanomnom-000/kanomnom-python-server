import purchaseEntrySchema from "@shared-schemas/purchase-entry-request.schema.json";
import { NextResponse } from "next/server";

import { buildRoleHeaders, requireUser } from "@/lib/auth/authorization";
import { invalidateGrocyProductsCache } from "@/lib/grocy/server";
import {
  deserializeGrocyStockEntry,
  type GrocyStockEntryPayload,
} from "@/lib/grocy/transformers";
import { safeReadResponseText } from "@/lib/http";
import {
  type JsonSchema,
  validateAgainstSchema,
} from "@/lib/json-schema-validator";
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

const toNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim().length) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const toOptionalNumber = (value: unknown): number | null => {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  return toNumber(value);
};

const toOptionalString = (value: unknown): string | null => {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
};

function toBackendMetadata(
  metadata: Record<string, unknown> | undefined,
): Record<string, unknown> | null {
  if (!metadata) {
    return null;
  }
  const shaped: Record<string, unknown> = {};
  if ("shippingCost" in metadata) {
    shaped.shipping_cost = metadata.shippingCost;
  } else if ("shipping_cost" in metadata) {
    shaped.shipping_cost = metadata.shipping_cost;
  }
  if ("taxRate" in metadata) {
    shaped.tax_rate = metadata.taxRate;
  } else if ("tax_rate" in metadata) {
    shaped.tax_rate = metadata.tax_rate;
  }
  if ("brand" in metadata) {
    shaped.brand = metadata.brand;
  }
  if ("packageSize" in metadata) {
    shaped.package_size = metadata.packageSize;
  } else if ("package_size" in metadata) {
    shaped.package_size = metadata.package_size;
  }
  if ("packagePrice" in metadata) {
    shaped.package_price = metadata.packagePrice;
  } else if ("package_price" in metadata) {
    shaped.package_price = metadata.package_price;
  }
  if ("quantity" in metadata) {
    shaped.package_quantity = metadata.quantity;
  } else if ("package_quantity" in metadata) {
    shaped.package_quantity = metadata.package_quantity;
  }
  if ("currency" in metadata) {
    shaped.currency = metadata.currency;
  }
  if ("conversionRate" in metadata) {
    shaped.conversion_rate = metadata.conversionRate;
  } else if ("conversion_rate" in metadata) {
    shaped.conversion_rate = metadata.conversion_rate;
  }
  if ("onSale" in metadata) {
    shaped.on_sale = metadata.onSale;
  } else if ("on_sale" in metadata) {
    shaped.on_sale = metadata.on_sale;
  }
  return Object.keys(shaped).length > 0 ? shaped : null;
}

function shapePurchasePayload(
  payload: Record<string, unknown>,
): Record<string, unknown> {
  const amount = toNumber(payload.amount);
  const price = toNumber(
    payload.pricePerUnit ?? payload.price ?? payload.unitPrice,
  );
  const bestBefore = toOptionalString(
    (payload.bestBeforeDate ?? payload.best_before_date) as string | undefined,
  );
  const purchasedDate = toOptionalString(
    (payload.purchasedDate ?? payload.purchased_date) as string | undefined,
  );
  const locationId = toOptionalNumber(
    payload.locationId ?? payload.location_id ?? null,
  );
  const shoppingLocationId = toOptionalNumber(
    payload.shoppingLocationId ?? payload.shopping_location_id ?? null,
  );
  const shoppingLocationName = toOptionalString(
    (payload.shoppingLocationName ??
      payload.shopping_location_name ??
      null) as string | null,
  );
  const note = toOptionalString(payload.note);
  const metadata = toBackendMetadata(
    isRecord(payload.metadata) ? payload.metadata : undefined,
  );
  return {
    amount,
    price,
    best_before_date: bestBefore,
    purchased_date: purchasedDate,
    location_id: locationId,
    shopping_location_id: shoppingLocationId,
    shopping_location_name: shoppingLocationName,
    note,
    metadata,
  };
}

export async function POST(
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

  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON payload" },
      { status: 400 },
    );
  }

  if (!isRecord(payload)) {
    return NextResponse.json(
      { error: "Invalid request payload" },
      { status: 400 },
    );
  }

  const upstreamPayload = shapePurchasePayload(payload);
  const schema = purchaseEntrySchema as JsonSchema;
  const validationErrors = validateAgainstSchema(schema, upstreamPayload);
  if (validationErrors.length > 0) {
    return NextResponse.json(
      {
        error: "Invalid purchase payload.",
        details: validationErrors,
      },
      { status: 400 },
    );
  }
  const apiBaseUrl = resolveApiBaseUrl();
  const url = new URL(
    `/grocy/${instance_index}/products/${product_id}/purchase`,
    apiBaseUrl,
  );
  const upstreamResponse = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...roleHeaders,
    },
    body: JSON.stringify(upstreamPayload),
    cache: "no-store",
  });

  if (!upstreamResponse.ok) {
    const detail = await safeReadResponseText(upstreamResponse);
    return NextResponse.json(
      {
        error:
          detail || `Failed to record purchase (${upstreamResponse.status}).`,
      },
      { status: upstreamResponse.status || 502 },
    );
  }

  const upstream = (await upstreamResponse.json()) as GrocyStockEntryPayload[];
  invalidateGrocyProductsCache(instance_index);
  return NextResponse.json(upstream.map(deserializeGrocyStockEntry));
}

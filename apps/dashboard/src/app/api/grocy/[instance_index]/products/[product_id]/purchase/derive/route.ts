import { NextResponse } from "next/server";

import { safeReadResponseText } from "@/lib/http";
import { environmentVariables } from "@/utils/environmentVariables";

type RouteContext = {
  params: Promise<{
    instance_index: string;
    product_id: string;
  }>;
};

type PurchaseDerivationRequest = {
  metadata: Record<string, unknown>;
};

type UpstreamDerivationResponse = {
  amount: number;
  unit_price: number;
  total_usd: number;
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

function normalizeMetadataPayload(
  value: Record<string, unknown>,
): Record<string, unknown> {
  const shaped: Record<string, unknown> = {};
  if ("shippingCost" in value) {
    shaped.shipping_cost = value.shippingCost;
  } else if ("shipping_cost" in value) {
    shaped.shipping_cost = value.shipping_cost;
  }
  if ("taxRate" in value) {
    shaped.tax_rate = value.taxRate;
  } else if ("tax_rate" in value) {
    shaped.tax_rate = value.tax_rate;
  }
  if ("brand" in value) {
    shaped.brand = value.brand;
  }
  if ("packageSize" in value) {
    shaped.package_size = value.packageSize;
  } else if ("package_size" in value) {
    shaped.package_size = value.package_size;
  }
  if ("packagePrice" in value) {
    shaped.package_price = value.packagePrice;
  } else if ("package_price" in value) {
    shaped.package_price = value.package_price;
  }
  if ("quantity" in value) {
    shaped.package_quantity = value.quantity;
  } else if ("package_quantity" in value) {
    shaped.package_quantity = value.package_quantity;
  }
  if ("currency" in value) {
    shaped.currency = value.currency;
  }
  if ("conversionRate" in value) {
    shaped.conversion_rate = value.conversionRate;
  } else if ("conversion_rate" in value) {
    shaped.conversion_rate = value.conversion_rate;
  }
  return shaped;
}

export async function POST(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  const { instance_index, product_id } = await context.params;
  if (!instance_index || !product_id) {
    return NextResponse.json(
      { error: "instance_index and product_id are required" },
      { status: 400 },
    );
  }

  let payload: PurchaseDerivationRequest;
  try {
    const rawPayload = (await request.json()) as PurchaseDerivationRequest;
    if (
      !rawPayload ||
      typeof rawPayload !== "object" ||
      Array.isArray(rawPayload) ||
      !rawPayload.metadata ||
      typeof rawPayload.metadata !== "object" ||
      Array.isArray(rawPayload.metadata)
    ) {
      throw new Error("metadata must be provided.");
    }
    payload = {
      metadata: normalizeMetadataPayload(
        rawPayload.metadata as Record<string, unknown>,
      ),
    };
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Invalid request payload.";
    return NextResponse.json({ error: message }, { status: 400 });
  }

  const apiBaseUrl = resolveApiBaseUrl();
  const upstreamUrl = new URL(
    `/grocy/${instance_index}/products/${product_id}/purchase/derive`,
    apiBaseUrl,
  );
  const upstreamResponse = await fetch(upstreamUrl, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  if (!upstreamResponse.ok) {
    const detail = await safeReadResponseText(upstreamResponse);
    return NextResponse.json(
      {
        error:
          detail ||
          `Failed to compute purchase totals (${upstreamResponse.status}).`,
      },
      { status: upstreamResponse.status || 502 },
    );
  }

  const data =
    (await upstreamResponse.json()) as UpstreamDerivationResponse | null;
  if (!data) {
    return NextResponse.json(
      { error: "Purchase totals response was empty." },
      { status: 502 },
    );
  }
  return NextResponse.json({
    amount: data.amount,
    unitPrice: data.unit_price,
    totalUsd: data.total_usd,
  });
}

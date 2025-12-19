import { NextResponse } from "next/server";
import { parseOptionalNonNegativeNumber } from "@/app/api/grocy/utils";
import { invalidateGrocyProductsCache } from "@/lib/grocy/server";
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

  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON payload" },
      { status: 400 },
    );
  }

  if (
    typeof payload !== "object" ||
    payload === null ||
    Array.isArray(payload)
  ) {
    return NextResponse.json(
      { error: "Invalid request payload" },
      { status: 400 },
    );
  }

  const amountRaw = (payload as Record<string, unknown>).amount;
  const priceRaw =
    (payload as Record<string, unknown>).pricePerUnit ??
    (payload as Record<string, unknown>).price ??
    (payload as Record<string, unknown>).unitPrice;
  const amount = Number(amountRaw);
  if (!Number.isFinite(amount) || amount <= 0) {
    return NextResponse.json(
      { error: "amount must be a positive number" },
      { status: 400 },
    );
  }
  const price = Number(priceRaw);
  if (!Number.isFinite(price)) {
    return NextResponse.json(
      { error: "pricePerUnit must be a valid number" },
      { status: 400 },
    );
  }
  const pricePerUnit = Math.round(price * 1_000_000) / 1_000_000;

  const bestBeforeValue =
    (payload as Record<string, unknown>).bestBeforeDate ??
    (payload as Record<string, unknown>).best_before_date ??
    null;
  const purchasedValue =
    (payload as Record<string, unknown>).purchasedDate ??
    (payload as Record<string, unknown>).purchased_date ??
    null;
  const locationValue =
    (payload as Record<string, unknown>).locationId ??
    (payload as Record<string, unknown>).location_id ??
    null;
  const shoppingLocationValue =
    (payload as Record<string, unknown>).shoppingLocationId ??
    (payload as Record<string, unknown>).shopping_location_id ??
    null;
  const noteRaw = (payload as Record<string, unknown>).note;

  const best_before_date =
    typeof bestBeforeValue === "string" && bestBeforeValue.trim().length
      ? bestBeforeValue
      : null;
  const purchased_date =
    typeof purchasedValue === "string" && purchasedValue.trim().length
      ? purchasedValue
      : null;
  const location_id =
    typeof locationValue === "number"
      ? locationValue
      : typeof locationValue === "string" && locationValue.trim().length
        ? Number(locationValue)
        : null;
  const shopping_location_id =
    typeof shoppingLocationValue === "number"
      ? shoppingLocationValue
      : typeof shoppingLocationValue === "string" &&
          shoppingLocationValue.trim().length
        ? Number(shoppingLocationValue)
        : null;
  const note =
    typeof noteRaw === "string" && noteRaw.trim().length ? noteRaw : null;

  const metadataRaw = (payload as Record<string, unknown>).metadata ?? null;
  let metadata: Record<string, unknown> | null = null;
  if (metadataRaw !== null) {
    if (typeof metadataRaw !== "object" || Array.isArray(metadataRaw)) {
      return NextResponse.json(
        { error: "metadata must be an object." },
        { status: 400 },
      );
    }
    try {
      const metadataRecord = metadataRaw as Record<string, unknown>;
      const shippingCost = parseOptionalNonNegativeNumber(
        metadataRecord.shippingCost,
        "metadata.shippingCost",
      );
      const taxRate = parseOptionalNonNegativeNumber(
        metadataRecord.taxRate,
        "metadata.taxRate",
      );
      const brandValue = metadataRecord.brand;
      const shaped: Record<string, unknown> = {};
      if (shippingCost !== null) {
        shaped.shipping_cost = shippingCost;
      }
      if (taxRate !== null) {
        shaped.tax_rate = taxRate;
      }
      if (typeof brandValue === "string" && brandValue.trim().length) {
        shaped.brand = brandValue;
      }
      const packageSize = parseOptionalPositiveNumber(
        metadataRecord.packageSize,
        "metadata.packageSize",
      );
      if (packageSize !== null) {
        shaped.package_size = packageSize;
      }
      const packagePrice = parseOptionalNonNegativeNumber(
        metadataRecord.packagePrice,
        "metadata.packagePrice",
      );
      if (packagePrice !== null) {
        shaped.package_price = packagePrice;
      }
      const quantity = parseOptionalPositiveNumber(
        metadataRecord.quantity,
        "metadata.quantity",
      );
      if (quantity !== null) {
        shaped.package_quantity = quantity;
      }
      const currencyValue = metadataRecord.currency;
      if (typeof currencyValue === "string" && currencyValue.trim().length) {
        shaped.currency = currencyValue.trim();
      }
      const conversionRate = parseOptionalPositiveNumber(
        metadataRecord.conversionRate,
        "metadata.conversionRate",
      );
      if (conversionRate !== null) {
        shaped.conversion_rate = conversionRate;
      }
      metadata = Object.keys(shaped).length > 0 ? shaped : null;
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Invalid purchase metadata payload.";
      return NextResponse.json({ error: message }, { status: 400 });
    }
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
    },
    body: JSON.stringify({
      amount,
      best_before_date,
      purchased_date,
      price: pricePerUnit,
      location_id,
      shopping_location_id,
      note,
      metadata,
    }),
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

  const upstream =
    (await upstreamResponse.json()) as GrocyProductInventoryEntry;
  invalidateGrocyProductsCache(instance_index);
  return NextResponse.json(deserializeGrocyProductInventoryEntry(upstream));
}
function parseOptionalPositiveNumber(
  value: unknown,
  field: string,
): number | null {
  if (value == null || value === "") {
    return null;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    throw new Error(`${field} must be a finite number.`);
  }
  if (parsed <= 0) {
    throw new Error(`${field} must be greater than 0.`);
  }
  return parsed;
}

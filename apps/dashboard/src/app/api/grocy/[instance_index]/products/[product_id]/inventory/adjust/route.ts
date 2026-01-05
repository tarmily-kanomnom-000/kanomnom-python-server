import { NextResponse } from "next/server";

import { buildRoleHeaders, requireUser } from "@/lib/auth/authorization";
import { invalidateGrocyProductsCache } from "@/lib/grocy/server";
import {
  deserializeGrocyProductInventoryEntry,
  type GrocyProductInventoryEntryPayload,
} from "@/lib/grocy/transformers";
import { safeReadResponseText } from "@/lib/http";
import { environmentVariables } from "@/utils/environmentVariables";

const LOSS_REASON_VALUES = new Set([
  "spoilage",
  "breakage",
  "overportion",
  "theft",
  "quality_reject",
  "process_error",
  "other",
]);

type LossEntryPayload = {
  reason: string;
  note: string | null;
};

function normalizeLossEntries(value: unknown): LossEntryPayload[] {
  if (value == null) {
    return [];
  }
  if (!Array.isArray(value)) {
    throw new Error("metadata.losses must be an array of loss objects.");
  }
  const normalized: LossEntryPayload[] = [];
  const seen = new Set<string>();
  for (const entry of value) {
    if (typeof entry !== "object" || entry === null || Array.isArray(entry)) {
      throw new Error("Each loss entry must be an object with reason/note.");
    }
    const record = entry as Record<string, unknown>;
    const reasonRaw = record.reason;
    if (typeof reasonRaw !== "string" || !reasonRaw.trim().length) {
      throw new Error("loss reason must be a non-empty string.");
    }
    const normalizedReason = reasonRaw.trim().toLowerCase();
    if (!LOSS_REASON_VALUES.has(normalizedReason)) {
      throw new Error(
        `loss reason must be one of: ${[...LOSS_REASON_VALUES].join(", ")}`,
      );
    }
    if (seen.has(normalizedReason)) {
      continue;
    }
    seen.add(normalizedReason);
    const noteValue = record.note;
    const note =
      typeof noteValue === "string" && noteValue.trim().length
        ? noteValue.trim()
        : null;
    normalized.push({ reason: normalizedReason, note });
  }
  return normalized;
}

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

  const deltaAmountRaw =
    (payload as Record<string, unknown>).deltaAmount ??
    (payload as Record<string, unknown>).delta_amount;
  const deltaAmount = Number(deltaAmountRaw);
  if (!Number.isFinite(deltaAmount)) {
    return NextResponse.json(
      { error: "deltaAmount must be a valid number" },
      { status: 400 },
    );
  }

  const bestBeforeValue =
    (payload as Record<string, unknown>).bestBeforeDate ??
    (payload as Record<string, unknown>).best_before_date ??
    null;
  const locationValue =
    (payload as Record<string, unknown>).locationId ??
    (payload as Record<string, unknown>).location_id ??
    null;
  const noteRaw = (payload as Record<string, unknown>).note;

  const best_before_date =
    typeof bestBeforeValue === "string" && bestBeforeValue.trim().length
      ? bestBeforeValue
      : null;
  const parsedLocation =
    typeof locationValue === "number"
      ? locationValue
      : typeof locationValue === "string" && locationValue.trim().length
        ? Number(locationValue)
        : null;
  const location_id =
    parsedLocation !== null && Number.isFinite(parsedLocation)
      ? parsedLocation
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
      const losses = normalizeLossEntries(metadataRecord.losses);
      metadata = losses.length ? { losses } : null;
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Invalid inventory metadata payload.";
      return NextResponse.json({ error: message }, { status: 400 });
    }
  }

  const apiBaseUrl = resolveApiBaseUrl();
  const url = new URL(
    `/grocy/${instance_index}/products/${product_id}/inventory/adjust`,
    apiBaseUrl,
  );
  const upstreamResponse = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...roleHeaders,
    },
    body: JSON.stringify({
      delta_amount: deltaAmount,
      best_before_date,
      location_id,
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
          detail ||
          `Failed to submit inventory adjustment (${upstreamResponse.status}).`,
      },
      { status: upstreamResponse.status || 502 },
    );
  }

  const upstream =
    (await upstreamResponse.json()) as GrocyProductInventoryEntryPayload;
  invalidateGrocyProductsCache(instance_index);
  return NextResponse.json(deserializeGrocyProductInventoryEntry(upstream));
}

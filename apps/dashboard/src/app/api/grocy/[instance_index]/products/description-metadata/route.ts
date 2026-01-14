import { NextResponse } from "next/server";

import { buildRoleHeaders, requireUser } from "@/lib/auth/authorization";
import { invalidateGrocyProductsCache } from "@/lib/grocy/server";
import { safeReadResponseText } from "@/lib/http";
import { environmentVariables } from "@/utils/environmentVariables";

type RouteContext = {
  params: Promise<{
    instance_index: string;
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

type ConversionPayload = {
  from_unit: string;
  to_unit: string;
  factor: number;
  tare?: number;
};

type UpdatePayload = {
  product_id: number;
  description: string | null;
  description_metadata: {
    unit_conversions: ConversionPayload[];
  };
};

type BatchPayload = {
  updates: UpdatePayload[];
};

function normalizePayload(raw: unknown): BatchPayload {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("Invalid request payload.");
  }
  const updatesRaw = (raw as Record<string, unknown>).updates;
  if (!Array.isArray(updatesRaw) || updatesRaw.length === 0) {
    throw new Error("updates must be a non-empty array.");
  }
  const updates: UpdatePayload[] = updatesRaw.map((entry, index) => {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
      throw new Error(`updates[${index}] must be an object.`);
    }
    const record = entry as Record<string, unknown>;
    const productId = Number(record.product_id);
    if (!Number.isFinite(productId)) {
      throw new Error(`updates[${index}].product_id must be a number.`);
    }
    const descriptionRaw = record.description;
    const description =
      typeof descriptionRaw === "string"
        ? descriptionRaw
        : descriptionRaw == null
          ? null
          : (() => {
              throw new Error(
                `updates[${index}].description must be a string or null.`,
              );
            })();
    const metadataRaw = record.description_metadata;
    if (
      !metadataRaw ||
      typeof metadataRaw !== "object" ||
      Array.isArray(metadataRaw)
    ) {
      throw new Error(
        `updates[${index}].description_metadata must be an object.`,
      );
    }
    const conversionsRaw = (metadataRaw as Record<string, unknown>)
      .unit_conversions;
    if (!Array.isArray(conversionsRaw)) {
      throw new Error(
        `updates[${index}].description_metadata.unit_conversions must be an array.`,
      );
    }
    if (conversionsRaw.length === 0 && !description) {
      throw new Error(
        `updates[${index}].description_metadata.unit_conversions must be a non-empty array when description is empty.`,
      );
    }
    const unit_conversions = conversionsRaw.map(
      (conversion, conversionIndex) => {
        if (
          !conversion ||
          typeof conversion !== "object" ||
          Array.isArray(conversion)
        ) {
          throw new Error(
            `updates[${index}].description_metadata.unit_conversions[${conversionIndex}] must be an object.`,
          );
        }
        const conversionRecord = conversion as Record<string, unknown>;
        const from_unit =
          typeof conversionRecord.from_unit === "string"
            ? conversionRecord.from_unit.trim()
            : "";
        const to_unit =
          typeof conversionRecord.to_unit === "string"
            ? conversionRecord.to_unit.trim()
            : "";
        if (!from_unit || !to_unit) {
          throw new Error(
            `updates[${index}].description_metadata.unit_conversions[${conversionIndex}] must include from_unit and to_unit.`,
          );
        }
        const factor = Number(conversionRecord.factor);
        if (!Number.isFinite(factor) || factor <= 0) {
          throw new Error(
            `updates[${index}].description_metadata.unit_conversions[${conversionIndex}].factor must be a positive number.`,
          );
        }
        const tareRaw = conversionRecord.tare;
        const tare =
          typeof tareRaw === "number"
            ? tareRaw
            : typeof tareRaw === "string" && tareRaw.trim().length
              ? Number(tareRaw)
              : null;
        if (tare !== null && (!Number.isFinite(tare) || tare < 0)) {
          throw new Error(
            `updates[${index}].description_metadata.unit_conversions[${conversionIndex}].tare must be a non-negative number.`,
          );
        }
        return {
          from_unit,
          to_unit,
          factor,
          ...(tare === null ? {} : { tare }),
        };
      },
    );
    return {
      product_id: productId,
      description,
      description_metadata: { unit_conversions },
    };
  });

  return { updates };
}

export async function POST(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  const authResult = await requireUser({ allowedRoles: ["admin"] });
  if ("response" in authResult) {
    return authResult.response;
  }
  const { instance_index } = await context.params;
  if (!instance_index) {
    return NextResponse.json(
      { error: "instance_index is required" },
      { status: 400 },
    );
  }

  let payload: BatchPayload;
  try {
    payload = normalizePayload(await request.json());
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Invalid JSON payload.";
    return NextResponse.json({ error: message }, { status: 400 });
  }

  const apiBaseUrl = resolveApiBaseUrl();
  const url = new URL(
    `/grocy/${instance_index}/products/description-metadata`,
    apiBaseUrl,
  );
  const roleHeaders = buildRoleHeaders(authResult.role);
  const upstreamResponse = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...roleHeaders,
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  if (!upstreamResponse.ok) {
    const detail = await safeReadResponseText(upstreamResponse);
    return NextResponse.json(
      { error: detail || "Failed to update product metadata." },
      { status: upstreamResponse.status || 502 },
    );
  }

  invalidateGrocyProductsCache(instance_index);
  const responsePayload = await upstreamResponse.json();
  return NextResponse.json(responsePayload);
}

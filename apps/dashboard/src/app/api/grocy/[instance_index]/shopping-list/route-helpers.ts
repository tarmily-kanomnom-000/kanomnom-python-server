import { NextResponse } from "next/server";

import { buildRoleHeaders, requireUser } from "@/lib/auth/authorization";
import { safeReadResponseText } from "@/lib/http";
import { environmentVariables } from "@/utils/environmentVariables";

type BaseContext = {
  params: Promise<{
    instance_index: string;
    [key: string]: string;
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

export async function resolveInstanceAndRole(context: BaseContext): Promise<
  | {
      instanceIndex: string;
      roleHeaders: Record<string, string>;
    }
  | { error: NextResponse }
> {
  const authResult = await requireUser({ allowedRoles: ["admin"] });
  if ("response" in authResult) {
    return { error: authResult.response };
  }
  const { instance_index } = await context.params;
  if (!instance_index) {
    return {
      error: NextResponse.json(
        { error: "instance_index is required" },
        { status: 400 },
      ),
    };
  }
  return {
    instanceIndex: instance_index,
    roleHeaders: buildRoleHeaders(authResult.role),
  };
}

export async function proxyGrocyRequest(options: {
  instanceIndex: string;
  roleHeaders: Record<string, string>;
  path: string;
  method: string;
  payload?: unknown;
  okStatuses?: number[];
  validate?: (payload: unknown) => string | null;
  logName?: string;
}): Promise<NextResponse> {
  const { instanceIndex, roleHeaders, path, method, payload, okStatuses } =
    options;
  const apiBaseUrl = resolveApiBaseUrl();
  const url = new URL(path.replace("{instance}", instanceIndex), apiBaseUrl);

  if (options.validate) {
    const validationError = options.validate(payload);
    if (validationError) {
      return NextResponse.json({ error: validationError }, { status: 400 });
    }
  }

  const upstreamResponse = await fetch(url, {
    method,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...roleHeaders,
    },
    body: payload ? JSON.stringify(payload) : undefined,
    cache: "no-store",
  });

  const isAllowedStatus =
    upstreamResponse.ok || okStatuses?.includes(upstreamResponse.status);

  if (!isAllowedStatus) {
    const detail = await safeReadResponseText(upstreamResponse);
    console.error("grocy_proxy_error", {
      path: url.pathname,
      method,
      status: upstreamResponse.status,
      detail,
      instanceIndex,
      logName: options.logName,
    });
    return NextResponse.json(
      {
        error:
          detail ||
          `Grocy request failed (${method} ${url.pathname}) with status ${upstreamResponse.status}.`,
      },
      { status: upstreamResponse.status || 502 },
    );
  }

  if (upstreamResponse.status === 204) {
    return new NextResponse(null, { status: 204 });
  }

  const data = await upstreamResponse.json();
  if (options.logName) {
    console.info("grocy_proxy_success", {
      path: url.pathname,
      method,
      status: upstreamResponse.status,
      instanceIndex,
      logName: options.logName,
    });
  }
  return NextResponse.json(data, { status: upstreamResponse.status || 200 });
}

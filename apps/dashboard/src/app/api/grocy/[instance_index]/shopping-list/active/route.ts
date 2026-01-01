import { proxyGrocyRequest, resolveInstanceAndRole } from "../route-helpers";
import type { RouteContext } from "../types";

export async function GET(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  const resolved = await resolveInstanceAndRole(context);
  if ("error" in resolved) {
    return resolved.error;
  }
  const { instanceIndex, roleHeaders } = resolved;

  return proxyGrocyRequest({
    instanceIndex,
    roleHeaders,
    path: "/grocy/{instance}/shopping-list/active",
    method: "GET",
  });
}

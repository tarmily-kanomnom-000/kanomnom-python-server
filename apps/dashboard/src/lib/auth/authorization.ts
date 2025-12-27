import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";

import { authOptions } from "./options";
import { type DashboardRole } from "./types";

type AuthorizationSuccess = {
  session: Awaited<ReturnType<typeof getServerSession>>;
  role: DashboardRole;
};

type AuthorizationFailure = {
  response: NextResponse;
};

type AuthorizationOptions = {
  allowedRoles?: DashboardRole[];
};

export async function requireUser(
  options?: AuthorizationOptions,
): Promise<AuthorizationSuccess | AuthorizationFailure> {
  const session = await getServerSession(authOptions);
  if (!session) {
    return {
      response: NextResponse.json({ error: "Unauthorized" }, { status: 401 }),
    };
  }
  const role = session.user?.role ?? "viewer";
  if (options?.allowedRoles && !options.allowedRoles.includes(role)) {
    return {
      response: NextResponse.json({ error: "Forbidden" }, { status: 403 }),
    };
  }
  return { session, role };
}

export function buildRoleHeaders(role: DashboardRole): HeadersInit {
  return { "X-Dashboard-Role": role };
}

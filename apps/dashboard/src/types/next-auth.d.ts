import type { DefaultSession } from "next-auth";
import type { JWT as DefaultJWT } from "next-auth/jwt";

import type { DashboardRole } from "@/lib/auth/types";

declare module "next-auth" {
  interface User {
    role: DashboardRole;
  }

  interface Session {
    user: {
      role: DashboardRole;
    } & DefaultSession["user"];
  }
}

declare module "next-auth/jwt" {
  interface JWT extends DefaultJWT {
    role?: DashboardRole;
  }
}

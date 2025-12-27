import type { Session } from "next-auth";
import { getServerSession } from "next-auth";

import { authOptions } from "./options";

export async function getCurrentSession(): Promise<Session | null> {
  return getServerSession(authOptions);
}

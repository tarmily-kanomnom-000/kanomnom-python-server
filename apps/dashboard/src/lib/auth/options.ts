import { compare } from "bcryptjs";
import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import { type DashboardRole } from "./types";
import { loadDashboardUsers } from "./users";

type AuthUser = {
  id: string;
  name: string;
  role: DashboardRole;
};

const isDev = process.env.NODE_ENV !== "production";

function resolveAuthSecret(): string {
  const secret =
    process.env.AUTH_SECRET?.trim() ?? process.env.NEXTAUTH_SECRET?.trim();
  if (!secret) {
    throw new Error(
      "Missing AUTH_SECRET (or NEXTAUTH_SECRET). Set it in your dashboard env file.",
    );
  }
  return secret;
}

const authSecret = resolveAuthSecret();

export const authOptions: NextAuthOptions = {
  session: { strategy: "jwt" },
  secret: authSecret,
  pages: { signIn: "/login" },
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        username: { label: "Username", type: "text" },
        password: { label: "Password", type: "password" },
      },
      authorize: async (credentials) => {
        try {
          if (!credentials?.username || !credentials?.password) {
            if (isDev) {
              console.warn("Auth: missing username or password in credentials");
            }
            return null;
          }
          const users = loadDashboardUsers();
          const user = users.find(
            (entry) => entry.username === credentials.username,
          );
          if (!user) {
            if (isDev) {
              console.warn(
                `Auth: user not found for username "${credentials.username}"`,
              );
            }
            return null;
          }
          const passwordMatches = await compare(
            credentials.password,
            user.passwordHash,
          );
          if (!passwordMatches) {
            if (isDev) {
              console.warn(
                `Auth: password mismatch for username "${credentials.username}"`,
              );
            }
            return null;
          }
          if (isDev) {
            console.info(
              `Auth: successful login for "${credentials.username}"`,
            );
          }
          return {
            id: user.username,
            name: user.username,
            role: user.role,
          };
        } catch (error) {
          const message =
            error instanceof Error
              ? error.message
              : "Unable to complete authentication.";
          if (isDev) {
            console.error("Auth: authorize error", message);
          }
          throw new Error(message);
        }
      },
    }),
  ],
  callbacks: {
    jwt: async ({ token, user }) => {
      if (user) {
        const authUser = user as AuthUser;
        token.role = authUser.role;
        token.name = authUser.name;
      }
      return token;
    },
    session: async ({ session, token }) => {
      if (!session.user) {
        return session;
      }
      session.user.role = (token.role as DashboardRole | undefined) ?? "viewer";
      session.user.name =
        session.user.name ??
        (typeof token.name === "string" ? token.name : session.user.email) ??
        "";
      return session;
    },
  },
};

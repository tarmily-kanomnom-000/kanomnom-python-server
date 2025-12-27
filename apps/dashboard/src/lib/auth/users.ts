import { readFileSync } from "node:fs";
import path from "node:path";

import { type DashboardRole, type DashboardUser } from "./types";

type RawDashboardUser = {
  username?: unknown;
  passwordHash?: unknown;
  role?: unknown;
};

const allowedRoles: DashboardRole[] = ["admin", "viewer"];

let cachedUsers: DashboardUser[] | null = null;

function parseRole(value: unknown): DashboardRole {
  if (typeof value !== "string") {
    throw new Error("role must be a string.");
  }
  const normalized = value.trim().toLowerCase();
  if (allowedRoles.includes(normalized as DashboardRole)) {
    return normalized as DashboardRole;
  }
  throw new Error(`role must be one of: ${allowedRoles.join(", ")}`);
}

function parseUser(entry: RawDashboardUser, index: number): DashboardUser {
  if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
    throw new Error(
      `DASHBOARD_USERS_JSON entry #${index + 1} must be an object.`,
    );
  }
  const username =
    typeof entry.username === "string" && entry.username.trim().length > 0
      ? entry.username.trim()
      : null;
  if (!username) {
    throw new Error(
      `DASHBOARD_USERS_JSON entry #${index + 1} is missing a username.`,
    );
  }
  const passwordHash =
    typeof entry.passwordHash === "string" && entry.passwordHash.trim().length
      ? entry.passwordHash.trim()
      : null;
  if (!passwordHash) {
    throw new Error(
      `DASHBOARD_USERS_JSON entry #${index + 1} is missing passwordHash.`,
    );
  }
  const role = parseRole(entry.role);
  return { username, passwordHash, role };
}

function parseUsersJson(rawJson: string): DashboardUser[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(rawJson);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Invalid JSON payload.";
    throw new Error(`Unable to parse dashboard users JSON: ${message}`);
  }
  if (!Array.isArray(parsed) || parsed.length === 0) {
    throw new Error("User list must be a non-empty JSON array.");
  }
  return parsed.map((entry, index) =>
    parseUser(entry as RawDashboardUser, index),
  );
}

export function loadDashboardUsers(): DashboardUser[] {
  if (cachedUsers) {
    return cachedUsers;
  }

  const usersFile = process.env.DASHBOARD_USERS_FILE?.trim();
  const usersJson = process.env.DASHBOARD_USERS_JSON?.trim();

  if (!usersFile && !usersJson) {
    throw new Error(
      'Set DASHBOARD_USERS_FILE to a JSON file path or DASHBOARD_USERS_JSON to a JSON array of { "username", "passwordHash", "role" } entries.',
    );
  }

  let users: DashboardUser[];
  if (usersFile) {
    const resolvedPath = path.resolve(process.cwd(), usersFile);
    try {
      const fileContents = readFileSync(resolvedPath, "utf-8");
      users = parseUsersJson(fileContents);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to read users file.";
      throw new Error(
        `Failed to load dashboard users from ${resolvedPath}: ${message}`,
      );
    }
  } else {
    users = parseUsersJson(usersJson as string);
  }

  cachedUsers = users;
  return users;
}

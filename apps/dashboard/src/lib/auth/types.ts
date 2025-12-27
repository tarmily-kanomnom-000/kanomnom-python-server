export type DashboardRole = "admin" | "viewer";

export type DashboardUser = {
  username: string;
  passwordHash: string;
  role: DashboardRole;
};

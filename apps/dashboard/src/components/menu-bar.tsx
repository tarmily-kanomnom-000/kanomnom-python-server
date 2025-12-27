"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut, useSession } from "next-auth/react";

type MenuItem = {
  href: string;
  label: string;
};

const menuItems: MenuItem[] = [
  { href: "/", label: "Overview" },
  { href: "/inventory", label: "Inventory" },
];

export function MenuBar() {
  const pathname = usePathname();
  const { data: session, status } = useSession();
  const isAuthenticated = status === "authenticated";
  const userRole = session?.user?.role;

  return (
    <header className="border-b border-neutral-200 bg-white">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4">
        <Link
          href="/"
          className="text-base font-semibold text-neutral-900"
          aria-label="Ka-Nom Nom dashboard home"
        >
          Ka-Nom Nom
        </Link>

        <div className="flex items-center gap-6">
          <nav aria-label="Primary" className="flex items-center gap-6 text-sm">
            {menuItems.map((item) => {
              const isActive =
                pathname === item.href || pathname?.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={isActive ? "page" : undefined}
                  className={`transition-colors ${
                    isActive
                      ? "text-neutral-900"
                      : "text-neutral-500 hover:text-neutral-900"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="flex items-center gap-3 text-sm">
            {status === "loading" ? (
              <span className="text-xs text-neutral-500">Loading…</span>
            ) : isAuthenticated ? (
              <>
                <span className="rounded-full border border-neutral-200 bg-neutral-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-neutral-600">
                  {userRole ?? "user"}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    void signOut({ callbackUrl: "/login" });
                  }}
                  className="rounded-full border border-neutral-300 px-4 py-1.5 font-medium text-neutral-700 transition hover:border-neutral-900 hover:text-neutral-900"
                >
                  Sign out
                </button>
              </>
            ) : (
              <Link
                href="/login"
                className="rounded-full bg-neutral-900 px-4 py-1.5 font-semibold text-white transition hover:bg-neutral-800"
              >
                Sign in
              </Link>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

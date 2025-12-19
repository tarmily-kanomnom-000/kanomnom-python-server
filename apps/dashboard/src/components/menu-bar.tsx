"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

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
      </div>
    </header>
  );
}

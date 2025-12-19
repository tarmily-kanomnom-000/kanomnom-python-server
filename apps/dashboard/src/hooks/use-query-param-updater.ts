"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

type QueryValue = string | null | undefined;

export function useQueryParamUpdater() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  return useCallback(
    (updates: Record<string, QueryValue>) => {
      const nextParams = new URLSearchParams(searchParams.toString());
      let changed = false;

      Object.entries(updates).forEach(([key, value]) => {
        const currentValue = searchParams.get(key);
        if (value === null || value === undefined || value === "") {
          if (currentValue !== null) {
            nextParams.delete(key);
            changed = true;
          }
          return;
        }

        if (currentValue !== value) {
          nextParams.set(key, value);
          changed = true;
        }
      });

      if (!changed) {
        return;
      }

      const queryString = nextParams.toString();
      router.replace(queryString ? `${pathname}?${queryString}` : pathname, {
        scroll: false,
      });
    },
    [pathname, router, searchParams],
  );
}

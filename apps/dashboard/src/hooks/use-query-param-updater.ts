"use client";

import { useCallback } from "react";

import { SEARCH_PARAM_CHANGE_EVENT } from "@/hooks/use-browser-search-params";

type QueryValue = string | null | undefined;

export function useQueryParamUpdater() {
  return useCallback((updates: Record<string, QueryValue>) => {
    if (typeof window === "undefined") {
      return;
    }

    const url = new URL(window.location.href);
    const nextParams = url.searchParams;
    let changed = false;

    Object.entries(updates).forEach(([key, value]) => {
      const currentValue = nextParams.get(key);
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

    const nextUrl =
      nextParams.toString().length > 0
        ? `${url.pathname}?${nextParams.toString()}`
        : url.pathname;

    window.history.replaceState(window.history.state, "", nextUrl);
    window.dispatchEvent(new Event(SEARCH_PARAM_CHANGE_EVENT));
  }, []);
}

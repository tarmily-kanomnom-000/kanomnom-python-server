"use client";

import type { ReadonlyURLSearchParams } from "next/navigation";
import { useMemo, useSyncExternalStore } from "react";

export const SEARCH_PARAM_CHANGE_EVENT = "kanomnom:searchparamschange" as const;

const getSearchSnapshot = (): string => {
  if (typeof window === "undefined") {
    return "";
  }
  return window.location.search;
};

const subscribeToSearchChanges = (onChange: () => void): (() => void) => {
  if (typeof window === "undefined") {
    return () => {};
  }
  const handler = () => onChange();
  window.addEventListener("popstate", handler);
  window.addEventListener(SEARCH_PARAM_CHANGE_EVENT, handler);
  return () => {
    window.removeEventListener("popstate", handler);
    window.removeEventListener(SEARCH_PARAM_CHANGE_EVENT, handler);
  };
};

export function useBrowserSearchParams(): ReadonlyURLSearchParams {
  const searchString = useSyncExternalStore(
    subscribeToSearchChanges,
    getSearchSnapshot,
    () => "",
  );
  return useMemo(() => new URLSearchParams(searchString), [searchString]);
}

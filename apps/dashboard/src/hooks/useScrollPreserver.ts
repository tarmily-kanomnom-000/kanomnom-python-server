import { useCallback } from "react";

/**
 * Preserve window scroll position across state updates that re-render the list.
 */
export function useScrollPreserver(): (updateFn: () => void) => void {
  return useCallback((updateFn: () => void) => {
    const currentScroll = typeof window !== "undefined" ? window.scrollY : 0;
    updateFn();
    if (typeof window !== "undefined") {
      requestAnimationFrame(() => {
        window.scrollTo({ top: currentScroll });
      });
    }
  }, []);
}

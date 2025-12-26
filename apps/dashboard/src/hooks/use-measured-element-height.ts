"use client";

import {
  type RefCallback,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

export function useMeasuredElementHeight<T extends HTMLElement>(): [
  RefCallback<T>,
  number | null,
] {
  const cleanupRef = useRef<(() => void) | null>(null);
  const [height, setHeight] = useState<number | null>(null);

  useEffect(() => {
    return () => {
      cleanupRef.current?.();
      cleanupRef.current = null;
    };
  }, []);

  const refCallback = useCallback((node: T | null) => {
    cleanupRef.current?.();
    cleanupRef.current = null;

    if (!node) {
      setHeight(null);
      return;
    }

    const updateHeight = () => {
      setHeight(node.getBoundingClientRect().height);
    };
    updateHeight();

    if (typeof ResizeObserver === "function") {
      const observer = new ResizeObserver(() => updateHeight());
      observer.observe(node);
      cleanupRef.current = () => observer.disconnect();
      return;
    }

    const handleResize = () => updateHeight();
    window.addEventListener("resize", handleResize);
    cleanupRef.current = () => {
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  return [refCallback, height];
}

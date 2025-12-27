"use client";

import { useEffect } from "react";

export function ServiceWorkerRegistration(): null {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") {
      return;
    }

    if (!("serviceWorker" in navigator)) {
      return;
    }

    const isLocalhost =
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1";
    const isSecureContext =
      window.location.protocol === "https:" || isLocalhost;

    if (!isSecureContext) {
      return;
    }

    navigator.serviceWorker.register("/sw.js").catch((error: unknown) => {
      console.error("Failed to register service worker", error);
    });
  }, []);

  return null;
}

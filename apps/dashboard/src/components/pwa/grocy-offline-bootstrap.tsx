"use client";

import { useEffect } from "react";

import { prefetchGrocyDataForOffline } from "@/lib/offline/grocy-cache";

export function GrocyOfflineBootstrap(): null {
  useEffect(() => {
    void prefetchGrocyDataForOffline();
  }, []);

  return null;
}

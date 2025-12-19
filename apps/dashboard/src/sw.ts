/// <reference lib="webworker" />

import { defaultCache } from "@serwist/next/worker";
import { type PrecacheEntry, Serwist } from "serwist";

declare const self: ServiceWorkerGlobalScope & {
  __SW_MANIFEST: Array<PrecacheEntry | string>;
};

const serwist = new Serwist({
  precacheEntries: self.__SW_MANIFEST,
  runtimeCaching: defaultCache,
  skipWaiting: true,
  clientsClaim: true,
});

serwist.addEventListeners();

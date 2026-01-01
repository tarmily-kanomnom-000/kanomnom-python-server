/// <reference lib="webworker" />

import { defaultCache } from "@serwist/next/worker";
import { type PrecacheEntry, Serwist } from "serwist";

declare const self: ServiceWorkerGlobalScope & {
  __SW_MANIFEST: Array<PrecacheEntry | string>;
};

const SW_VERSION = "v2";
const PAGE_CACHE = `page-cache-${SW_VERSION}`;
const OFFLINE_FALLBACK_CACHE = `offline-fallback-${SW_VERSION}`;
const OFFLINE_FALLBACK_URL = "/offline.html";
const PAGE_CACHE_LIMIT = 50;
const NAV_CACHE_MAX_AGE_MS = 1000 * 60 * 60 * 24; // 24h

const cachePageUrls = async (urls: string[]): Promise<void> => {
  const cache = await caches.open(PAGE_CACHE);
  await Promise.all(
    urls.map(async (url) => {
      try {
        const response = await fetch(url, { credentials: "include" });
        if (response.ok) {
          await cache.put(url, response.clone());
          await trimCache(cache, PAGE_CACHE_LIMIT);
          console.info("sw_cache_put", { url, cache: PAGE_CACHE });
          const verified = await cache.match(url);
          console.info("sw_cache_verified", { url, cached: Boolean(verified) });
        }
      } catch (error) {
        console.warn("sw_cache_preload_failed", { url, error });
      }
    }),
  );
};

const trimCache = async (cache: Cache, maxEntries: number): Promise<void> => {
  const requests = await cache.keys();
  if (requests.length <= maxEntries) {
    return;
  }
  const toDelete = requests.slice(0, requests.length - maxEntries);
  await Promise.all(toDelete.map((req) => cache.delete(req)));
};

const isFresh = (response: Response): boolean => {
  const dateHeader = response.headers.get("date");
  if (!dateHeader) {
    return true;
  }
  const ageMs = Date.now() - Date.parse(dateHeader);
  return Number.isFinite(ageMs) ? ageMs <= NAV_CACHE_MAX_AGE_MS : true;
};

const serwist = new Serwist({
  precacheEntries: self.__SW_MANIFEST,
  runtimeCaching: defaultCache,
  skipWaiting: true,
  clientsClaim: true,
});

// Intercept custom CACHE_URLS messages and handle them before Serwist to avoid
// its built-in handler expecting a different payload shape.
self.addEventListener("message", (event) => {
  const payload = event.data as
    | {
        type?: string;
        urls?: string[];
        urlsToCache?: string[];
        payload?: { urlsToCache?: string[] };
      }
    | undefined;

  if (!payload || payload.type !== "CACHE_URLS") {
    return;
  }

  // Prevent Serwist's own message handler from processing this message.
  event.stopImmediatePropagation?.();

  const urls =
    payload.urls ?? payload.urlsToCache ?? payload.payload?.urlsToCache;
  if (!Array.isArray(urls)) {
    return;
  }

  event.waitUntil(cachePageUrls(urls));
});

serwist.addEventListeners();

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(PAGE_CACHE);
      // Cache the root so the app shell is available offline even if no page cache exists yet.
      await cache.add("/");

      // Prepare an offline fallback page so navigations still render something.
      const offlineCache = await caches.open(OFFLINE_FALLBACK_CACHE);
      await offlineCache.put(
        OFFLINE_FALLBACK_URL,
        new Response(
          "<!doctype html><html><head><meta charset='utf-8'><title>Offline</title></head><body><h1>Offline</h1><p>You are offline. Reconnect to sync changes.</p></body></html>",
          {
            headers: { "Content-Type": "text/html; charset=utf-8" },
          },
        ),
      );
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter(
            (key) =>
              key.startsWith("page-cache-") ||
              key.startsWith("offline-fallback-"),
          )
          .filter((key) => key !== PAGE_CACHE && key !== OFFLINE_FALLBACK_CACHE)
          .map((key) => caches.delete(key)),
      );
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  // Only handle navigation requests; let assets use the default Serwist handlers.
  if (request.mode !== "navigate") {
    return;
  }

  const isShoppingListPage =
    request.url.includes("/inventory/") &&
    request.url.includes("/shopping-list");

  event.respondWith(
    (async () => {
      const cache = await caches.open(PAGE_CACHE);
      try {
        const networkResponse = await fetch(request);
        // Cache a clone of the page for offline use.
        void cache
          .put(request, networkResponse.clone())
          .then(() => trimCache(cache, PAGE_CACHE_LIMIT));
        console.info("sw_cache_put_nav", {
          url: request.url,
          shoppingList: isShoppingListPage,
        });
        return networkResponse;
      } catch (error) {
        const cachedResponse = await cache.match(request);
        if (cachedResponse) {
          if (!isFresh(cachedResponse)) {
            console.warn("sw_cache_serve_stale", {
              url: request.url,
              maxAgeMs: NAV_CACHE_MAX_AGE_MS,
            });
          }
          if (isShoppingListPage) {
            console.warn("sw_cache_shopping_list_served_from_cache", {
              url: request.url,
            });
          }
          return cachedResponse;
        }
        const shell = await cache.match("/");
        if (shell) {
          console.warn("sw_cache_shell_fallback", { url: request.url });
          return shell;
        }
        const offline = await caches
          .open(OFFLINE_FALLBACK_CACHE)
          .then((c) => c.match(OFFLINE_FALLBACK_URL));
        if (offline) {
          console.warn("sw_cache_offline_fallback", {
            url: request.url,
            shoppingList: isShoppingListPage,
          });
          return offline;
        }
        console.error("sw_cache_fetch_failed_no_fallback", {
          url: request.url,
          error,
        });
        return new Response("Offline", { status: 503 });
      }
    })(),
  );
});

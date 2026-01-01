# Offline PWA Testing Notes

The dev server (`npm run dev` / `npm run dev:pwa`) is not reliable for true offline on installed PWAs. Next.js dev depends on a live HMR/websocket connection and does not fully precache assets. For offline testing on devices:

1) Build/start with production output but dev env vars:
   - `npm run build:dev-env`
   - `npm run start:dev-env`
2) Install/refresh the PWA from that served site so the production build + service worker are used.
3) While online, open Inventory and the Shopping List once to cache them.
4) Go offline/airplane mode and use “View Shopping List”; it should use cached pages instead of failing.

Use `npm run dev:pwa` only for desktop dev convenience; it will still break offline once the network is fully cut.***

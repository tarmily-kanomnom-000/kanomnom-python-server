import path from "node:path";

import withSerwistInit, { type PluginOptions } from "@serwist/next";
import type { NextConfig } from "next";

const enablePwaInDev =
  process.env.SERWIST_ENABLE_DEV === "true" ||
  process.env.ENABLE_PWA_IN_DEV === "true";

const pluginOptions: PluginOptions = {
  swSrc: "src/sw.ts",
  swDest: "public/sw.js",
  disable: process.env.NODE_ENV === "development" && !enablePwaInDev,
};

const withSerwist = withSerwistInit(pluginOptions);

const nextConfig: NextConfig = {
  allowedDevOrigins: [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://kanomnom0000:6971",
    "http://kanomnom0000",
    "kanomnom0000",
    "http://dev-dashboard.kanomnom.com",
    "https://dev-dashboard.kanomnom.com",
    "http://dev-dashboard.kanomnom.com:3000",
    "https://dev-dashboard.kanomnom.com:3000",
  ],
  experimental: {
    externalDir: true,
  },
  webpack(config) {
    config.resolve = config.resolve || {};
    config.resolve.alias = {
      ...(config.resolve.alias ?? {}),
      "@shared-schemas": path.resolve(__dirname, "..", "..", "schemas"),
    };
    return config;
  },
};

export default withSerwist(nextConfig);

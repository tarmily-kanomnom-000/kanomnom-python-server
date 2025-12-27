import path from "node:path";

import withSerwistInit, { type PluginOptions } from "@serwist/next";
import type { NextConfig } from "next";

const pluginOptions: PluginOptions = {
  swSrc: "src/sw.ts",
  swDest: "public/sw.js",
  disable: process.env.NODE_ENV === "development",
};

const withSerwist = withSerwistInit(pluginOptions);

const nextConfig: NextConfig = {
  allowedDevOrigins: [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://kanomnom0000:6971",
    "http://kanomnom0000",
    "kanomnom0000",
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

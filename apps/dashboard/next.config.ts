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

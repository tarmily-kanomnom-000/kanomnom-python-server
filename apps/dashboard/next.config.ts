import withSerwistInit, { type PluginOptions } from "@serwist/next";
import type { NextConfig } from "next";

const pluginOptions: PluginOptions = {
  swSrc: "src/sw.ts",
  swDest: "public/sw.js",
  disable: process.env.NODE_ENV === "development",
};

const withSerwist = withSerwistInit(pluginOptions);

const nextConfig: NextConfig = {
};

export default withSerwist(nextConfig);

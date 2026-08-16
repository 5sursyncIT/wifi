import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The API client is shipped as TypeScript source from the workspace.
  transpilePackages: ["@dakar-wifi/api-client", "@dakar-wifi/ui"],
  // Captive mini-browsers choke on heavy payloads: keep the budget visible (§12.1).
  productionBrowserSourceMaps: false,
};

export default nextConfig;

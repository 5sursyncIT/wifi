import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@dakar-wifi/api-client", "@dakar-wifi/ui"],
};

export default nextConfig;

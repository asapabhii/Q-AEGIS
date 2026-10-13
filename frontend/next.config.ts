import type { NextConfig } from "next";

// Dev-only reverse proxy.
//
// The browser loads the app over plain HTTP on the Next dev server
// (http://127.0.0.1:3000) and calls the API at same-origin paths like
// /api/v1/health. Next forwards every /api/* request to the real backend,
// which runs over HTTPS with a self-signed dev cert. Because the hop to the
// backend happens server-side (Node), the browser never sees the self-signed
// certificate: no CA import into the OS/browser trust store, no cross-origin
// CORS, and no mixed-content prompts. The dev server is launched with
// NODE_TLS_REJECT_UNAUTHORIZED=0 so this server-side hop accepts the dev cert.
//
// Production is unaffected: rewrites are skipped when NODE_ENV=production, and
// a real deployment points NEXT_PUBLIC_API_URL at its own API origin.
const API_PROXY_TARGET =
  process.env.API_PROXY_TARGET ?? "https://127.0.0.1:8443";

const nextConfig: NextConfig = {
  // Opening the app on 127.0.0.1 while the dev server advertises localhost
  // otherwise makes Next 16 block dev-only resources (the HMR websocket and
  // /_next/*). Allow-list the loopback origin so HMR and fast refresh work.
  allowedDevOrigins: ["127.0.0.1"],
  async rewrites() {
    if (process.env.NODE_ENV === "production") return [];
    return [
      {
        source: "/api/:path*",
        destination: `${API_PROXY_TARGET}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;

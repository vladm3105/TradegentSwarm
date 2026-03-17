/** @type {import('next').NextConfig} */
const nextConfig = {
  // Proxy API requests to FastAPI backend
  async rewrites() {
    return [
      {
        source: '/api/orchestrator/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081'}/:path*`,
      },
    ];
  },

  // Allow Grafana iframe embedding
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: `frame-src 'self' ${process.env.NEXT_PUBLIC_GRAFANA_URL || 'http://localhost:3000'}`,
          },
        ],
      },
    ];
  },

  // Image optimization for external sources
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '*.tradingview.com',
      },
    ],
  },

  // Strict mode disabled: causes React double-mount in dev which triggers WS
  // connect/disconnect loop (useEffect cleanup fires before remount).
  // Re-enable when WebSocket hook is StrictMode-compatible.
  reactStrictMode: false,

  // Output standalone for Docker deployment
  output: 'standalone',
  // Ignore lint and type errors during build for faster/easier deployment
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
};

module.exports = nextConfig;

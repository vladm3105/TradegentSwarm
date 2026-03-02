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

  // Strict mode for better development
  reactStrictMode: true,

  // Output standalone for Docker deployment
  output: 'standalone',
};

module.exports = nextConfig;

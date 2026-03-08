import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  allowedDevOrigins: [
    'https://10.0.0.119:4000',
    'http://10.0.0.119:4000',
    '*.ngrok-free.dev',
    '*.ngrok.dev',
    '*.ngrok.io',
  ],
  experimental: {
    serverActions: {
      bodySizeLimit: '2mb',
    },
  },
  // Force Next.js to run on port 4000
  ...(process.env.NODE_ENV === 'development' && {
    env: {
      PORT: '4000',
    },
  }),
  async headers() {
    return [
      {
        source: '/chat/:path*',
        headers: [
          {
            key: 'Permissions-Policy',
            value: 'microphone=(self), camera=(self)',
          },
        ],
      },
      // Prevent Safari from caching pages in dev mode (HMR doesn't work through ngrok)
      ...(process.env.NODE_ENV === 'development' ? [{
        source: '/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'no-store, must-revalidate',
          },
        ],
      }] : []),
    ];
  },
};

export default nextConfig;

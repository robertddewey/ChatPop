import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
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
};

export default nextConfig;

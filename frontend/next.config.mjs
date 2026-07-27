/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        // In production, IIS reverse proxy handles this — this rewrite is for local dev only
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },
};

export default nextConfig;
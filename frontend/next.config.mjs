/** @type {import('next').NextConfig} */
const nextConfig = {
  // Pin the workspace root so Turbopack doesn't get confused by the stray
  // package-lock.json in the user's home directory
  turbopack: {
    root: import.meta.dirname,
  },
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
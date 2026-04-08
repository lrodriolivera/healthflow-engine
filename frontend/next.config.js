/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
      {
        source: '/fhir/:path*',
        destination: 'http://localhost:8000/fhir/:path*',
      },
    ];
  },
};

module.exports = nextConfig;

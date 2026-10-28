/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // The three-tab app starts at /overview.
  async redirects() {
    return [{ source: '/', destination: '/overview', permanent: false }]
  },
}

module.exports = nextConfig

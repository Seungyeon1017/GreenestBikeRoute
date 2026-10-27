/** @type {import('next').NextConfig} */
const nextConfig = {
  webpack: (config, _options) => {
    config.module.rules.push({
      test: /\.csv$/,
      loader: 'csv-loader',
      options: {
        dynamicTyping: true,
        header: true,
        skipEmptyLines: true,
      },
    })
    config.module.rules.push({
      test: /\.md$/,
      type: 'asset/source',
    })
    return config
  },
  output: 'standalone',
  // GreenestBikeRoute: the three-tab app starts at /overview. The original
  // dashboard code in app/(main) is kept but no longer the start page.
  async redirects() {
    return [{ source: '/', destination: '/overview', permanent: false }]
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**.reedu.de',
      },
      {
        protocol: 'https',
        hostname: '**.greencity.hn',
      },
      {
        protocol: 'http',
        hostname: 'localhost',
      },
      {
        protocol: 'https',
        hostname: 'nbg1.your-objectstorage.com',
      },
      {
        protocol: 'https',
        hostname: 'wiediversistmeingarten.org',
      },
    ],
  },
}

module.exports = nextConfig

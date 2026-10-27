import { Metadata, Viewport } from 'next'

export const metadata: Metadata = {
  appleWebApp: {
    capable: true,
  },
  other: {
    'mobile-web-app-capable': 'yes',
  },
}

export const viewport: Viewport = {
  themeColor: '#ffffff',
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return <div className="container mx-auto p-4 md:p-8">{children}</div>
}

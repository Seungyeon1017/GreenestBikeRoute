import Footer from '@/components/Layout/Footer'
import Navbar from '@/components/Layout/Navbar'
import Providers from '@/components/Layout/Providers'
import { getCollections, getTheme } from '@/lib/api/prismaService'

export default async function Layout({
  children,
}: {
  children: React.ReactNode
}) {
  const collections = await getCollections('PUBLISHED')
  const hasCollections = collections.length > 0

  const theme = await getTheme()

  return (
    <div className="flex h-screen flex-col font-inter">
      <Navbar
        aboutButton={{
          title: theme?.aboutButtonTitle || 'Über das Dashboard',
          text: theme?.aboutButtonText || '',
        }}
        large={hasCollections}
      />
      <div className="flex-1">
        <Providers>{children}</Providers>
      </div>
      <Footer />
    </div>
  )
}

import TranslationsProvider from '@/components/TranslationsProvider'
import { getActiveLocale } from '@/lib/i18n'
import '@/styles/globals.css'
import { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import de from '@/messages/de.json'
import en from '@/messages/en.json'

const messagesMap = { de, en } as const

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })

export const metadata: Metadata = {
  // Social apps need absolute URLs; `app/opengraph-image.png` is the preview.
  metadataBase: new URL('https://greenestbikeroute.ta-a-mi.earth'),
  title: 'GreenestBikeRoute Heilbronn',
  icons: '/favicon.svg',
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const locale = await getActiveLocale()
  const messages = messagesMap[locale as keyof typeof messagesMap] ?? de

  return (
    <html className={inter.variable} lang={locale}>
      <body>
        <TranslationsProvider locale={locale} messages={messages}>
          {children}
        </TranslationsProvider>
      </body>
    </html>
  )
}

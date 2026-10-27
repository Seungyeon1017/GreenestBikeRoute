import { Fraunces } from 'next/font/google'
import AppFooter from '@/components/Greenest/Layout/AppFooter'
import AppHeader from '@/components/Greenest/Layout/AppHeader'

// Serif for headings (Tailwind `font-display`); body text stays Inter.
const fraunces = Fraunces({
  subsets: ['latin'],
  variable: '--font-display',
  weight: ['400', '500', '600'],
})

export default function GreenestLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div
      className={`${fraunces.variable} flex min-h-screen flex-col bg-leaf-cream font-inter text-leaf-ink antialiased`}
    >
      <AppHeader />
      <main className="flex flex-1 flex-col">{children}</main>
      <AppFooter />
    </div>
  )
}

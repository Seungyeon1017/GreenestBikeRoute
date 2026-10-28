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
  // A page marked `data-workspace` (the Overview) fills exactly the window on
  // wide screens: the page itself doesn't scroll, only its panels do.
  return (
    <div
      className={`${fraunces.variable} group flex min-h-screen flex-col bg-leaf-cream font-inter text-leaf-ink antialiased lg:has-[[data-workspace]]:h-dvh`}
    >
      <AppHeader />
      <main className="flex min-h-0 flex-1 flex-col">{children}</main>
      <AppFooter />
    </div>
  )
}

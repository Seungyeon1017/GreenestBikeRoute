import AppFooter from '@/components/Greenest/Layout/AppFooter'
import AppHeader from '@/components/Greenest/Layout/AppHeader'

export default function GreenestLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex min-h-screen flex-col bg-stone-50 font-inter text-stone-800">
      <AppHeader />
      <main className="flex flex-1 flex-col">{children}</main>
      <AppFooter />
    </div>
  )
}

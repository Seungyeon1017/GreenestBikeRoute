'use client'

import { cx } from 'class-variance-authority'
import { Leaf } from 'lucide-react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useTranslation } from 'react-i18next'
import LanguageSwitcher from './LanguageSwitcher'
import { NAV_TABS } from './navigation'

export default function AppHeader() {
  const pathname = usePathname() ?? ''
  const { t } = useTranslation()

  return (
    // Phones: logo and language on the first row, the tabs full width below.
    <header className="z-30 border-b border-leaf-sand/80 bg-leaf-cream/85 backdrop-blur-md md:sticky md:top-0">
      <div className="mx-auto grid max-w-[1920px] grid-cols-[1fr_auto] items-center gap-3 px-4 py-3 md:flex md:justify-between md:px-8 md:py-4">
        <Link
          className="group flex items-center gap-3 self-start rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-leaf-moss md:self-auto"
          href="/overview"
        >
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-leaf-forest text-leaf-cream ring-4 ring-leaf-mint transition-transform group-hover:rotate-12">
            <Leaf aria-hidden className="h-5 w-5" />
          </span>
          <span className="flex flex-col leading-tight">
            <span className="font-display text-xl font-semibold tracking-tight text-leaf-forest">
              Greenest<span className="italic text-leaf-fern">Bike</span>Route
            </span>
            <span className="text-[11px] uppercase tracking-[0.2em] text-leaf-muted">
              Heilbronn
            </span>
          </span>
        </Link>

        <div className="contents md:flex md:items-center md:gap-3">
          <nav
            aria-label={t('greenest.nav.label')}
            className="order-last col-span-2 md:order-none"
          >
            <ul className="grid grid-cols-3 gap-1 rounded-2xl border border-leaf-sand bg-white/70 p-1 shadow-soft lg:rounded-full">
              {NAV_TABS.map(({ href, key, icon: Icon }) => {
                const active =
                  pathname === href || pathname.startsWith(`${href}/`)
                return (
                  <li key={href}>
                    <Link
                      aria-current={active ? 'page' : undefined}
                      className={cx(
                        // Up to tablets: icon above a smaller label, so all three fit.
                        'flex flex-col items-center justify-center gap-0.5 whitespace-nowrap rounded-xl px-1 py-1.5 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-leaf-moss lg:flex-row lg:gap-2 lg:rounded-full lg:px-5 lg:py-2 lg:text-sm',
                        active
                          ? 'bg-leaf-forest text-leaf-cream shadow-sm'
                          : 'text-leaf-muted hover:bg-leaf-mint hover:text-leaf-forest',
                      )}
                      href={href}
                    >
                      <Icon aria-hidden className="h-4 w-4 shrink-0" />
                      {t(`greenest.nav.${key}`)}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </nav>
          <LanguageSwitcher />
        </div>
      </div>
    </header>
  )
}

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
    <header className="sticky top-0 z-30 border-b border-leaf-sand/80 bg-leaf-cream/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-[1920px] flex-col gap-3 px-4 py-3 md:flex-row md:items-center md:justify-between md:px-8 md:py-4">
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

        <div className="flex items-center gap-3">
                  <nav aria-label={t('greenest.nav.label')}>
          <ul className="grid grid-cols-3 gap-1 rounded-full border border-leaf-sand bg-white/70 p-1 shadow-soft">
            {NAV_TABS.map(({ href, key, icon: Icon }) => {
              const active =
                pathname === href || pathname.startsWith(`${href}/`)
              return (
                <li key={href}>
                  <Link
                    aria-current={active ? 'page' : undefined}
                    className={cx(
                      'flex items-center justify-center gap-2 whitespace-nowrap rounded-full px-3 py-2 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-leaf-moss md:px-5',
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

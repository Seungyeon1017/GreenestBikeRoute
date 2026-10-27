'use client'

import { cx } from 'class-variance-authority'
import { Bike } from 'lucide-react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useTranslation } from 'react-i18next'
import { NAV_TABS } from './navigation'

export default function AppHeader() {
  const pathname = usePathname() ?? ''
  const { t } = useTranslation()

  return (
    <header className="sticky top-0 z-30 border-b border-stone-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-[1920px] flex-col gap-3 px-4 py-3 md:flex-row md:items-center md:justify-between md:px-8">
        <Link
          className="flex items-center gap-2 self-start rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 md:self-auto"
          href="/overview"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-600 text-white">
            <Bike aria-hidden className="h-5 w-5" />
          </span>
          <span className="font-lexend text-lg font-bold text-stone-900">
            GreenestBikeRoute
          </span>
          <span className="hidden text-sm text-stone-500 lg:inline">
            · Heilbronn
          </span>
        </Link>

        <nav aria-label={t('greenest.nav.label')}>
          <ul className="grid grid-cols-3 gap-1 rounded-xl bg-stone-100 p-1">
            {NAV_TABS.map(({ href, key, icon: Icon }) => {
              const active =
                pathname === href || pathname.startsWith(`${href}/`)
              return (
                <li key={href}>
                  <Link
                    aria-current={active ? 'page' : undefined}
                    className={cx(
                      'flex items-center justify-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 md:px-5',
                      active
                        ? 'bg-white text-emerald-700 shadow-sm'
                        : 'text-stone-600 hover:bg-white/60 hover:text-stone-900',
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
      </div>
    </header>
  )
}

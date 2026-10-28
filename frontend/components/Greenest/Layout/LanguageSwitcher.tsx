'use client'

import { cx } from 'class-variance-authority'
import { useRouter } from 'next/navigation'
import { useTransition } from 'react'
import { useTranslation } from 'react-i18next'
import { type Locale, supportedLocales } from '@/lib/i18n/settings'

const ONE_YEAR_S = 60 * 60 * 24 * 365

/**
 * DE / EN toggle. Saves the choice in the `lang` cookie, which the root layout
 * reads on the server (lib/i18n.ts), then re-renders the page in that language.
 */
export default function LanguageSwitcher() {
  const { t, i18n } = useTranslation()
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const active = i18n.language

  function choose(locale: Locale) {
    if (locale === active) {
      return
    }
    document.cookie = `lang=${locale}; path=/; max-age=${ONE_YEAR_S}; samesite=lax`
    // Ask the server for the page again; the layout now picks the new language.
    startTransition(() => router.refresh())
  }

  return (
    <div
      aria-busy={pending}
      aria-label={t('greenest.language.label')}
      className="flex rounded-full border border-leaf-sand bg-white/70 p-1 shadow-soft"
      role="group"
    >
      {supportedLocales.map(locale => (
        <button
          aria-pressed={locale === active}
          className={cx(
            'rounded-full px-3 py-1.5 text-xs font-semibold uppercase transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-leaf-moss',
            locale === active
              ? 'bg-leaf-forest text-leaf-cream'
              : 'text-leaf-muted hover:bg-leaf-mint hover:text-leaf-forest',
          )}
          disabled={pending}
          key={locale}
          lang={locale}
          onClick={() => choose(locale)}
          title={t(`greenest.language.${locale}`)}
          type="button"
        >
          {locale}
        </button>
      ))}
    </div>
  )
}
'use client'

import { cx } from 'class-variance-authority'
import { Bike, ExternalLink } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export const SENSEBOX_BIKE_URL = 'https://sensebox.kaufen/pages/sensebox-bike'

/**
 * Invites riders to collect data themselves with a senseBox:bike (citizen
 * science). Opens the senseBox:bike page in a new tab.
 */
export default function SenseBoxCta({ className }: { className?: string }) {
  const { t } = useTranslation()
  return (
    <section
      className={cx(
        'flex flex-col gap-5 rounded-[2rem] border border-leaf-sage/50 bg-leaf-mint p-6 md:flex-row md:items-center md:justify-between md:p-10',
        className,
      )}
    >
      <div className="flex items-start gap-4">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-leaf-forest text-leaf-cream">
          <Bike aria-hidden className="h-6 w-6" />
        </span>
        <div className="max-w-2xl space-y-1.5">
          <h2 className="font-display text-2xl font-medium tracking-tight text-leaf-forest md:text-3xl">
            {t('greenest.senseBox.title')}
          </h2>
          <p className="text-sm leading-relaxed text-leaf-muted">
            {t('greenest.senseBox.text')}
          </p>
        </div>
      </div>
      <a
        className="flex shrink-0 items-center gap-2 self-start rounded-full bg-leaf-forest px-5 py-2.5 text-sm font-semibold text-leaf-cream shadow-sm transition-colors hover:bg-leaf-moss focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-leaf-moss md:self-center"
        href={SENSEBOX_BIKE_URL}
        rel="noreferrer"
        target="_blank"
      >
        {t('greenest.senseBox.button')}
        <ExternalLink aria-hidden className="h-4 w-4" />
        <span className="sr-only">{t('greenest.senseBox.newTab')}</span>
      </a>
    </section>
  )
}

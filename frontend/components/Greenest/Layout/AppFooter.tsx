'use client'

import { Leaf } from 'lucide-react'
import Link from 'next/link'
import { useTranslation } from 'react-i18next'

/** Keeps the attribution and license notice of the original dashboard visible. */
export default function AppFooter() {
  const { t } = useTranslation()

  return (
    <footer className="mt-8 bg-leaf-forest text-leaf-cream/80">
      <div className="mx-auto flex max-w-[1920px] flex-col gap-6 px-4 py-8 md:flex-row md:items-end md:justify-between md:px-8">
        <div className="flex flex-col gap-3">
          <span className="flex items-center gap-2 font-display text-lg text-leaf-cream">
            <Leaf aria-hidden className="h-4 w-4 text-leaf-sage" />
            {t('greenest.vision')}
          </span>
          <p className="max-w-2xl text-xs leading-relaxed">
            {t('greenest.footer.basedOn')}{' '}
            <span className="font-medium text-leaf-cream">
              Green City Dashboard Heilbronn
            </span>{' '}
            (Arkadia, reedu, AIM) ·{' '}
            <a
              className="underline decoration-leaf-sage/60 underline-offset-2 hover:text-leaf-cream"
              href="https://www.gnu.org/licenses/agpl-3.0.en.html"
              rel="noreferrer"
              target="_blank"
            >
              AGPL-3.0
            </a>{' '}
            · {t('greenest.footer.mapData')} © OpenStreetMap, CARTO · ATRAI
            senseBox:bike
          </p>
        </div>
        <div className="flex gap-5 text-xs">
          <Link
            className="underline decoration-leaf-sage/60 underline-offset-2 hover:text-leaf-cream"
            href="/impressum"
          >
            {t('footer.impressum')}
          </Link>
          <Link
            className="underline decoration-leaf-sage/60 underline-offset-2 hover:text-leaf-cream"
            href="/datenschutz"
          >
            {t('footer.datenschutz')}
          </Link>
        </div>
      </div>
    </footer>
  )
}

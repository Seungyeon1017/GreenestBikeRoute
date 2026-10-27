'use client'

import Link from 'next/link'
import { useTranslation } from 'react-i18next'

/** Keeps the attribution and license notice of the original dashboard visible. */
export default function AppFooter() {
  const { t } = useTranslation()

  return (
    <footer className="border-t border-stone-200 bg-white">
      <div className="mx-auto flex max-w-[1920px] flex-col gap-2 px-4 py-4 text-xs text-stone-500 md:flex-row md:items-center md:justify-between md:px-8">
        <p>
          {t('greenest.footer.basedOn')}{' '}
          <span className="font-medium text-stone-700">
            Green City Dashboard Heilbronn
          </span>{' '}
          (Arkadia, reedu, AIM) ·{' '}
          <a
            className="underline hover:text-stone-700"
            href="https://www.gnu.org/licenses/agpl-3.0.en.html"
            rel="noreferrer"
            target="_blank"
          >
            AGPL-3.0
          </a>{' '}
          · {t('greenest.footer.mapData')} © OpenStreetMap, CARTO
        </p>
        <div className="flex gap-4">
          <Link className="underline hover:text-stone-700" href="/impressum">
            {t('footer.impressum')}
          </Link>
          <Link className="underline hover:text-stone-700" href="/datenschutz">
            {t('footer.datenschutz')}
          </Link>
        </div>
      </div>
    </footer>
  )
}

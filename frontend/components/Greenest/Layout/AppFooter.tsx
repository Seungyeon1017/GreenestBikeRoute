'use client'

import { Leaf } from 'lucide-react'
import Link from 'next/link'
import { Fragment } from 'react'
import { useTranslation } from 'react-i18next'

const REPOSITORY_URL = 'https://github.com/Seungyeon1017/GreenestBikeRoute'
const DL_DE_BY = {
  label: 'dl-de/by-2-0',
  href: 'https://www.govdata.de/dl-de/by-2-0',
}

/**
 * Credits for the data shown in the app, worded as in data/README.md#licenses.
 * `credit` is a translation key when it starts with `greenest.`.
 */
const DATA_CREDITS: Array<{
  credit: string
  license?: { label: string; href: string }
}> = [
  {
    credit: 'greenest.footer.osm',
    license: { label: 'ODbL', href: 'https://www.openstreetmap.org/copyright' },
  },
  { credit: '© CARTO' },
  { credit: 'ATRAI, reedu GmbH & Co. KG' },
  { credit: 'Datenquelle: LGL, www.lgl-bw.de', license: DL_DE_BY },
  { credit: 'Stadt Heilbronn, Baumkataster', license: DL_DE_BY },
  {
    credit: 'Mapillary',
    license: {
      label: 'CC BY-SA 4.0',
      href: 'https://creativecommons.org/licenses/by-sa/4.0/',
    },
  },
]

const LINK =
  'underline decoration-leaf-sage/60 underline-offset-2 hover:text-leaf-cream'

/** Keeps the attribution and license notice of the original dashboard visible. */
export default function AppFooter() {
  const { t } = useTranslation()

  return (
    // Slim single line under a full-window workspace page (see the layout).
    <footer className="mt-8 bg-leaf-forest text-leaf-cream/80 lg:group-has-[[data-workspace]]:mt-0">
      <div className="mx-auto flex max-w-[1920px] flex-col gap-6 px-4 py-8 md:flex-row md:items-end md:justify-between md:px-8 lg:group-has-[[data-workspace]]:items-center lg:group-has-[[data-workspace]]:py-2.5">
        <div className="flex flex-col gap-3">
          <span className="flex items-center gap-2 font-display text-lg text-leaf-cream lg:group-has-[[data-workspace]]:hidden">
            <Leaf aria-hidden className="h-4 w-4 text-leaf-sage" />
            {t('greenest.vision')}
          </span>
          <div className="flex max-w-3xl flex-col gap-1 text-xs leading-relaxed lg:group-has-[[data-workspace]]:max-w-none">
            <p>
              {t('greenest.footer.basedOn')}{' '}
              <span className="font-medium text-leaf-cream">
                Green City Dashboard Heilbronn
              </span>{' '}
              (Arkadia, reedu, AIM) ·{' '}
              <a
                className={LINK}
                href="https://www.gnu.org/licenses/agpl-3.0.en.html"
                rel="noreferrer"
                target="_blank"
              >
                AGPL-3.0
              </a>{' '}
              ·{' '}
              {/* AGPL-3.0 §13: offer the source to everyone using the site. */}
              <a
                className={LINK}
                href={REPOSITORY_URL}
                rel="noreferrer"
                target="_blank"
              >
                {t('greenest.footer.sourceCode')}
              </a>
            </p>
            <p>
              {t('greenest.footer.data')}:{' '}
              {DATA_CREDITS.map(({ credit, license }, i) => (
                <Fragment key={credit}>
                  {i > 0 && ' · '}
                  {credit.startsWith('greenest.') ? t(credit) : credit}
                  {license && (
                    <>
                      ,{' '}
                      <a
                        className={LINK}
                        href={license.href}
                        rel="noreferrer"
                        target="_blank"
                      >
                        {license.label}
                      </a>
                    </>
                  )}
                </Fragment>
              ))}
            </p>
          </div>
        </div>
        <div className="flex gap-5 text-xs">
          <a
            className={LINK}
            href="https://reedu.de/imprint"
            rel="noreferrer"
            target="_blank"
          >
            {t('footer.impressum')}
          </a>
          <Link className={LINK} href="/datenschutz">
            {t('footer.datenschutz')}
          </Link>
        </div>
      </div>
    </footer>
  )
}

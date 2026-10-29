'use client'

import { MapPin, Trees } from 'lucide-react'
import Link from 'next/link'
import { useTranslation } from 'react-i18next'
import type { HighlightPlace } from '@/types/greenest'

const VIEW_ON_MAP_CLASS =
  'flex items-center gap-1.5 self-start rounded-lg text-sm font-medium text-leaf-moss hover:text-leaf-forest disabled:cursor-not-allowed disabled:text-leaf-muted/70'

/** Plan trip reads `to` (lng,lat) and `name` and sets that place as the destination. */
function planTripHref(place: HighlightPlace) {
  const [lng, lat] = place.location ?? []
  const query = new URLSearchParams({ to: `${lng},${lat}`, name: place.name })
  return `/plan-trip?${query}`
}

export default function PlaceCard({ place }: { place: HighlightPlace }) {
  const { t } = useTranslation()
  const credit = place.imageCredit

  return (
    <article className="group flex flex-col overflow-hidden rounded-3xl border border-leaf-sand/80 bg-white shadow-soft transition-transform hover:-translate-y-0.5">
      <div className="relative flex h-36 items-center justify-center overflow-hidden bg-gradient-to-br from-leaf-mint via-leaf-cream to-leaf-sand/60">
        {place.imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element -- small static photos from /public
          <img
            alt={place.name}
            className="h-full w-full object-cover transition-transform group-hover:scale-105"
            loading="lazy"
            src={place.imageUrl}
          />
        ) : (
          <Trees
            aria-hidden
            className="h-12 w-12 text-leaf-moss/40 transition-transform group-hover:scale-110"
          />
        )}
        {place.imageUrl && credit && (
          <a
            className="absolute bottom-1 right-1 max-w-[calc(100%-0.5rem)] truncate rounded bg-black/55 px-1.5 py-0.5 text-[10px] text-white/90 hover:bg-black/75"
            href={credit.sourceUrl}
            rel="noopener noreferrer"
            target="_blank"
          >
            {t('greenest.highlights.photoBy', {
              author: credit.author,
              license: credit.license,
            })}
          </a>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-display text-lg font-medium text-leaf-forest">
            {place.name}
          </h3>
        </div>
        <p className="flex-1 text-sm text-leaf-muted">
          {t(`greenest.highlights.places.${place.id}`)}
        </p>
        {place.location ? (
          <Link className={VIEW_ON_MAP_CLASS} href={planTripHref(place)}>
            <MapPin aria-hidden className="h-4 w-4" />
            {t('greenest.highlights.viewOnMap')}
          </Link>
        ) : (
          <button
            className={VIEW_ON_MAP_CLASS}
            disabled
            title={t('greenest.highlights.noLocation')}
            type="button"
          >
            <MapPin aria-hidden className="h-4 w-4" />
            {t('greenest.highlights.viewOnMap')}
          </button>
        )}
      </div>
    </article>
  )
}

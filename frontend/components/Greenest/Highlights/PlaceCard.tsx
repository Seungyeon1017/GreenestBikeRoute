'use client'

import { MapPin, Trees } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import AvailabilityBadge from '@/components/Greenest/ui/AvailabilityBadge'
import type { HighlightPlace } from '@/types/greenest'

export default function PlaceCard({ place }: { place: HighlightPlace }) {
  const { t } = useTranslation()

  return (
    <article className="flex flex-col overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm transition-shadow hover:shadow-md">
      {/* Image slot; replaced by place.imageUrl once licensed photos are available. */}
      <div className="flex h-32 items-center justify-center bg-gradient-to-br from-emerald-100 to-lime-50">
        <Trees aria-hidden className="h-10 w-10 text-emerald-600/60" />
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-lexend text-base font-bold text-stone-900">
            {place.name}
          </h3>
          {place.demo && <AvailabilityBadge availability="demo" />}
        </div>
        <p className="flex-1 text-sm text-stone-600">{place.description}</p>
        <button
          className="flex items-center gap-1.5 self-start rounded-lg text-sm font-medium text-emerald-700 hover:text-emerald-800 disabled:cursor-not-allowed disabled:text-stone-400"
          disabled={!place.location}
          title={
            place.location ? undefined : t('greenest.highlights.noLocation')
          }
          type="button"
        >
          <MapPin aria-hidden className="h-4 w-4" />
          {t('greenest.highlights.viewOnMap')}
        </button>
      </div>
    </article>
  )
}

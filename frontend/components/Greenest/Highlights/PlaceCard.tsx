'use client'

import { MapPin, Trees } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import AvailabilityBadge from '@/components/Greenest/ui/AvailabilityBadge'
import type { HighlightPlace } from '@/types/greenest'

export default function PlaceCard({ place }: { place: HighlightPlace }) {
  const { t } = useTranslation()

  return (
    <article className="group flex flex-col overflow-hidden rounded-3xl border border-leaf-sand/80 bg-white shadow-soft transition-transform hover:-translate-y-0.5">
      {/* Image slot; replaced by place.imageUrl once licensed photos are available. */}
      <div className="relative flex h-36 items-center justify-center bg-gradient-to-br from-leaf-mint via-leaf-cream to-leaf-sand/60">
        <Trees
          aria-hidden
          className="h-12 w-12 text-leaf-moss/40 transition-transform group-hover:scale-110"
        />
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-display text-lg font-medium text-leaf-forest">
            {place.name}
          </h3>
          {place.demo && <AvailabilityBadge availability="demo" />}
        </div>
        <p className="flex-1 text-sm text-leaf-muted">{place.description}</p>
        <button
          className="flex items-center gap-1.5 self-start rounded-lg text-sm font-medium text-leaf-moss hover:text-leaf-forest disabled:cursor-not-allowed disabled:text-leaf-muted/70"
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

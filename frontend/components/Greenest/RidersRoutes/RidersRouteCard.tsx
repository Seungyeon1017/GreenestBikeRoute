'use client'

import { MapPin } from 'lucide-react'
import Link from 'next/link'
import { useTranslation } from 'react-i18next'
import type { CommunityRouteSummary } from '@/types/users'
import { day, km, rideTime } from './format'
import HeartSaveButtons from './HeartSaveButtons'
import RouteShape from './RouteShape'
import TagList from './TagList'

/** One riders' leisure route on Highlights: its shape, what it is, heart/save, and a link to the map. */
export default function RidersRouteCard({
  route,
  onChange,
}: {
  route: CommunityRouteSummary
  onChange?: (_route: CommunityRouteSummary) => void
}) {
  const { t, i18n } = useTranslation()

  return (
    <article className="group flex flex-col overflow-hidden rounded-3xl border border-leaf-sand/80 bg-white shadow-soft transition-transform hover:-translate-y-0.5">
      <div className="flex h-32 items-center justify-center bg-gradient-to-br from-leaf-mint via-leaf-cream to-leaf-sand/60">
        <RouteShape className="h-24 w-24" points={route.preview} />
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <h3 className="font-display text-lg font-medium leading-snug text-leaf-forest">
          {route.name}
        </h3>
        <p className="text-xs text-leaf-muted">
          {[
            route.author
              ? t('greenest.ridersRoutes.by', { name: route.author })
              : t('greenest.ridersRoutes.byRider'),
            day(route.recorded_on, i18n.language),
          ].join(' · ')}
        </p>
        <p className="text-sm font-medium text-leaf-ink">
          {km(route.length_m)} · {rideTime(route.moving_s)}
        </p>
        <TagList isLoop={route.is_loop} tags={route.tags} />
        {route.description && (
          <p className="line-clamp-3 flex-1 text-sm text-leaf-muted">
            {route.description}
          </p>
        )}
        <HeartSaveButtons
          className="mt-auto"
          loginNext="/highlights"
          onChange={onChange}
          route={route}
        />
        <Link
          className="flex items-center gap-1.5 self-start text-sm font-medium text-leaf-moss hover:text-leaf-forest"
          href={`/plan-trip?route=${route.id}`}
        >
          <MapPin aria-hidden className="h-4 w-4" />
          {t('greenest.highlights.viewOnMap')}
        </Link>
      </div>
    </article>
  )
}

'use client'

import { useTranslation } from 'react-i18next'
import AvailabilityBadge from '@/components/Greenest/ui/AvailabilityBadge'
import Card, { CardTitle } from '@/components/Greenest/ui/Card'
import type { RouteKind } from '@/types/greenest'

/** Colours used for each route on the map and in the comparison. */
export const ROUTE_COLORS: Record<RouteKind, string> = {
  fastest: '#64748b',
  greenest: '#16a34a',
}

const METRICS = [
  'duration',
  'distance',
  'greenScore',
  'greenery',
  'noise',
  'airQuality',
] as const

/**
 * Side-by-side comparison of the fastest and greenest route.
 * Until a route is calculated (Phase 4) every value shows "–" and is marked unavailable.
 */
export default function RouteComparison() {
  const { t } = useTranslation()
  const kinds: RouteKind[] = ['fastest', 'greenest']

  return (
    <Card className="flex flex-col gap-3">
      <CardTitle>{t('greenest.planTrip.comparisonTitle')}</CardTitle>
      <div className="grid grid-cols-2 gap-3">
        {kinds.map(kind => (
          <div
            className="flex flex-col gap-2 rounded-xl border border-leaf-sand/70 p-3"
            key={kind}
          >
            <div className="flex items-center gap-2">
              <span
                aria-hidden
                className="h-1.5 w-6 rounded-full"
                style={{ backgroundColor: ROUTE_COLORS[kind] }}
              />
              <span className="text-sm font-semibold text-leaf-ink">
                {t(`greenest.planTrip.routes.${kind}`)}
              </span>
            </div>
            <p className="text-xs text-leaf-muted">
              {t(`greenest.planTrip.routes.${kind}Hint`)}
            </p>
            <dl className="flex flex-col gap-1.5">
              {METRICS.map(metric => (
                <div
                  className="flex items-center justify-between gap-2 text-xs"
                  key={metric}
                >
                  <dt className="text-leaf-muted">
                    {t(`greenest.planTrip.metrics.${metric}`)}
                  </dt>
                  <dd className="font-medium tabular-nums text-leaf-muted/70">
                    –
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
      <div className="flex items-start gap-2 rounded-xl bg-leaf-cream p-3 text-xs text-leaf-muted">
        <AvailabilityBadge availability="unavailable" className="shrink-0" />
        <span>{t('greenest.planTrip.emptyState')}</span>
      </div>
    </Card>
  )
}

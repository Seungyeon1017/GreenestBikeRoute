'use client'

import { useTranslation } from 'react-i18next'
import AvailabilityBadge from '@/components/Greenest/ui/AvailabilityBadge'
import Card, { CardTitle } from '@/components/Greenest/ui/Card'
import type {
  RouteKind,
  RouteProperties,
  RouteComparison as RouteResult,
} from '@/types/greenest'

/** Colours used for each route on the map and in the comparison. */
export const ROUTE_COLORS: Record<RouteKind, string> = {
  greenest: '#16a34a',
  shortest: '#64748b',
}

/** Formats a number, or shows "–" when the backend sent null (no measurement). */
function fixed(value: number | null, digits: number): string {
  return value == null ? '–' : value.toFixed(digits)
}

/** One row per metric: the translation key and how to show the value. */
const METRICS: Array<{
  key: string
  format: (_p: RouteProperties) => string
}> = [
  { key: 'distance', format: p => `${(p.length_m / 1000).toFixed(2)} km` },
  { key: 'roughness', format: p => fixed(p.mean_roughness, 1) },
  { key: 'overtaking', format: p => String(p.danger_points) },
  { key: 'airQuality', format: p => fixed(p.mean_pm_risk, 2) },
  { key: 'stopGo', format: p => fixed(p.mean_stop_go, 2) },
]

type RouteComparisonProps = {
  result: RouteResult | null
}

/** Side-by-side comparison of the shortest route and the route for the chosen penalties. */
export default function RouteComparison({ result }: RouteComparisonProps) {
  const { t } = useTranslation()
  const kinds: RouteKind[] = ['shortest', 'greenest']

  // The backend calls the penalty-based route "route"; on screen it's the greenest route.
  const propertiesFor = (kind: RouteKind) =>
    kind === 'shortest' ? result?.shortest.properties : result?.route.properties

  return (
    <Card className="flex flex-col gap-3">
      <CardTitle>{t('greenest.planTrip.comparisonTitle')}</CardTitle>
      <div className="grid grid-cols-2 gap-3">
        {kinds.map(kind => {
          const properties = propertiesFor(kind)
          return (
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
                {METRICS.map(({ key, format }) => (
                  <div
                    className="flex items-center justify-between gap-2 text-xs"
                    key={key}
                  >
                    <dt className="text-leaf-muted">
                      {t(`greenest.planTrip.metrics.${key}`)}
                    </dt>
                    <dd className="font-medium tabular-nums text-leaf-ink">
                      {properties ? format(properties) : '–'}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          )
        })}
      </div>

      {result ? (
        <p className="rounded-xl bg-leaf-cream p-3 text-xs font-medium text-leaf-ink">
          {result.same_path
            ? t('greenest.planTrip.sameAsShortest')
            : t('greenest.planTrip.detour', {
                pct: result.detour_pct.toFixed(1),
              })}
        </p>
      ) : (
        <div className="flex items-start gap-2 rounded-xl bg-leaf-cream p-3 text-xs text-leaf-muted">
          <AvailabilityBadge availability="unavailable" className="shrink-0" />
          <span>{t('greenest.planTrip.emptyState')}</span>
        </div>
      )}
    </Card>
  )
}

/* 'use client'

import { useTranslation } from 'react-i18next'
import AvailabilityBadge from '@/components/Greenest/ui/AvailabilityBadge'
import Card, { CardTitle } from '@/components/Greenest/ui/Card'
import type { RouteKind } from '@/types/greenest'

// Colours used for each route on the map and in the comparison.
export const ROUTE_COLORS: Record<RouteKind, string> = {
  shortest: '#64748b',
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


// Side-by-side comparison of the fastest and greenest route.
// Until a route is calculated (Phase 4) every value shows "–" and is marked unavailable.

export default function RouteComparison() {
  const { t } = useTranslation()
  const kinds: RouteKind[] = ['shortest', 'greenest']

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
 */
'use client'

import { cx } from 'class-variance-authority'
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

/** Riding time as "12 min" (or "1 h 05 min"). */
function minutes(seconds: number): string {
  const total = Math.round(seconds / 60)
  if (total < 60) {
    return `${total} min`
  }
  return `${Math.floor(total / 60)} h ${String(total % 60).padStart(2, '0')} min`
}

/** A percentage with its sign, e.g. "+3.3 %" or "−2.0 %". */
function signedPct(value: number): string {
  const sign = value > 0 ? '+' : value < 0 ? '−' : '±'
  return `${sign}${Math.abs(value).toFixed(1)} %`
}

/** One row per metric: the translation key and how to show the value. */
const METRICS: Array<{
  key: string
  format: (_p: RouteProperties) => string
}> = [
  { key: 'duration', format: p => minutes(p.duration_s) },
  { key: 'distance', format: p => `${(p.length_m / 1000).toFixed(2)} km` },
  { key: 'roughness', format: p => fixed(p.mean_roughness, 1) },
  { key: 'overtaking', format: p => String(p.danger_points) },
  { key: 'airQuality', format: p => fixed(p.mean_pm_risk, 2) },
  { key: 'stopGo', format: p => fixed(p.mean_stop_go, 2) },
]

type RouteComparisonProps = {
  result: RouteResult | null
  /**
   * True while the trip with a rented vehicle is shown: these two routes are for
   * your own bike, so the card fades like their lines on the map.
   */
  paused?: boolean
}

/** The route's line as drawn on the map: grey dashed for the shortest, green solid for yours. */
function RouteLine({ kind }: { kind: RouteKind }) {
  return (
    <svg aria-hidden className="h-2 w-6 shrink-0" viewBox="0 0 24 8">
      <line
        stroke={ROUTE_COLORS[kind]}
        strokeDasharray={kind === 'shortest' ? '4 3' : undefined}
        strokeWidth={kind === 'shortest' ? 3.5 : 4.5}
        x1="0"
        x2="24"
        y1="4"
        y2="4"
      />
    </svg>
  )
}

/** Side-by-side comparison of the shortest route and the route for the chosen penalties. */
export default function RouteComparison({
  result,
  paused = false,
}: RouteComparisonProps) {
  const { t } = useTranslation()
  const kinds: RouteKind[] = ['shortest', 'greenest']

  // The backend calls the penalty-based route "route"; on screen it's the greenest route.
  const propertiesFor = (kind: RouteKind) =>
    kind === 'shortest' ? result?.shortest.properties : result?.route.properties

  return (
    <Card className="flex flex-col gap-3">
      <CardTitle>{t('greenest.planTrip.comparisonTitle')}</CardTitle>
      {paused && (
        <p className="rounded-xl border border-leaf-sand bg-leaf-cream p-3 text-xs text-leaf-ink">
          {t('greenest.planTrip.comparisonPaused')}
        </p>
      )}
      <div
        aria-disabled={paused || undefined}
        className={cx(
          'flex flex-col gap-3 transition-opacity',
          paused && 'opacity-40',
        )}
      >
        <div className="grid grid-cols-2 gap-3">
          {kinds.map(kind => {
            const properties = propertiesFor(kind)
            return (
              <div
                className="flex flex-col gap-2 rounded-xl border border-leaf-sand/70 p-3"
                key={kind}
              >
                <div className="flex items-center gap-2">
                  <RouteLine kind={kind} />
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
          <div className="flex flex-col gap-1 rounded-xl bg-leaf-cream p-3 text-xs text-leaf-ink">
            <p className="font-medium">
              {result.same_path
                ? t('greenest.planTrip.sameAsShortest')
                : t('greenest.planTrip.difference', {
                    distance: signedPct(result.detour_pct),
                    time: signedPct(result.extra_time_pct),
                  })}
            </p>
            {/* Which time-of-day factor the backend applied, if a departure time was set. */}
            {result.route.properties.daylight === true && (
              <p className="text-leaf-muted">
                {t('greenest.planTrip.appliedShade')}
              </p>
            )}
            {result.route.properties.daylight === false && (
              <p className="text-leaf-muted">
                {t('greenest.planTrip.appliedDark')}
              </p>
            )}
          </div>
        ) : (
          <div className="flex items-start gap-2 rounded-xl bg-leaf-cream p-3 text-xs text-leaf-muted">
            <AvailabilityBadge
              availability="unavailable"
              className="shrink-0"
            />
            <span>{t('greenest.planTrip.emptyState')}</span>
          </div>
        )}
      </div>
    </Card>
  )
}

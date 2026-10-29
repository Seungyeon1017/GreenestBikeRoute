'use client'

import { cx } from 'class-variance-authority'
import { useTranslation } from 'react-i18next'
import AvailabilityBadge from '@/components/Greenest/ui/AvailabilityBadge'
import Card, { CardTitle } from '@/components/Greenest/ui/Card'
import InfoTip from '@/components/Greenest/ui/InfoTip'
import type {
  RouteKind,
  RouteProperties,
  RouteComparison as RouteResult,
} from '@/types/greenest'
import WhyThisRoute from './WhyThisRoute'
import type { FlagFocus } from './WhyThisRoute'

/** Colours used for each route on the map and in the comparison. */
export const ROUTE_COLORS: Record<RouteKind, string> = {
  greenest: '#16a34a',
  shortest: '#64748b',
}

/** Riding time as "12 min" (or "1 h 05 min"). */
function minutes(seconds: number): string {
  const total = Math.round(seconds / 60)
  if (total < 60) {
    return `${total} min`
  }
  return `${Math.floor(total / 60)} h ${String(total % 60).padStart(2, '0')} min`
}

/** A number with fixed decimals in the page language, or "–" when nothing was measured. */
function fixed(value: number | null, digits: number, language: string): string {
  return value == null
    ? '–'
    : value.toLocaleString(language, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      })
}

/** One row per metric: the translation key and how to show the value. */
const METRICS: Array<{
  key: string
  format: (_p: RouteProperties, _language: string) => string
  /** Only shown when either route has a value (shade by day, lighting after dark). */
  optional?: (_p: RouteProperties) => number | null
}> = [
  { key: 'distance', format: (p, l) => `${fixed(p.length_m / 1000, 2, l)} km` },
  { key: 'duration', format: p => minutes(p.duration_s) },
  { key: 'roughness', format: (p, l) => fixed(p.mean_roughness, 1, l) },
  { key: 'overtaking', format: p => String(p.danger_points) },
  { key: 'airQuality', format: (p, l) => fixed(p.mean_pm_risk, 2, l) },
  { key: 'stopGo', format: (p, l) => fixed(p.mean_stop_go, 2, l) },
  {
    key: 'shade',
    format: (p, l) => fixed(p.mean_shade, 2, l),
    optional: p => p.mean_shade,
  },
  {
    key: 'lit',
    format: (p, l) => fixed(p.mean_lit, 2, l),
    optional: p => (p.daylight === false ? p.mean_lit : null),
  },
  { key: 'kcal', format: p => `~${Math.round(p.kcal)}` },
]

const percent = (share: number) => `${Math.round(share * 100)} %`

/** Info for a metric, one line per route: where roughness comes from, and whether kcal counts the climbs. */
const TIPS: Record<
  string,
  (_p: RouteProperties) => [key: string, values: Record<string, unknown>]
> = {
  roughness: p => [
    'roughnessRoute',
    {
      measured: percent(p.measured_share),
      estimated: percent(p.estimated_share),
      unknown: percent(Math.max(0, 1 - p.measured_share - p.estimated_share)),
    },
  ],
  kcal: p =>
    p.climb_m == null
      ? ['kcalNoHeight', {}]
      : ['kcalRoute', { m: Math.round(p.climb_m) }],
}

function MetricTip({
  metric,
  result,
}: {
  metric: string
  result: RouteResult
}) {
  const { t } = useTranslation()
  const routes: Array<[RouteKind, RouteProperties]> = [
    // In the order of the table's columns.
    ['shortest', result.shortest.properties],
    ['greenest', result.route.properties],
  ]
  return (
    <>
      {routes.map(([kind, p]) => {
        const [key, values] = TIPS[metric](p)
        return (
          <span className="block" key={kind}>
            <span className="font-medium text-leaf-ink">
              {t(`greenest.planTrip.routes.${kind}Short`)}:
            </span>{' '}
            {t(`greenest.planTrip.metrics.tips.${key}`, values)}
          </span>
        )
      })}
      <span className="mt-1 block text-leaf-muted">
        {t(`greenest.planTrip.metrics.tips.${metric}`)}
      </span>
    </>
  )
}

type RouteComparisonProps = {
  result: RouteResult | null
  /**
   * True while the trip with a rented vehicle is shown: these two routes are for
   * your own bike, so the card fades like their lines on the map.
   */
  paused?: boolean
  /** Links the "Why this route?" rows to the map. */
  focus?: FlagFocus
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

/** The shortest route and the route for the chosen settings in one table, and why yours goes where it goes. */
export default function RouteComparison({
  result,
  paused = false,
  focus,
}: RouteComparisonProps) {
  const { t, i18n } = useTranslation()
  const kinds: RouteKind[] = ['shortest', 'greenest']

  // The backend calls the penalty-based route "route"; on screen it's the greenest route.
  const propertiesFor = (kind: RouteKind) =>
    kind === 'shortest' ? result?.shortest.properties : result?.route.properties
  const rows = METRICS.filter(
    ({ optional }) =>
      !optional ||
      kinds.some(kind => {
        const p = propertiesFor(kind)
        return p != null && optional(p) != null
      }),
  )

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
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr>
              <th className="pb-1" scope="col">
                <span className="sr-only">
                  {t('greenest.planTrip.comparisonTitle')}
                </span>
              </th>
              {kinds.map(kind => (
                <th
                  className="whitespace-nowrap pb-1 pl-3 text-right font-semibold text-leaf-ink"
                  key={kind}
                  scope="col"
                  title={t(`greenest.planTrip.routes.${kind}Hint`)}
                >
                  <span className="inline-flex items-center gap-1.5">
                    <RouteLine kind={kind} />
                    {t(`greenest.planTrip.routes.${kind}Short`)}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ key, format }) => (
              // relative: a row's info panel spans the table's width.
              <tr className="relative border-t border-leaf-sand/50" key={key}>
                <th
                  className="py-1 text-left font-normal text-leaf-muted"
                  scope="row"
                >
                  <span className="inline-flex items-center gap-1">
                    {t(`greenest.planTrip.metrics.${key}`)}
                    {result && key in TIPS && (
                      <InfoTip
                        label={t('greenest.planTrip.info.about', {
                          name: t(`greenest.planTrip.metrics.${key}`),
                        })}
                      >
                        <MetricTip metric={key} result={result} />
                      </InfoTip>
                    )}
                  </span>
                </th>
                {kinds.map(kind => {
                  const properties = propertiesFor(kind)
                  return (
                    <td
                      className="whitespace-nowrap py-1 pl-3 text-right font-medium tabular-nums text-leaf-ink"
                      key={kind}
                    >
                      {properties ? format(properties, i18n.language) : '–'}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-[11px] text-leaf-muted">
          {t('greenest.planTrip.metrics.scales')}
        </p>

        {result ? (
          <div className="flex flex-col gap-2 rounded-xl bg-leaf-cream p-3 text-xs">
            <WhyThisRoute focus={paused ? undefined : focus} result={result} />
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

'use client'

import { cx } from 'class-variance-authority'
import { useTranslation } from 'react-i18next'
import type { RouteComparison, RouteProperties } from '@/types/greenest'
import { ROUTE_COLORS } from './RouteComparison'

type Factor = {
  key:
    | 'bumpy_m'
    | 'danger_points'
    | 'bad_air_m'
    | 'stop_go_m'
    | 'sunny_m'
    | 'unlit_m'
    | 'bike_friendly_m'
  /** Counted in metres (else in spots). */
  metres: boolean
  /** More is better (bike paths). */
  more?: boolean
}

/** What the route avoids or gains, as in the demo's "Why this route?". */
const FACTORS: Factor[] = [
  { key: 'bumpy_m', metres: true },
  { key: 'danger_points', metres: false },
  { key: 'bad_air_m', metres: true },
  { key: 'stop_go_m', metres: true },
  { key: 'sunny_m', metres: true },
  { key: 'unlit_m', metres: true },
  { key: 'bike_friendly_m', metres: true, more: true },
]

/** Differences below this count as "about the same" (20 m, or less than one spot). */
const SAME = { metres: 20, spots: 1 }

type Tone = 'better' | 'worse' | 'same'

const TONE_CLASS: Record<Tone, string> = {
  better: 'text-[#1a7f37]',
  worse: 'text-[#b3261e]',
  same: 'text-leaf-muted',
}

/** One bar, as wide as `value` is of `max`. */
function Bar({ value, max, color }: { value: number; max: number; color: string }) {
  return (
    <div
      className="h-1 min-w-px rounded-full"
      style={{ width: `${(100 * value) / Math.max(max, 1)}%`, background: color }}
    />
  )
}

/**
 * "Why this route?": per factor, how many metres of bad streets the shortest
 * route has (grey bar) and yours has (green bar), so the rider sees what the
 * detour buys. When nothing is traded, what the route is like on the way.
 */
export default function WhyThisRoute({ result }: { result: RouteComparison }) {
  const { t, i18n } = useTranslation()
  const w = (key: string, values?: Record<string, unknown>) =>
    t(`greenest.planTrip.why.${key}`, values)
  const number = (n: number, digits = 0) =>
    n.toLocaleString(i18n.language, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    })
  const r = result.route.properties
  const s = result.shortest.properties
  const value = (p: RouteProperties, f: Factor) => p[f.key]
  const shown = FACTORS.filter(f => {
    const a = value(r, f)
    const b = value(s, f)
    return a != null && b != null && (a > 0 || b > 0)
  })
  const amount = (n: number, f: Factor) =>
    f.metres ? `${number(n)} m` : number(n)

  if (result.same_path) {
    const max = Math.max(
      ...shown.filter(f => f.metres).map(f => value(r, f) ?? 0),
      1,
    )
    return (
      <div className="flex flex-col gap-2 text-xs text-leaf-ink">
        <p className="text-sm font-semibold">{w('title')}</p>
        <p className="text-leaf-muted">
          {w('same', {
            km: number(r.length_m / 1000, 2),
            min: Math.round(r.duration_s / 60),
          })}
        </p>
        {shown.map(f => (
          <div className="flex flex-col gap-1" key={f.key}>
            <div className="flex justify-between gap-2">
              <span>{w(`rows.${f.key}`)}</span>
              <span className="font-semibold tabular-nums text-leaf-muted">
                {amount(value(r, f) ?? 0, f)}
              </span>
            </div>
            {f.metres && (
              <Bar color={ROUTE_COLORS.greenest} max={max} value={value(r, f) ?? 0} />
            )}
          </div>
        ))}
      </div>
    )
  }

  const extraM = Math.round(r.length_m - s.length_m)
  // From the rounded minutes, so it matches the table (3 min vs 4 min = 1 min slower).
  const extraMin =
    Math.round(r.duration_s / 60) - Math.round(s.duration_s / 60)
  const pct = `${result.detour_pct >= 0 ? '+' : '−'}${number(Math.abs(result.detour_pct), 1)} %`
  const time =
    extraMin > 0
      ? w('slower', { min: extraMin })
      : extraMin < 0
        ? w('quicker', { min: -extraMin })
        : w('asQuick')

  return (
    <div className="flex flex-col gap-2 text-xs text-leaf-ink">
      <p className="text-sm font-semibold">{w('title')}</p>
      <p className="text-leaf-muted">
        {w('trade', { m: number(extraM), pct, time })}
      </p>
      {shown.map(f => {
        const a = value(r, f) ?? 0
        const b = value(s, f) ?? 0
        const d = a - b
        const tone: Tone =
          Math.abs(d) < (f.metres ? SAME.metres : SAME.spots)
            ? 'same'
            : (f.more ? d > 0 : d < 0)
              ? 'better'
              : 'worse'
        const text =
          tone === 'same'
            ? w('aboutSame')
            : w(d < 0 ? (f.metres ? 'less' : 'fewer') : 'more', {
                amount: amount(Math.abs(d), f),
              })
        return (
          <div
            className="flex flex-col gap-1"
            key={f.key}
            title={w('bars', { shortest: amount(b, f), yours: amount(a, f) })}
          >
            <div className="flex justify-between gap-2">
              <span>{w(`rows.${f.key}`)}</span>
              <span
                className={cx(
                  'shrink-0 font-semibold tabular-nums',
                  TONE_CLASS[tone],
                )}
              >
                {text}
              </span>
            </div>
            <Bar color={ROUTE_COLORS.shortest} max={Math.max(a, b)} value={b} />
            <Bar color={ROUTE_COLORS.greenest} max={Math.max(a, b)} value={a} />
          </div>
        )
      })}
    </div>
  )
}

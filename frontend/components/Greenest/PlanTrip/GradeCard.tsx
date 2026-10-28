'use client'

import { useTranslation } from 'react-i18next'
import Card, { CardTitle } from '@/components/Greenest/ui/Card'
import type { GradeCollection, GradeProperties } from '@/types/greenest'

type GradeCardProps = {
  show: boolean
  onShowChange: (_show: boolean) => void
  grade: GradeCollection | null
  error: string | null
  /** False until both points are set: there is no route to grade yet. */
  hasRoute: boolean
}

const SEVERITIES: Array<GradeProperties['severity']> = [
  'flat',
  'gentle',
  'noticeable',
  'steep',
  'very_steep',
]

/** "Show hills" toggle plus climb, descent and steepest part of the route from /route/grade. */
export default function GradeCard({
  show,
  onShowChange,
  grade,
  error,
  hasRoute,
}: GradeCardProps) {
  const { t } = useTranslation()

  // The colour the backend uses for each severity that occurs on this route.
  const colors = new Map<string, string>()
  grade?.features.forEach(f =>
    colors.set(f.properties.severity, f.properties.color),
  )

  return (
    <Card className="flex flex-col gap-3">
      <CardTitle>{t('greenest.planTrip.hills.title')}</CardTitle>
      <label className="flex cursor-pointer items-center gap-2 text-sm text-leaf-ink/80">
        <input
          checked={show}
          className="h-4 w-4 accent-leaf-forest"
          onChange={e => onShowChange(e.target.checked)}
          type="checkbox"
        />
        {t('greenest.planTrip.hills.show')}
      </label>

      {show && !hasRoute && (
        <p className="text-xs text-leaf-muted">
          {t('greenest.planTrip.hills.needRoute')}
        </p>
      )}
      {show && error && (
        <p className="text-xs text-red-700" role="alert">
          {error}
        </p>
      )}

      {show && grade && (
        <>
          <dl className="grid grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded-lg bg-leaf-cream p-2">
              <dt className="text-leaf-muted">
                {t('greenest.planTrip.hills.climb')}
              </dt>
              <dd className="font-semibold tabular-nums text-leaf-ink">
                ↑ {Math.round(grade.summary.climb_m)} m
              </dd>
            </div>
            <div className="rounded-lg bg-leaf-cream p-2">
              <dt className="text-leaf-muted">
                {t('greenest.planTrip.hills.descent')}
              </dt>
              <dd className="font-semibold tabular-nums text-leaf-ink">
                ↓ {Math.round(grade.summary.descent_m)} m
              </dd>
            </div>
            <div className="rounded-lg bg-leaf-cream p-2">
              <dt className="text-leaf-muted">
                {t('greenest.planTrip.hills.steepest')}
              </dt>
              <dd className="font-semibold tabular-nums text-leaf-ink">
                {grade.summary.max_grade_pct.toFixed(1)} %
              </dd>
            </div>
          </dl>
          <ul className="flex flex-wrap gap-x-3 gap-y-1">
            {SEVERITIES.filter(s => colors.has(s)).map(severity => (
              <li
                className="flex items-center gap-1.5 text-[11px] text-leaf-muted"
                key={severity}
              >
                <span
                  aria-hidden
                  className="h-1.5 w-4 rounded-full"
                  style={{ backgroundColor: colors.get(severity) }}
                />
                {t(`greenest.planTrip.hills.severity.${severity}`)}
              </li>
            ))}
          </ul>
          <p className="text-[11px] text-leaf-muted/70">
            {t('greenest.planTrip.hills.credit')}
          </p>
        </>
      )}
    </Card>
  )
}

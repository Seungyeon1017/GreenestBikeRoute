'use client'

import { useTranslation } from 'react-i18next'
import Card, { CardTitle } from '@/components/Greenest/ui/Card'
import type { GradeCollection } from '@/types/greenest'
import { GRADE_BANDS } from '@/lib/hillColors'

type GradeCardProps = {
  show: boolean
  onShowChange: (_show: boolean) => void
  grade: GradeCollection | null
  error: string | null
  /** False until both points are set: there is no route to grade yet. */
  hasRoute: boolean
}

/** "Show hills" toggle plus climb, descent and steepest part of the route from /route/grade. */
export default function GradeCard({
  show,
  onShowChange,
  grade,
  error,
  hasRoute,
}: GradeCardProps) {
  const { t } = useTranslation()

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
          <div className="flex flex-col gap-1 text-[11px] text-leaf-muted">
            <div className="flex justify-between">
              <span>{t('greenest.planTrip.hills.legend.down')}</span>
              <span>{t('greenest.planTrip.hills.legend.up')}</span>
            </div>
            {/* One equal swatch per band, exactly the colours on the map. */}
            <div aria-hidden className="flex h-2 overflow-hidden rounded-full">
              {GRADE_BANDS.map(({ from, color }) => (
                <span
                  className="flex-1"
                  key={from}
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
            {/* The grade where one band ends and the next starts, under that border. */}
            <div aria-hidden className="relative h-3.5 text-[10px] tabular-nums">
              {GRADE_BANDS.slice(1).map(({ from }, i) => (
                <span
                  className="absolute -translate-x-1/2"
                  key={from}
                  style={{ left: `${(100 * (i + 1)) / GRADE_BANDS.length}%` }}
                >
                  {from}
                </span>
              ))}
            </div>
            <p>{t('greenest.planTrip.hills.legend.hint')}</p>
          </div>
          <p className="text-[11px] text-leaf-muted/70">
            {t('greenest.planTrip.hills.credit')}
          </p>
        </>
      )}
    </Card>
  )
}

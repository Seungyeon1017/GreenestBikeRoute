'use client'

import { useTranslation } from 'react-i18next'
import InfoTip from '@/components/Greenest/ui/InfoTip'
import type { GradeCollection } from '@/types/greenest'
import { GRADE_BANDS } from '@/lib/hillColors'

type HillsLegendProps = {
  grade: GradeCollection | null
  error: string | null
  /** False until both points are set: there is no route to grade yet. */
  hasRoute: boolean
}

/**
 * On the map while the Hills layer is on: climb, descent and steepest part of
 * the route from /route/grade, and the colour of each grade band.
 */
export default function HillsLegend({
  grade,
  error,
  hasRoute,
}: HillsLegendProps) {
  const { t } = useTranslation()

  return (
    <div className="pointer-events-auto relative flex w-64 flex-col gap-2 rounded-2xl border border-leaf-sand bg-white p-3 text-xs text-leaf-ink shadow-soft">
      <div className="flex items-center gap-1.5">
        <strong className="text-sm text-leaf-forest">
          {t('greenest.planTrip.hills.title')}
        </strong>
        <InfoTip
          above
          label={t('greenest.planTrip.info.about', {
            name: t('greenest.planTrip.hills.title'),
          })}
        >
          {t('greenest.planTrip.hills.legend.hint')}
          <span className="mt-1 block text-leaf-muted">
            {t('greenest.planTrip.hills.credit')}
          </span>
        </InfoTip>
      </div>

      {!hasRoute && (
        <p className="text-leaf-muted">
          {t('greenest.planTrip.hills.needRoute')}
        </p>
      )}
      {error && (
        <p className="text-red-700" role="alert">
          {error}
        </p>
      )}

      {grade && (
        <dl className="grid grid-cols-3 gap-1.5 text-center">
          <div className="rounded-lg bg-leaf-cream p-1.5">
            <dt className="text-leaf-muted">
              {t('greenest.planTrip.hills.climb')}
            </dt>
            <dd className="font-semibold tabular-nums">
              ↑ {Math.round(grade.summary.climb_m)} m
            </dd>
          </div>
          <div className="rounded-lg bg-leaf-cream p-1.5">
            <dt className="text-leaf-muted">
              {t('greenest.planTrip.hills.descent')}
            </dt>
            <dd className="font-semibold tabular-nums">
              ↓ {Math.round(grade.summary.descent_m)} m
            </dd>
          </div>
          <div className="rounded-lg bg-leaf-cream p-1.5">
            <dt className="text-leaf-muted">
              {t('greenest.planTrip.hills.steepest')}
            </dt>
            <dd className="font-semibold tabular-nums">
              {grade.summary.max_grade_pct.toFixed(1)} %
            </dd>
          </div>
        </dl>
      )}

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
      </div>
    </div>
  )
}

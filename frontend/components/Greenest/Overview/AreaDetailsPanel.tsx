'use client'

import { cx } from 'class-variance-authority'
import { ChevronRight, MousePointerClick, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import AvailabilityBadge from '@/components/Greenest/ui/AvailabilityBadge'
import Card, { CardTitle } from '@/components/Greenest/ui/Card'
import type { AreaProperties } from '@/types/greenest'

type AreaDetailsPanelProps = {
  area: AreaProperties | null
  open: boolean
  onToggle: () => void
  onClear: () => void
}

type Indicator = {
  key: string
  value: string | null
  unit: string
  basis: string
  source: string
}

function Row({ indicator }: { indicator: Indicator }) {
  const { t } = useTranslation()
  const measured = indicator.value !== null
  return (
    <div className="flex flex-col gap-1 rounded-xl border border-leaf-sand/70 p-3">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium text-leaf-ink">
          {t(`greenest.overview.indicators.${indicator.key}`)}
        </span>
        <AvailabilityBadge
          availability={measured ? 'measured' : 'unavailable'}
        />
      </div>
      {measured ? (
        <p className="font-display text-xl font-semibold tabular-nums text-leaf-ink">
          {indicator.value}
          <span className="ml-1 text-xs font-normal text-leaf-muted">
            {indicator.unit}
          </span>
        </p>
      ) : (
        <p className="text-sm text-leaf-muted/70">
          {t('greenest.overview.noMeasurement')}
        </p>
      )}
      {indicator.basis && (
        <p className="text-[11px] text-leaf-muted">{indicator.basis}</p>
      )}
      {indicator.source && (
        <p className="text-[11px] text-leaf-muted/70">
          {t('greenest.overview.source')}: {indicator.source}
        </p>
      )}
    </div>
  )
}

/** Right-hand panel with the measured indicators of the clicked area. */
export default function AreaDetailsPanel({
  area,
  open,
  onToggle,
  onClear,
}: AreaDetailsPanelProps) {
  const { t } = useTranslation()

  const indicators: Indicator[] = area
    ? [
        {
          key: 'pmRisk',
          value: area.pm_risk?.toFixed(2) ?? null,
          unit: t('greenest.overview.units.index'),
          basis: t('greenest.overview.basis.points', {
            count: area.pm_points,
          }),
          source: 'ATRAI senseBox:bike (danger_zones_PM)',
        },
        {
          key: 'roughness',
          value: area.roughness?.toFixed(1) ?? null,
          unit: '/ 100',
          basis: t('greenest.overview.basis.length', {
            km: (area.roughness_measured_m / 1000).toFixed(1),
          }),
          source: 'ATRAI senseBox:bike (bumpy_roads)',
        },
        {
          key: 'overtakingRisk',
          value: area.overtaking_risk?.toFixed(2) ?? null,
          unit: t('greenest.overview.units.index'),
          basis: t('greenest.overview.basis.manoeuvres', {
            count: area.overtaking_points,
          }),
          source: 'ATRAI senseBox:bike (danger_zones)',
        },
        { key: 'noise', value: null, unit: '', basis: '', source: '' },
        { key: 'greenery', value: null, unit: '', basis: '', source: '' },
      ]
    : []

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <button
          aria-expanded={open}
          className="flex flex-1 items-center gap-2 text-left"
          onClick={onToggle}
          type="button"
        >
          <ChevronRight
            aria-hidden
            className={cx(
              'h-4 w-4 text-leaf-muted/70 transition-transform',
              open && 'rotate-90',
            )}
          />
          <CardTitle>{t('greenest.overview.detailsTitle')}</CardTitle>
        </button>
        {area && (
          <button
            aria-label={t('greenest.overview.clearSelection')}
            className="rounded-lg p-1 text-leaf-muted/70 hover:bg-leaf-sand/50 hover:text-leaf-ink/80"
            onClick={onClear}
            type="button"
          >
            <X aria-hidden className="h-4 w-4" />
          </button>
        )}
      </div>
      {open &&
        (area ? (
          <div className="flex flex-col gap-2">
            <p className="text-xs text-leaf-muted">
              {t('greenest.overview.areaNote')}
            </p>
            {indicators.map(indicator => (
              <Row indicator={indicator} key={indicator.key} />
            ))}
            <p className="text-[11px] text-leaf-muted/70">
              {t('greenest.overview.indexNote')}
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 rounded-xl bg-leaf-cream px-4 py-8 text-center">
            <MousePointerClick
              aria-hidden
              className="h-6 w-6 text-leaf-muted/70"
            />
            <p className="text-sm text-leaf-muted">
              {t('greenest.overview.detailsEmpty')}
            </p>
          </div>
        ))}
    </Card>
  )
}

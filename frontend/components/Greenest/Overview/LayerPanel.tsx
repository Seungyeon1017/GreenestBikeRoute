'use client'

import { cx } from 'class-variance-authority'
import { useTranslation } from 'react-i18next'
import AvailabilityBadge from '@/components/Greenest/ui/AvailabilityBadge'
import Card, { CardTitle } from '@/components/Greenest/ui/Card'
import type { OverlayState } from '@/hooks/useOverlays'
import type { EnvironmentLayer, EnvironmentLayerId } from '@/types/greenest'

type LayerPanelProps = {
  layers: EnvironmentLayer[]
  enabled: Set<EnvironmentLayerId>
  onToggle: (_id: EnvironmentLayerId) => void
  /** Download state of the backend layers, to show "loading" or an error. */
  overlays: OverlayState
}

export default function LayerPanel({
  layers,
  enabled,
  onToggle,
  overlays,
}: LayerPanelProps) {
  const { t } = useTranslation()

  return (
    // On wide screens the title stays put and only the list scrolls, inside the card.
    <Card className="flex flex-col gap-3 lg:max-h-full lg:min-h-0">
      <CardTitle>{t('greenest.overview.layersTitle')}</CardTitle>
      <ul className="flex flex-col gap-2 lg:-mr-3 lg:min-h-0 lg:overflow-y-auto lg:overscroll-contain lg:pr-3">
        {layers.map(layer => {
          const inputId = `layer-${layer.id}`
          const available = layer.availability !== 'unavailable'
          const on = available && enabled.has(layer.id)
          const overlay = overlays[layer.id]
          return (
            <li
              className={cx(
                'rounded-xl border p-3',
                on
                  ? 'border-leaf-sage/60 bg-leaf-mint/60'
                  : 'border-leaf-sand/70',
              )}
              key={layer.id}
            >
              <div className="flex items-start gap-3">
                <input
                  checked={on}
                  className="mt-0.5 h-4 w-4 accent-leaf-forest disabled:opacity-40"
                  disabled={!available}
                  id={inputId}
                  onChange={() => onToggle(layer.id)}
                  type="checkbox"
                />
                <div className="min-w-0 flex-1 space-y-1.5">
                  {/* Badge under the title: long German names leave no room beside it. */}
                  <div className="flex flex-col items-start gap-1">
                    <label
                      className={cx(
                        'block text-sm font-medium',
                        available
                          ? 'cursor-pointer text-leaf-ink'
                          : 'text-leaf-muted/70',
                      )}
                      htmlFor={inputId}
                    >
                      {t(`greenest.layers.${layer.id}.label`)}
                    </label>
                    <AvailabilityBadge availability={layer.availability} />
                  </div>
                  <p className="text-xs text-leaf-muted">
                    {t(`greenest.layers.${layer.id}.description`)}
                  </p>
                  {on && overlay?.status === 'loading' && (
                    <p className="text-[11px] text-leaf-muted" role="status">
                      {t('greenest.overview.loadingLayer')}
                    </p>
                  )}
                  {overlay?.status === 'error' && (
                    <p className="text-[11px] text-red-700" role="alert">
                      {t('greenest.overview.layerError')} {overlay.message}
                    </p>
                  )}
                  {on && layer.legend.length > 0 && (
                    <ul className="flex flex-col gap-1 pt-1">
                      {layer.legend.map(({ color, label }) => (
                        <li
                          className="flex items-center gap-2 text-[11px] text-leaf-muted"
                          key={label}
                        >
                          <span
                            aria-hidden
                            className="h-2 w-4 rounded-sm"
                            style={{ backgroundColor: color }}
                          />
                          {label}
                        </li>
                      ))}
                    </ul>
                  )}
                  {on && (
                    <p className="text-[11px] text-leaf-muted/70">
                      {[layer.unit, layer.source].filter(Boolean).join(' · ')}
                    </p>
                  )}
                </div>
              </div>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

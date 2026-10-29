'use client'

import { cx } from 'class-variance-authority'
import { Construction, Layers, Mountain, TrainFront } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import ReportsLegend from './ReportsLegend'

type MapLayersProps = {
  showHills: boolean
  onShowHillsChange: (_show: boolean) => void
  showReports: boolean
  onShowReportsChange: (_show: boolean) => void
  showStations: boolean
  onShowStationsChange: (_show: boolean) => void
  /** Legends and notices of the layers that are on, in a row beside the button; hidden while the panel is open. */
  children?: ReactNode
}

function LayerTile({
  icon: Icon,
  label,
  hint,
  on,
  onToggle,
}: {
  icon: LucideIcon
  label: string
  hint: string
  on: boolean
  onToggle: () => void
}) {
  return (
    <button
      aria-pressed={on}
      className={cx(
        'flex w-20 flex-col items-center gap-1 rounded-xl p-1 text-center text-[11px] leading-tight hover:bg-leaf-cream',
        on ? 'font-semibold text-leaf-forest' : 'text-leaf-ink/80',
      )}
      onClick={onToggle}
      title={hint}
      type="button"
    >
      <span
        className={cx(
          'flex h-12 w-12 items-center justify-center rounded-xl border-2',
          on ? 'border-leaf-forest bg-leaf-cream' : 'border-leaf-sand bg-white',
        )}
      >
        <Icon aria-hidden className="h-5 w-5" />
      </span>
      {label}
    </button>
  )
}

/**
 * "Layers" at the bottom left of the map, as in Google Maps: a button that
 * opens tiles to switch hills, riders' reports and stations on and off. The legend or
 * question of a layer that is on sits beside the button.
 */
export default function MapLayers({
  showHills,
  onShowHillsChange,
  showReports,
  onShowReportsChange,
  showStations,
  onShowStationsChange,
  children,
}: MapLayersProps) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // A click elsewhere or Esc closes the panel.
  useEffect(() => {
    if (!open) {
      return
    }
    const close = (e: PointerEvent | KeyboardEvent) => {
      if (
        e instanceof KeyboardEvent
          ? e.key === 'Escape'
          : !ref.current?.contains(e.target as Node)
      ) {
        setOpen(false)
      }
    }
    document.addEventListener('pointerdown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('pointerdown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  return (
    // Bottom left: MapLibre's attribution takes the bottom right corner.
    <div className="pointer-events-none absolute inset-x-2.5 bottom-2.5 z-10 flex flex-wrap-reverse items-end gap-2 pr-8">
      <div className="pointer-events-auto relative" ref={ref}>
        {open && (
          <div className="absolute bottom-full left-0 mb-2 flex w-72 flex-col gap-3 rounded-2xl border border-leaf-sand bg-white p-3 shadow-soft">
            <strong className="text-sm text-leaf-forest">
              {t('greenest.planTrip.layers.title')}
            </strong>
            <div className="flex gap-1">
              <LayerTile
                hint={t('greenest.planTrip.hills.show')}
                icon={Mountain}
                label={t('greenest.planTrip.hills.title')}
                on={showHills}
                onToggle={() => onShowHillsChange(!showHills)}
              />
              <LayerTile
                hint={t('greenest.planTrip.reports.show')}
                icon={Construction}
                label={t('greenest.planTrip.reports.title')}
                on={showReports}
                onToggle={() => onShowReportsChange(!showReports)}
              />
              <LayerTile
                hint={t('greenest.planTrip.stations.show')}
                icon={TrainFront}
                label={t('greenest.planTrip.stations.title')}
                on={showStations}
                onToggle={() => onShowStationsChange(!showStations)}
              />
            </div>
            {showReports && <ReportsLegend />}
          </div>
        )}
        <button
          aria-expanded={open}
          className="flex h-16 w-16 flex-col items-center justify-center gap-1 rounded-2xl border border-leaf-sand bg-white text-[11px] font-semibold text-leaf-forest shadow-soft hover:bg-leaf-cream"
          onClick={() => setOpen(o => !o)}
          type="button"
        >
          <Layers aria-hidden className="h-5 w-5" />
          {t('greenest.planTrip.layers.button')}
        </button>
      </div>
      {/* Hidden while the panel is open: on phones they wrap above the button, where the panel opens. */}
      {!open && children}
    </div>
  )
}

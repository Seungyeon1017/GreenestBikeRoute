'use client'

import { AlertTriangle } from 'lucide-react'
import { useCallback, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Spinner } from '@/components/Elements/Spinner'
import PageIntro from '@/components/Greenest/ui/PageIntro'
import useOverlays from '@/hooks/useOverlays'
import useOverviewData from '@/hooks/useOverviewData'
import type { EnvironmentLayerId } from '@/types/greenest'
import AreaDetailsPanel from './AreaDetailsPanel'
import LayerPanel from './LayerPanel'
import { ENVIRONMENT_LAYERS } from './layers'
import OverviewMap from './OverviewMap'

export default function OverviewView() {
  const { t } = useTranslation()
  const overview = useOverviewData()
  const data = overview.status === 'ready' ? overview.data : null

  const [enabled, setEnabled] = useState<Set<EnvironmentLayerId>>(
    () =>
      new Set<EnvironmentLayerId>(['air-quality', 'cycling-infrastructure']),
  )
  // Backend layers, each downloaded the first time it's switched on.
  const overlays = useOverlays(ENVIRONMENT_LAYERS, enabled)
  const [detailsOpen, setDetailsOpen] = useState(true)
  const [selectedCell, setSelectedCell] = useState<string | null>(null)

  const selectedArea = useMemo(
    () =>
      data?.areas.features.find(f => f.properties.cell === selectedCell)
        ?.properties ?? null,
    [data, selectedCell],
  )

  const selectCell = useCallback((cell: string | null) => {
    setSelectedCell(cell)
    setDetailsOpen(true)
  }, [])

  const toggleLayer = (id: EnvironmentLayerId) =>
    setEnabled(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })

  return (
    <div className="mx-auto flex w-full max-w-[1920px] flex-1 flex-col gap-4 px-4 py-4 md:px-8">
      <PageIntro
        eyebrow={t('greenest.overview.eyebrow')}
        subtitle={t('greenest.overview.subtitle')}
        title={t('greenest.overview.title')}
      />
      {/* On wide screens the row has a fixed height and the side panels scroll inside it,
          so a panel growing when a layer is toggled never moves or resizes the map. */}
      <div className="grid flex-1 grid-cols-1 gap-4 lg:h-[calc(100vh-7rem)] lg:flex-none lg:grid-cols-[18rem_minmax(0,1fr)_20rem] lg:grid-rows-[minmax(0,1fr)]">
        <aside className="order-2 lg:order-1 lg:overflow-y-auto">
          <LayerPanel
            enabled={enabled}
            layers={ENVIRONMENT_LAYERS}
            onToggle={toggleLayer}
            overlays={overlays}
          />
        </aside>
        <section className="relative order-1 h-[60vh] min-h-[420px] overflow-hidden rounded-3xl border border-leaf-sand shadow-soft lg:order-2 lg:h-auto lg:min-h-0">
          <OverviewMap
            ariaLabel={t('greenest.overview.mapLabel')}
            data={data}
            enabled={enabled}
            onSelectCell={selectCell}
            overlays={overlays}
            selectedCell={selectedCell}
          />
          {overview.status === 'loading' && (
            <div className="absolute left-3 top-3 flex items-center gap-2 rounded-lg bg-white/90 px-3 py-1.5 text-xs text-leaf-muted shadow-sm">
              <Spinner size="sm" />
              {t('greenest.overview.loadingData')}
            </div>
          )}
          {overview.status === 'error' && (
            <div
              className="absolute inset-x-3 top-3 flex items-start gap-2 rounded-lg border border-red-200 bg-white/95 p-3 text-xs text-red-700 shadow-sm"
              role="alert"
            >
              <AlertTriangle aria-hidden className="h-4 w-4 shrink-0" />
              {overview.message}
            </div>
          )}
        </section>
        <aside className="order-3 lg:overflow-y-auto">
          <AreaDetailsPanel
            area={selectedArea}
            onClear={() => setSelectedCell(null)}
            onToggle={() => setDetailsOpen(open => !open)}
            open={detailsOpen}
          />
        </aside>
      </div>
    </div>
  )
}

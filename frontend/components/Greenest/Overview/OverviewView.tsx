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

const STREET_LAYERS = new Set(
  ENVIRONMENT_LAYERS.filter(layer => layer.colorsStreets).map(
    layer => layer.id,
  ),
)

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
        return next
      }
      // Street layers would paint over each other, so switching one on
      // switches the others off. Areas and points stack on top.
      if (STREET_LAYERS.has(id)) {
        STREET_LAYERS.forEach(other => next.delete(other))
      }
      next.add(id)
      return next
    })

  return (
    // data-workspace: on wide screens the page fills the window and doesn't
    // scroll; the map's row takes the remaining height and the side panels
    // scroll inside it, so a panel growing never moves or resizes the map.
    <div
      className="mx-auto flex min-h-0 w-full max-w-[1920px] flex-1 flex-col gap-4 px-4 py-4 md:px-8"
      data-workspace
    >
      <PageIntro
        subtitle={t('greenest.overview.subtitle')}
        title={t('greenest.overview.title')}
      />
      <div className="grid flex-1 grid-cols-1 gap-4 lg:min-h-0 lg:grid-cols-[18rem_minmax(0,1fr)_20rem] lg:grid-rows-[minmax(0,1fr)]">
        {/* On phones the area details come right under the map, the layer list after them. */}
        <aside className="order-3 lg:order-1 lg:flex lg:min-h-0 lg:flex-col">
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
        <aside className="order-2 lg:order-3 lg:flex lg:min-h-0 lg:flex-col">
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

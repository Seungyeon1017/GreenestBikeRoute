'use client'

import type { Map as MapLibreMap } from 'maplibre-gl'
import { useEffect, useState } from 'react'
import BaseMap from '@/components/Greenest/Map'
import type { OverlayState } from '@/hooks/useOverlays'
import type { OverviewData } from '@/services/mapData'
import type { EnvironmentLayerId } from '@/types/greenest'
import { OVERLAY_STYLES, PM_RISK_STEPS, ROUGHNESS_STEPS } from './layers'

type OverviewMapProps = {
  ariaLabel: string
  data: OverviewData | null
  /** Backend overlays loaded so far (see hooks/useOverlays.ts). */
  overlays: OverlayState
  enabled: Set<EnvironmentLayerId>
  selectedCell: string | null
  onSelectCell: (_cell: string | null) => void
}

/** MapLibre layer ids drawn for each environmental layer. */
const MAP_LAYERS: Partial<Record<EnvironmentLayerId, string[]>> = {
  'air-quality': ['areas-pm'],
  'surface-roughness': ['roughness-lines'],
}

/** MapLibre `step` expression from legend steps with an upper bound per class. */
function stepColor(
  property: string,
  steps: Array<{ color: string; max: number }>,
) {
  const expression: unknown[] = ['step', ['get', property], steps[0].color]
  steps.slice(1).forEach((step, i) => {
    expression.push(steps[i].max, step.color)
  })
  return expression as never
}

function addLayers(map: MapLibreMap, data: OverviewData) {
  map.addSource('areas', { type: 'geojson', data: data.areas })
  map.addSource('roughness', { type: 'geojson', data: data.roughness })

  map.addLayer({
    id: 'areas-pm',
    type: 'fill',
    source: 'areas',
    filter: ['!=', ['get', 'pm_risk'], null],
    paint: {
      'fill-color': stepColor('pm_risk', PM_RISK_STEPS),
      'fill-opacity': 0.4,
      'fill-outline-color': 'rgba(255,255,255,0.6)',
    },
  })
  map.addLayer({
    id: 'roughness-lines',
    type: 'line',
    source: 'roughness',
    paint: {
      'line-color': stepColor('roughness', ROUGHNESS_STEPS),
      'line-width': ['interpolate', ['linear'], ['zoom'], 12, 1.5, 16, 4],
      'line-opacity': 0.85,
    },
  })
  // Invisible fill so every area can be clicked, whichever layers are on.
  map.addLayer({
    id: 'areas-hit',
    type: 'fill',
    source: 'areas',
    paint: { 'fill-color': '#000', 'fill-opacity': 0 },
  })
  map.addLayer({
    id: 'areas-selected',
    type: 'line',
    source: 'areas',
    filter: ['==', ['get', 'cell'], ''],
    paint: { 'line-color': '#065f46', 'line-width': 3 },
  })
}

export default function OverviewMap({
  ariaLabel,
  data,
  overlays,
  enabled,
  selectedCell,
  onSelectCell,
}: OverviewMapProps) {
  const [map, setMap] = useState<MapLibreMap | null>(null)
  const [layersAdded, setLayersAdded] = useState(false)

  // Add sources and layers once both the map and the data are ready.
  useEffect(() => {
    if (!map || !data || layersAdded) {
      return
    }
    addLayers(map, data)
    map.on('click', 'areas-hit', event => {
      onSelectCell(String(event.features?.[0]?.properties?.cell ?? '') || null)
    })
    map.on('mouseenter', 'areas-hit', () => {
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', 'areas-hit', () => {
      map.getCanvas().style.cursor = ''
    })
    setLayersAdded(true)
  }, [map, data, layersAdded, onSelectCell])

  useEffect(() => {
    if (!map || !layersAdded) {
      return
    }
    for (const [layerId, mapLayerIds] of Object.entries(MAP_LAYERS)) {
      const visibility = enabled.has(layerId as EnvironmentLayerId)
        ? 'visible'
        : 'none'
      for (const id of mapLayerIds) {
        map.setLayoutProperty(id, 'visibility', visibility)
      }
    }
  }, [map, layersAdded, enabled])

  // Backend overlays: add each one once its data has arrived, then show or hide it.
  useEffect(() => {
    if (!map) {
      return
    }
    for (const [key, overlay] of Object.entries(overlays)) {
      const id = key as EnvironmentLayerId
      const style = OVERLAY_STYLES[id]
      if (!style || overlay?.status !== 'ready') {
        continue
      }
      if (!map.getSource(id)) {
        map.addSource(id, { type: 'geojson', data: overlay.data })
        // Below the invisible click layer, so areas stay clickable and the selection stays on top.
        const before = map.getLayer('areas-hit') ? 'areas-hit' : undefined
        map.addLayer({ id, source: id, ...style } as never, before)
      }
      map.setLayoutProperty(
        id,
        'visibility',
        enabled.has(id) ? 'visible' : 'none',
      )
    }
  }, [map, overlays, enabled])

  useEffect(() => {
    if (map && layersAdded) {
      map.setFilter('areas-selected', [
        '==',
        ['get', 'cell'],
        selectedCell ?? '',
      ])
    }
  }, [map, layersAdded, selectedCell])

  return <BaseMap ariaLabel={ariaLabel} onLoad={setMap} zoom={12.5} />
}

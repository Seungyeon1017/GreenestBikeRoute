import type { FeatureCollection } from 'geojson'
import { useEffect, useRef, useState } from 'react'
import { fetchOverlay } from '@/services/greenestApi'
import type { EnvironmentLayer, EnvironmentLayerId } from '@/types/greenest'

export type OverlayStatus =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: FeatureCollection }

export type OverlayState = Partial<Record<EnvironmentLayerId, OverlayStatus>>

/** Hour of the /shade time slot shown on the map (the backend has 9, 12, 15 and 18 h of 21 July). */
export const SHADE_HOUR = 15

/**
 * /shade returns a list of values per street, one per time slot. MapLibre can't
 * read lists from GeoJSON properties, so keep only the slot closest to SHADE_HOUR.
 */
function pickShadeSlot(
  data: FeatureCollection & { slots?: string[] },
): FeatureCollection {
  const hours = (data.slots ?? []).map(slot => Number(slot.slice(11, 13)))
  let index = 0
  hours.forEach((hour, i) => {
    if (Math.abs(hour - SHADE_HOUR) < Math.abs(hours[index] - SHADE_HOUR)) {
      index = i
    }
  })
  return {
    type: 'FeatureCollection',
    features: data.features.map(feature => ({
      ...feature,
      properties: { shade: feature.properties?.shade?.[index] ?? null },
    })),
  }
}

/**
 * Loads each backend overlay the first time its layer is switched on, then
 * keeps it. Layers that are never switched on are never downloaded.
 */
export default function useOverlays(
  layers: EnvironmentLayer[],
  enabled: Set<EnvironmentLayerId>,
): OverlayState {
  const [state, setState] = useState<OverlayState>({})
  // Which overlays were already requested, so a toggle off and on doesn't fetch again.
  const requested = useRef(new Set<EnvironmentLayerId>())

  useEffect(() => {
    for (const layer of layers) {
      if (
        !layer.overlay ||
        !enabled.has(layer.id) ||
        requested.current.has(layer.id)
      ) {
        continue
      }
      const { id, overlay } = layer
      requested.current.add(id)
      setState(prev => ({ ...prev, [id]: { status: 'loading' } }))
      fetchOverlay(overlay)
        .then(data => {
          const ready = overlay === 'shade' ? pickShadeSlot(data) : data
          setState(prev => ({
            ...prev,
            [id]: { status: 'ready', data: ready },
          }))
        })
        .catch((error: Error) => {
          // Allow a retry by switching the layer off and on again.
          requested.current.delete(id)
          setState(prev => ({
            ...prev,
            [id]: { status: 'error', message: error.message },
          }))
        })
    }
  }, [layers, enabled])

  return state
}
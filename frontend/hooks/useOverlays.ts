import type { FeatureCollection } from 'geojson'
import { useEffect, useSyncExternalStore } from 'react'
import { fetchOverlay, fetchStreetNames } from '@/services/greenestApi'
import type { EnvironmentLayer, EnvironmentLayerId } from '@/types/greenest'

export type OverlayStatus =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  // named: false for a street layer the backend hasn't named yet (its first ~30 s), named again once it has.
  | { status: 'ready'; data: FeatureCollection; named: boolean }

export type OverlayState = Partial<Record<EnvironmentLayerId, OverlayStatus>>

/** Hour of the /shade time slot shown on the map (the backend has 9, 12, 15 and 18 h of 21 July). */
export const SHADE_HOUR = 15

/** How often to ask whether the street names are ready, while some layer has none. */
const NAMES_POLL_MS = 3000

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
      properties: {
        ...feature.properties,
        shade: feature.properties?.shade?.[index] ?? null,
      },
    })),
  }
}

// The overlays are the same for everyone and MBs each, so they are kept for
// the whole visit: leaving the Overview and coming back doesn't fetch again.
let overlays: OverlayState = {}
const listeners = new Set<() => void>()
const EMPTY: OverlayState = {}

function update(id: EnvironmentLayerId, status: OverlayStatus) {
  overlays = { ...overlays, [id]: status }
  listeners.forEach(listener => listener())
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

async function download(layer: EnvironmentLayer) {
  const data = (await fetchOverlay(layer.overlay!)) as FeatureCollection & {
    named?: boolean
  }
  return {
    status: 'ready' as const,
    data: layer.overlay === 'shade' ? pickShadeSlot(data) : data,
    named: data.named !== false,
  }
}

/** Downloads `layer` unless it is loading or loaded; one that failed only when `retry`. */
async function load(layer: EnvironmentLayer, retry: boolean) {
  const current = overlays[layer.id]?.status
  if (
    !layer.overlay ||
    current === 'loading' ||
    current === 'ready' ||
    (current === 'error' && !retry)
  ) {
    return
  }
  update(layer.id, { status: 'loading' })
  try {
    const ready = await download(layer)
    update(layer.id, ready)
    if (!ready.named) {
      waitForNames()
    }
  } catch (error) {
    // Retried when the layer is switched on again.
    update(layer.id, { status: 'error', message: (error as Error).message })
  }
}

let waiting = false
let known: EnvironmentLayer[] = []

/**
 * Right after the backend starts, its street layers come without street names.
 * Ask until it has them, then fetch those layers again, keeping the unnamed
 * ones on the map meanwhile.
 */
function waitForNames() {
  if (waiting) {
    return
  }
  waiting = true
  const poll = async () => {
    const ready = await fetchStreetNames()
      .then(names => names.ready)
      .catch(() => false) // the backend restarting: ask again
    if (!ready) {
      setTimeout(poll, NAMES_POLL_MS)
      return
    }
    waiting = false
    for (const layer of known) {
      const current = overlays[layer.id]
      if (current?.status === 'ready' && !current.named) {
        download(layer)
          .then(named => update(layer.id, named))
          .catch(() => waitForNames()) // keep the unnamed layer, try again
      }
    }
  }
  setTimeout(poll, NAMES_POLL_MS)
}

/**
 * Loads every backend overlay as soon as the Overview opens, the layers that
 * are switched on first and then the rest in the background, so switching one
 * on later shows it at once.
 */
export default function useOverlays(
  layers: EnvironmentLayer[],
  enabled: Set<EnvironmentLayerId>,
): OverlayState {
  const state = useSyncExternalStore(
    subscribe,
    () => overlays,
    () => EMPTY,
  )

  useEffect(() => {
    known = layers
    const on = layers.filter(layer => enabled.has(layer.id))
    // The rest only after those, so the backend builds the shown ones first.
    Promise.allSettled(on.map(layer => load(layer, true))).then(() =>
      layers
        .filter(layer => !enabled.has(layer.id))
        .forEach(layer => load(layer, false)),
    )
  }, [layers, enabled])

  return state
}

'use client'

import type { Feature, FeatureCollection } from 'geojson'
import maplibregl, { type Map as MapLibreMap } from 'maplibre-gl'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import BaseMap from '@/components/Greenest/Map'
import { segmentLabels } from '@/components/Greenest/PlanTrip/routeSegments'
import { type OverlayState, SHADE_HOUR } from '@/hooks/useOverlays'
import type { OverviewData } from '@/services/mapData'
import type { EnvironmentLayerId } from '@/types/greenest'
import { OVERLAY_STYLES, PM_RISK_STEPS, stepColor } from './layers'
import { type StreetLabels, streetPopup } from './streetPopup'

/** What the map picks: a grid cell, or a street of the street layer that is switched on. */
export type PickMode = 'area' | 'street'

type OverviewMapProps = {
  ariaLabel: string
  data: OverviewData | null
  /** Backend overlays loaded so far (see hooks/useOverlays.ts). */
  overlays: OverlayState
  enabled: Set<EnvironmentLayerId>
  selectedCell: string | null
  onSelectCell: (_cell: string | null) => void
  pickMode: PickMode
}

/** MapLibre layer ids drawn for each environmental layer. */
const MAP_LAYERS: Partial<Record<EnvironmentLayerId, string[]>> = {
  'air-quality': ['areas-pm'],
}

/** Street layers that can be pointed at: the line layers, each with an invisible, wider hit line. */
const STREET_IDS = (Object.keys(OVERLAY_STYLES) as EnvironmentLayerId[]).filter(
  id => OVERLAY_STYLES[id]?.type === 'line',
)
const HIT_PREFIX = 'street-hit-'
const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] }

/** The invisible, wide line that hovers and clicks on a street layer hit; shown by the pick-mode effect. */
function addStreetHit(
  map: MapLibreMap,
  id: EnvironmentLayerId,
  source: string,
) {
  map.addLayer({
    id: HIT_PREFIX + id,
    type: 'line',
    source,
    layout: { 'line-cap': 'round', visibility: 'none' },
    paint: { 'line-color': 'rgba(0, 0, 0, 0)', 'line-width': 14 },
  })
}

function addLayers(map: MapLibreMap, data: OverviewData) {
  map.addSource('areas', { type: 'geojson', data: data.areas })

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
  // The pointed-at street, outlined like a stretch on Plan a trip.
  map.addSource('street-active', { type: 'geojson', data: EMPTY })
  const round = { 'line-cap': 'round', 'line-join': 'round' } as const
  map.addLayer({
    id: 'street-active-casing',
    type: 'line',
    source: 'street-active',
    layout: round,
    paint: { 'line-color': '#ffffff', 'line-width': 9 },
  })
  map.addLayer({
    id: 'street-active',
    type: 'line',
    source: 'street-active',
    layout: round,
    paint: { 'line-color': '#1f3d2b', 'line-width': 5 },
  })
}

/** Outlines the pointed-at street, or clears it. */
function markStreet(map: MapLibreMap, feature: Feature | null) {
  map
    .getSource<maplibregl.GeoJSONSource>('street-active')
    ?.setData(feature ?? EMPTY)
}

export default function OverviewMap({
  ariaLabel,
  data,
  overlays,
  enabled,
  selectedCell,
  onSelectCell,
  pickMode,
}: OverviewMapProps) {
  const { t, i18n } = useTranslation()
  const [map, setMap] = useState<MapLibreMap | null>(null)
  const [layersAdded, setLayersAdded] = useState(false)

  // Read by the map's event handlers, which are bound once.
  const pickModeRef = useRef(pickMode)
  pickModeRef.current = pickMode
  const overlaysRef = useRef(overlays)
  overlaysRef.current = overlays
  const labels: StreetLabels = {
    ...segmentLabels(t, i18n.language),
    layer: id => t(`greenest.layers.${id}.label`),
    shadeNote: t('greenest.layers.shade.unit', { hour: SHADE_HOUR }),
    ridden: t('greenest.overview.street.ridden'),
    lightsPer100m: t('greenest.overview.street.lightsPer100m'),
    nameLoading: t('greenest.overview.street.nameLoading'),
  }
  const labelsRef = useRef(labels)
  labelsRef.current = labels
  // The street popup: follows the mouse while hovering a street, stays put once clicked.
  const streetRef = useRef<{
    popup: maplibregl.Popup
    pinned: boolean
    layer: EnvironmentLayerId
    key: string
  } | null>(null)

  // Opens the popup again at a point, for the same street in new data (set with the map's handlers).
  const reshowStreetRef = useRef<
    ((_at: maplibregl.LngLat, _pinned: boolean) => void) | null
  >(null)
  // The data each overlay's source has, to replace it when the named one arrives.
  const sourceData = useRef(new Map<EnvironmentLayerId, FeatureCollection>())

  function closeStreet(target: MapLibreMap) {
    streetRef.current?.popup.remove()
    streetRef.current = null
    markStreet(target, null)
  }

  // Add sources and layers once both the map and the data are ready.
  useEffect(() => {
    if (!map || !data || layersAdded) {
      return
    }
    addLayers(map, data)
    map.on('click', 'areas-hit', event => {
      if (pickModeRef.current === 'area') {
        onSelectCell(
          String(event.features?.[0]?.properties?.cell ?? '') || null,
        )
      }
    })
    map.on('mouseenter', 'areas-hit', () => {
      if (pickModeRef.current === 'area') {
        map.getCanvas().style.cursor = 'pointer'
      }
    })
    map.on('mouseleave', 'areas-hit', () => {
      if (pickModeRef.current === 'area') {
        map.getCanvas().style.cursor = ''
      }
    })

    /** The street under a map point, on a street layer that is shown, with its whole line. */
    const streetAt = (point: maplibregl.PointLike) => {
      const layers = STREET_IDS.map(id => HIT_PREFIX + id).filter(
        id =>
          map.getLayer(id) &&
          map.getLayoutProperty(id, 'visibility') === 'visible',
      )
      const hit = layers.length
        ? map.queryRenderedFeatures(point, { layers })[0]
        : undefined
      if (hit?.id == null) {
        return null
      }
      const layer = hit.layer.id.slice(HIT_PREFIX.length) as EnvironmentLayerId
      const overlay = overlaysRef.current[layer]
      const feature: Feature | undefined =
        overlay?.status === 'ready'
          ? overlay.data.features[Number(hit.id)]
          : undefined
      return feature && overlay?.status === 'ready'
        ? {
            layer,
            key: `${layer}:${hit.id}`,
            feature,
            named: overlay.named,
          }
        : null
    }

    /** Shows the street's values: on hover until the mouse leaves it, or (pinned) after a click until closed. */
    const showStreet = (
      hit: NonNullable<ReturnType<typeof streetAt>>,
      at: maplibregl.LngLat,
      pinned: boolean,
    ) => {
      const open = streetRef.current
      if (open?.pinned && !pinned) {
        return // a clicked street stays until it's closed
      }
      if (open && !open.pinned && !pinned && open.key === hit.key) {
        open.popup.setLngLat(at)
        return
      }
      open?.popup.remove()
      const popup = new maplibregl.Popup({
        className: 'greenest-popup',
        closeButton: pinned,
        closeOnClick: false,
        focusAfterOpen: false,
        offset: 12,
        maxWidth: '260px',
      })
        .setLngLat(at)
        .setDOMContent(
          streetPopup(
            hit.layer,
            hit.feature.properties ?? {},
            labelsRef.current,
            hit.named,
          ),
        )
        .addTo(map)
      const entry = { popup, pinned, layer: hit.layer, key: hit.key }
      popup.on('close', () => {
        if (streetRef.current === entry) {
          streetRef.current = null
          markStreet(map, null)
        }
      })
      streetRef.current = entry
      markStreet(map, hit.feature)
    }

    map.on('mousemove', event => {
      if (pickModeRef.current !== 'street') {
        return
      }
      const hit = streetAt(event.point)
      map.getCanvas().style.cursor = hit ? 'pointer' : ''
      if (hit) {
        showStreet(hit, event.lngLat, false)
      } else if (!streetRef.current?.pinned) {
        closeStreet(map)
      }
    })
    map.on('mouseout', () => {
      if (!streetRef.current?.pinned) {
        closeStreet(map)
      }
    })
    map.on('click', event => {
      if (pickModeRef.current !== 'street') {
        return
      }
      const hit = streetAt(event.point)
      if (hit) {
        showStreet(hit, event.lngLat, true)
      } else {
        closeStreet(map)
      }
    })
    reshowStreetRef.current = (at, pinned) => {
      const hit = streetAt(map.project(at))
      if (hit) {
        showStreet(hit, at, pinned)
      }
    }
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
        // generateId: a hit street's id is its index in the data, to look up its whole line.
        map.addSource(id, {
          type: 'geojson',
          data: overlay.data,
          generateId: true,
        })
        // Below the invisible click layer, so areas stay clickable and the selection stays on top.
        const before = map.getLayer('areas-hit') ? 'areas-hit' : undefined
        map.addLayer({ id, source: id, ...style } as never, before)
        if (style.type === 'line') {
          addStreetHit(map, id, id)
        }
      } else if (sourceData.current.get(id) !== overlay.data) {
        // The street names arrived: the lines are cut per name now, so the
        // open popup's index points elsewhere. Open it again on the new data.
        ;(map.getSource(id) as maplibregl.GeoJSONSource).setData(overlay.data)
        const open = streetRef.current
        if (open?.layer === id) {
          const at = open.popup.getLngLat()
          const { pinned } = open
          closeStreet(map)
          map.once('idle', () => reshowStreetRef.current?.(at, pinned))
        }
      }
      sourceData.current.set(id, overlay.data)
      map.setLayoutProperty(
        id,
        'visibility',
        enabled.has(id) ? 'visible' : 'none',
      )
    }
  }, [map, overlays, enabled])

  // Streets can be pointed at only in street mode, on the street layer that is shown.
  useEffect(() => {
    if (!map) {
      return
    }
    const street = pickMode === 'street'
    for (const id of STREET_IDS) {
      if (map.getLayer(HIT_PREFIX + id)) {
        map.setLayoutProperty(
          HIT_PREFIX + id,
          'visibility',
          street && enabled.has(id) ? 'visible' : 'none',
        )
      }
    }
    const open = streetRef.current
    if (open && (!street || !enabled.has(open.layer))) {
      closeStreet(map)
    }
    if (!street) {
      map.getCanvas().style.cursor = ''
    }
  }, [map, layersAdded, overlays, enabled, pickMode])

  useEffect(() => {
    if (map && layersAdded) {
      map.setFilter('areas-selected', [
        '==',
        ['get', 'cell'],
        selectedCell ?? '',
      ])
    }
  }, [map, layersAdded, selectedCell])

  // Count layers switched on, so the recenter button can point out that the
  // new layer is drawn in Heilbronn when the view is elsewhere.
  const [layersSwitchedOn, setLayersSwitchedOn] = useState(0)
  const previousEnabled = useRef(enabled)
  useEffect(() => {
    if (Array.from(enabled).some(id => !previousEnabled.current.has(id))) {
      setLayersSwitchedOn(count => count + 1)
    }
    previousEnabled.current = enabled
  }, [enabled])

  return (
    <BaseMap
      ariaLabel={ariaLabel}
      onLoad={setMap}
      recenterHint={layersSwitchedOn}
      showRecenter
      zoom={12.5}
    />
  )
}

import type { FeatureCollection } from 'geojson'
import type maplibregl from 'maplibre-gl'

/** Riders' leisure routes are blue, apart from the green and dashed routes and the coloured reports. */
export const LEISURE_COLOR = '#2563eb'

const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] }

/**
 * A riders' leisure route (or a GPX upload not yet published, dashed) as a blue
 * line on a white casing, with a dot where it starts. Drawn below the planned
 * routes, so the trip to its start stays on top.
 */
export function drawLeisure(
  map: maplibregl.Map,
  coordinates: [number, number][] | null,
  draft: boolean,
) {
  if (!map.getSource('leisure')) {
    map.addSource('leisure', { type: 'geojson', data: EMPTY })
    map.addSource('leisure-start', { type: 'geojson', data: EMPTY })
    map.addLayer({
      id: 'leisure-casing',
      type: 'line',
      source: 'leisure',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#ffffff', 'line-width': 9 },
    })
    map.addLayer({
      id: 'leisure',
      type: 'line',
      source: 'leisure',
      layout: { 'line-join': 'round' },
      paint: { 'line-color': LEISURE_COLOR, 'line-width': 5 },
    })
    map.addLayer({
      id: 'leisure-start',
      type: 'circle',
      source: 'leisure-start',
      paint: {
        'circle-radius': 7,
        'circle-color': '#ffffff',
        'circle-stroke-color': LEISURE_COLOR,
        'circle-stroke-width': 3,
      },
    })
  }
  map.setPaintProperty('leisure', 'line-dasharray', draft ? [1.5, 1.5] : [1, 0])
  const line = coordinates && coordinates.length >= 2 ? coordinates : null
  map.getSource<maplibregl.GeoJSONSource>('leisure')?.setData(
    line
      ? {
          type: 'Feature',
          properties: {},
          geometry: { type: 'LineString', coordinates: line },
        }
      : EMPTY,
  )
  map.getSource<maplibregl.GeoJSONSource>('leisure-start')?.setData(
    line
      ? {
          type: 'Feature',
          properties: {},
          geometry: { type: 'Point', coordinates: line[0] },
        }
      : EMPTY,
  )
}

/** The bounds of `coordinates`, to fit the map to a route. */
export function lineBounds(
  coordinates: [number, number][],
): [[number, number], [number, number]] {
  const lons = coordinates.map(([lon]) => lon)
  const lats = coordinates.map(([, lat]) => lat)
  return [
    [Math.min(...lons), Math.min(...lats)],
    [Math.max(...lons), Math.max(...lats)],
  ]
}

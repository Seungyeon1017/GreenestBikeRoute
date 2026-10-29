import type { Feature, FeatureCollection, LineString } from 'geojson'
import maplibregl from 'maplibre-gl'
import type {
  RouteFlag,
  RouteKind,
  RouteProperties,
  RouteComparison as RouteResult,
  RouteSegment,
  WayKind,
} from '@/types/greenest'
import { ROUTE_COLORS } from './RouteComparison'
import { el } from './sharingLayers'

const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] }

/** The invisible, wide line that hovers and taps on either route hit. */
export const SEGMENT_HIT_LAYER = 'segment-hit'

/** Where a "Why this route?" row's stretches are drawn: orange for bad, blue for bike paths. */
export const FLAG_COLORS = { bad: '#ea580c', good: '#0284c7' }

/** Properties of one stretch on the map. MapLibre can't filter on lists, so `flags` is ",bumpy_m,stop_go_m,". */
type SegmentProps = { kind: RouteKind; index: number; flags: string }

/** A route's stretches; none from a backend that is older than them. */
function segmentsOf(route: RouteResult['route']): RouteSegment[] {
  return route.properties.segments ?? []
}

/** Both routes as one line per stretch; the shortest first, so yours is on top where they share streets. */
function segmentFeatures(result: RouteResult | null): FeatureCollection {
  if (!result) {
    return EMPTY
  }
  const routes: Array<[RouteKind, RouteResult['route']]> = [
    ['shortest', result.shortest],
    ['greenest', result.route],
  ]
  const features: Array<Feature<LineString, SegmentProps>> = []
  for (const [kind, route] of routes) {
    const coords = route.geometry.coordinates
    segmentsOf(route).forEach((s, index) =>
      features.push({
        type: 'Feature',
        geometry: {
          type: 'LineString',
          coordinates: coords.slice(s.from_index, s.to_index + 1),
        },
        properties: { kind, index, flags: `,${s.flags.join(',')},` },
      }),
    )
  }
  return { type: 'FeatureCollection', features }
}

/**
 * Creates the stretch layers the first time, then puts the current result in:
 * the flagged stretches of the chosen "Why this route?" row, the pointed-at
 * stretch, and the invisible hit line. Call after drawRoutes, so they're on top.
 */
export function drawSegments(map: maplibregl.Map, result: RouteResult | null) {
  if (!map.getSource('segments')) {
    map.addSource('segments', { type: 'geojson', data: EMPTY })
    map.addSource('segment-active', { type: 'geojson', data: EMPTY })
    const round: maplibregl.LineLayerSpecification['layout'] = {
      'line-cap': 'round',
      'line-join': 'round',
    }
    const none: maplibregl.FilterSpecification = ['==', ['get', 'flags'], '-']
    map.addLayer({
      id: 'segment-flag-casing',
      type: 'line',
      source: 'segments',
      layout: round,
      filter: none,
      paint: { 'line-color': '#ffffff', 'line-width': 11 },
    })
    map.addLayer({
      id: 'segment-flag',
      type: 'line',
      source: 'segments',
      layout: round,
      filter: none,
      paint: { 'line-color': FLAG_COLORS.bad, 'line-width': 7 },
    })
    map.addLayer({
      id: 'segment-active-casing',
      type: 'line',
      source: 'segment-active',
      layout: round,
      paint: { 'line-color': '#ffffff', 'line-width': 12 },
    })
    map.addLayer({
      id: 'segment-active',
      type: 'line',
      source: 'segment-active',
      layout: round,
      paint: { 'line-color': '#1f3d2b', 'line-width': 7 },
    })
    map.addLayer({
      id: SEGMENT_HIT_LAYER,
      type: 'line',
      source: 'segments',
      layout: round,
      paint: { 'line-color': 'rgba(0, 0, 0, 0)', 'line-width': 14 },
    })
  }
  map
    .getSource<maplibregl.GeoJSONSource>('segments')
    ?.setData(segmentFeatures(result))
}

/** Shows the stretches of both routes that count towards `flag`, or none. */
export function highlightFlag(map: maplibregl.Map, flag: RouteFlag | null) {
  if (!map.getLayer('segment-flag')) {
    return
  }
  const filter: maplibregl.FilterSpecification = flag
    ? ['in', `,${flag},`, ['get', 'flags']]
    : ['==', ['get', 'flags'], '-']
  map.setFilter('segment-flag-casing', filter)
  map.setFilter('segment-flag', filter)
  map.setPaintProperty(
    'segment-flag',
    'line-color',
    flag === 'bike_friendly_m' ? FLAG_COLORS.good : FLAG_COLORS.bad,
  )
}

/** Outlines the pointed-at stretch, or clears it. */
export function markSegment(map: maplibregl.Map, line: LineString | null) {
  map
    .getSource<maplibregl.GeoJSONSource>('segment-active')
    ?.setData(
      line ? { type: 'Feature', geometry: line, properties: {} } : EMPTY,
    )
}

/** The stretches of both routes that count towards `flag`, as one box; null if there are none. */
export function flagBounds(
  result: RouteResult,
  flag: RouteFlag,
): maplibregl.LngLatBounds | null {
  let bounds: maplibregl.LngLatBounds | null = null
  for (const route of [result.shortest, result.route]) {
    const coords = route.geometry.coordinates
    for (const s of segmentsOf(route)) {
      if (!s.flags.includes(flag)) {
        continue
      }
      for (const [lng, lat] of coords.slice(s.from_index, s.to_index + 1)) {
        bounds = bounds
          ? bounds.extend([lng, lat])
          : new maplibregl.LngLatBounds([lng, lat], [lng, lat])
      }
    }
  }
  return bounds
}

/** The stretch under a map point: yours where both routes share it. */
export function segmentAt(
  map: maplibregl.Map,
  point: maplibregl.PointLike,
  result: RouteResult | null,
): { kind: RouteKind; segment: RouteSegment; line: LineString } | null {
  if (!result || !map.getLayer(SEGMENT_HIT_LAYER)) {
    return null
  }
  const hits = map.queryRenderedFeatures(point, { layers: [SEGMENT_HIT_LAYER] })
  const hit =
    hits.find(f => f.properties.kind === 'greenest') ?? hits[0] ?? null
  if (!hit) {
    return null
  }
  const kind = hit.properties.kind as RouteKind
  const route = kind === 'greenest' ? result.route : result.shortest
  const segment = route.properties.segments[Number(hit.properties.index)]
  if (!segment) {
    return null
  }
  const line: LineString = {
    type: 'LineString',
    coordinates: route.geometry.coordinates.slice(
      segment.from_index,
      segment.to_index + 1,
    ),
  }
  return { kind, segment, line }
}

/** Texts of the stretch popup, in the page's language. */
export type SegmentLabels = {
  route: (_kind: RouteKind) => string
  unnamed: string
  way: (_kind: WayKind) => string
  /** "Sidewalk beside the road" */
  beside: (_way: string) => string
  length: (_m: number) => string
  row: (_key: string) => string
  notMeasured: string
  yes: string
  no: string
  number: (_n: number, _digits: number) => string
}

type Row = {
  key: string
  value: string
  /** Orange when it is one of the stretch's bad flags, blue for a bike path, as on the map. */
  tone?: 'bad' | 'good'
}

/**
 * What a stretch is like, for the factors the rider cares about (slider above
 * 0, from your route's settings) and anything flagged on it.
 */
function segmentRows(
  s: RouteSegment,
  settings: RouteProperties,
  labels: SegmentLabels,
): Row[] {
  const flagged = (flag: RouteFlag) => s.flags.includes(flag)
  const known = (value: number | null, show: (_v: number) => string) =>
    value == null ? labels.notMeasured : show(value)
  const percent = (v: number) => `${labels.number(v * 100, 0)} %`
  const rows: Array<Row & { on: boolean }> = [
    {
      key: 'roughness',
      value: known(s.roughness, v => labels.number(v, 0)),
      tone: flagged('bumpy_m') ? 'bad' : undefined,
      on: settings.bump_penalty > 0 || flagged('bumpy_m'),
    },
    {
      key: 'overtaking',
      value: labels.number(s.danger_points, 0),
      tone: flagged('danger_points') ? 'bad' : undefined,
      on: settings.danger_penalty > 0 || flagged('danger_points'),
    },
    {
      key: 'fineDust',
      value: known(s.pm_risk, v => labels.number(v, 2)),
      tone: flagged('bad_air_m') ? 'bad' : undefined,
      on: settings.pm_penalty > 0 || flagged('bad_air_m'),
    },
    {
      key: 'stopGo',
      value: known(s.stop_go, v => labels.number(v, 2)),
      tone: flagged('stop_go_m') ? 'bad' : undefined,
      on: settings.stop_penalty > 0 || flagged('stop_go_m'),
    },
    {
      key: 'speed',
      value: known(s.speed_kmh, v => `${labels.number(v, 0)} km/h`),
      on: settings.prefer_time,
    },
    {
      key: 'shade',
      value: known(s.shade, percent),
      tone: flagged('sunny_m') ? 'bad' : undefined,
      on: s.shade != null && (settings.shade_penalty > 0 || flagged('sunny_m')),
    },
    {
      key: 'lit',
      value: known(s.lit, percent),
      tone: flagged('unlit_m') ? 'bad' : undefined,
      on: settings.daylight === false,
    },
    {
      key: 'bikePath',
      value: s.bike_friendly ? labels.yes : labels.no,
      tone: s.bike_friendly ? 'good' : undefined,
      on: settings.prefer_bike_friendly > 0 || s.bike_friendly,
    },
  ]
  return rows.filter(r => r.on)
}

/**
 * Popup content for a pointed-at stretch: street, which route and how long,
 * then one line per factor. Built from DOM nodes with textContent, so street
 * names from OSM are never read as HTML.
 */
export function segmentPopup(
  kind: RouteKind,
  s: RouteSegment,
  settings: RouteProperties,
  labels: SegmentLabels,
  /** A button under the values, e.g. to report the stretch closed. */
  action?: { label: string; onClick: () => void },
): HTMLElement {
  const box = el(
    'div',
    'flex min-w-[12rem] flex-col gap-1 text-xs text-leaf-ink',
  )
  const title = el('span', 'flex items-center gap-2 pr-4')
  const dot = el('span', 'h-2.5 w-2.5 shrink-0 rounded-full')
  dot.style.background = ROUTE_COLORS[kind]
  title.append(
    dot,
    el(
      'strong',
      'text-sm font-semibold text-leaf-forest',
      s.name ?? (s.way ? labels.way(s.way) : labels.unnamed),
    ),
  )
  // Under a street name, what kind of way it is: "Sidewalk beside the road", or "Crossing" for the road it crosses.
  const way =
    s.name && s.way
      ? s.along && s.way !== 'crossing'
        ? labels.beside(labels.way(s.way))
        : labels.way(s.way)
      : null
  box.append(
    title,
    el(
      'span',
      'mb-0.5 text-leaf-muted',
      [way, labels.route(kind), labels.length(Math.round(s.length_m))]
        .filter(Boolean)
        .join(' · '),
    ),
  )
  for (const row of segmentRows(s, settings, labels)) {
    const line = el('span', 'flex justify-between gap-3')
    const value = el('span', 'font-semibold tabular-nums', row.value)
    if (row.tone) {
      value.style.color = FLAG_COLORS[row.tone]
    }
    line.append(el('span', 'text-leaf-muted', labels.row(row.key)), value)
    box.appendChild(line)
  }
  if (action) {
    const button = el(
      'button',
      'mt-1.5 self-start rounded-full border border-leaf-sand bg-leaf-cream px-3 py-1 font-semibold text-leaf-forest hover:bg-leaf-sand/60',
      action.label,
    )
    button.type = 'button'
    button.addEventListener('click', action.onClick)
    box.appendChild(button)
  }
  return box
}

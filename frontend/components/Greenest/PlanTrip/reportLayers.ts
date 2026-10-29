import type { FeatureCollection } from 'geojson'
import type maplibregl from 'maplibre-gl'
import type {
  ClosureCollection,
  ClosureProperties,
  ClosureStatus,
  MappingCollection,
  MappingProperties,
  ReportKind,
  ReportPick,
} from '@/types/greenest'
import { el } from './sharingLayers'

const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] }

/** Red = closed, orange = reported (routes avoid it), grey = no report lately (routes still avoid it). */
export const CLOSURE_COLORS: Record<ClosureStatus, string> = {
  closed: '#b3261e',
  reported: '#f2994a',
  unconfirmed: '#9e9e9e',
  open: '#2e7d32',
}

/** The ring of a mapping report waiting for review (not the teal/pink of shared vehicles). */
export const MAPPING_COLOR = '#5e35b1'

/** Layers a click opens a popup for, instead of setting a point. */
export const CLICKABLE_REPORT_LAYERS = ['report-closures', 'report-mapping']

const REPORT_LAYERS = ['report-closures-casing', ...CLICKABLE_REPORT_LAYERS]

function source(map: maplibregl.Map, id: string) {
  return map.getSource<maplibregl.GeoJSONSource>(id)
}

/**
 * Streets riders reported closed (thick dashed line on a white casing, coloured by
 * status) and footways waiting for review (white dot, purple ring). Drawn above the
 * routes: a closure on the route must show.
 */
export function drawReports(
  map: maplibregl.Map,
  closures: ClosureCollection | null,
  mapping: MappingCollection | null,
  visible: boolean,
) {
  if (!map.getSource('report-closures')) {
    map.addSource('report-closures', { type: 'geojson', data: EMPTY })
    map.addSource('report-mapping', { type: 'geojson', data: EMPTY })
    map.addLayer({
      id: 'report-closures-casing',
      type: 'line',
      source: 'report-closures',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#ffffff', 'line-width': 11 },
    })
    map.addLayer({
      id: 'report-closures',
      type: 'line',
      source: 'report-closures',
      layout: { 'line-join': 'round' },
      paint: {
        'line-color': [
          'match',
          ['get', 'status'],
          'closed',
          CLOSURE_COLORS.closed,
          'reported',
          CLOSURE_COLORS.reported,
          CLOSURE_COLORS.unconfirmed,
        ],
        'line-width': 7,
        'line-dasharray': [1.5, 1],
      },
    })
    map.addLayer({
      id: 'report-mapping',
      type: 'circle',
      source: 'report-mapping',
      paint: {
        'circle-radius': 6,
        'circle-color': '#ffffff',
        'circle-stroke-color': MAPPING_COLOR,
        'circle-stroke-width': 2.5,
      },
    })
  }
  source(map, 'report-closures')?.setData(closures ?? EMPTY)
  source(map, 'report-mapping')?.setData(mapping ?? EMPTY)
  for (const id of REPORT_LAYERS) {
    map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none')
  }
}

export type ReportLabels = {
  /** "Closed. 2 reports, until Thu 5 Nov." */
  closure: (_p: ClosureProperties) => string
  stillClosed: string
  openAgain: string
  mappingTitle: (_p: MappingProperties) => string
  /** "Rider's note", before what the reporter wrote. */
  noteLabel: string
}

/** What the reporter wrote, labelled so it doesn't read as the app's own text. */
function noteLine(note: string, labels: ReportLabels): HTMLElement {
  const line = el('span', 'text-leaf-muted')
  line.append(el('span', 'font-semibold', `${labels.noteLabel}: `), note)
  return line
}

/**
 * Popup content for a clicked closure (with the one-tap answers) or mapping report.
 * Built from DOM nodes with textContent, so riders' notes are never read as HTML.
 */
export function reportPopup(
  layer: string,
  properties: Record<string, unknown>,
  labels: ReportLabels,
  onAnswer: (_segment: string, _stillClosed: boolean) => void,
): HTMLElement {
  const box = el(
    'div',
    'flex min-w-[12rem] flex-col gap-2 text-xs text-leaf-ink',
  )
  if (layer === 'report-mapping') {
    const p = properties as unknown as MappingProperties
    box.appendChild(
      el(
        'strong',
        'pr-4 text-sm font-semibold text-leaf-forest',
        labels.mappingTitle(p),
      ),
    )
    if (p.note) {
      box.appendChild(noteLine(p.note, labels))
    }
    return box
  }
  const p = properties as unknown as ClosureProperties
  const title = el('span', 'flex items-start gap-2 pr-4')
  const swatch = el('span', 'mt-1 h-1.5 w-4 shrink-0 rounded-full')
  swatch.style.background = CLOSURE_COLORS[p.status]
  title.append(swatch, el('span', '', labels.closure(p)))
  box.appendChild(title)
  if (p.note) {
    box.appendChild(noteLine(p.note, labels))
  }
  const buttons = el('div', 'flex gap-2')
  for (const [text, stillClosed] of [
    [labels.stillClosed, true],
    [labels.openAgain, false],
  ] as const) {
    const button = el(
      'button',
      'rounded-full border border-leaf-sand bg-leaf-cream px-3 py-1 font-semibold text-leaf-forest hover:bg-leaf-sand/60',
      text,
    )
    button.type = 'button'
    button.addEventListener('click', () => onAnswer(p.segment, stillClosed))
    buttons.appendChild(button)
  }
  box.appendChild(buttons)
  return box
}

/** Picked for a report: red for a closed street, the mapping purple for a footway. */
const PICK_COLORS: Record<ReportKind, string> = {
  closure: CLOSURE_COLORS.closed,
  rideable: MAPPING_COLOR,
  other: MAPPING_COLOR,
}

/**
 * The streets or footways picked for the report being written, as a thick line
 * on a white casing above everything else on the map, or none.
 */
export function drawReportPicks(
  map: maplibregl.Map,
  picks: ReportPick[],
  kind: ReportKind | null,
) {
  if (!map.getSource('report-picks')) {
    map.addSource('report-picks', { type: 'geojson', data: EMPTY })
    map.addLayer({
      id: 'report-picks-casing',
      type: 'line',
      source: 'report-picks',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#ffffff', 'line-width': 12 },
    })
    map.addLayer({
      id: 'report-picks',
      type: 'line',
      source: 'report-picks',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': CLOSURE_COLORS.closed, 'line-width': 7 },
    })
  }
  if (kind) {
    map.setPaintProperty('report-picks', 'line-color', PICK_COLORS[kind])
  }
  source(map, 'report-picks')?.setData({
    type: 'FeatureCollection',
    features: picks.map(p => ({
      type: 'Feature',
      geometry: p.geometry,
      properties: { key: p.key },
    })),
  })
}

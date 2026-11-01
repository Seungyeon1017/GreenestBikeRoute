import {
  popupBox,
  popupRow,
  type SegmentLabels,
  type StreetPlace,
  streetTitle,
} from '@/components/Greenest/PlanTrip/routeSegments'
import { el } from '@/components/Greenest/PlanTrip/sharingLayers'
import type { EnvironmentLayerId } from '@/types/greenest'

/** Texts of the street popup: Plan a trip's, plus a few only the Overview layers need. */
export type StreetLabels = SegmentLabels & {
  /** The layer's name, e.g. "Overall score". */
  layer: (_id: EnvironmentLayerId) => string
  /** Which time of day the shade layer shows. */
  shadeNote: string
  ridden: string
  lightsPer100m: string
  /** In place of the name while the backend is still naming the streets. */
  nameLoading: string
  whyTitle: string
  whyNone: string
  /** A factor's name, e.g. "Traffic". */
  why: (_key: string) => string
  /** "feels 1.5× longer", or "shorter" for a credit. */
  whyFactor: (_factor: string, _credit: boolean) => string
}

/**
 * The score's factors, worst first, orange when they cost points and blue when
 * they earn credit, like Plan a trip's flags. MapLibre hands nested properties
 * over as a JSON string.
 */
function whyRows(raw: unknown, labels: StreetLabels): HTMLElement[] {
  let why: Record<string, number> = {}
  try {
    why = typeof raw === 'string' ? JSON.parse(raw) : ((raw as never) ?? {})
  } catch {
    return []
  }
  const entries = Object.entries(why).sort((a, b) => b[1] - a[1])
  return [
    el('strong', 'mt-1 text-leaf-forest', labels.whyTitle),
    ...(entries.length === 0
      ? [el('span', 'text-leaf-muted', labels.whyNone)]
      : entries.map(([key, factor]) =>
          popupRow(
            labels.why(key),
            labels.whyFactor(
              labels.number(factor < 1 ? 1 / factor : factor, 2),
              factor < 1,
            ),
            factor < 1 ? 'good' : 'bad',
          ),
        )),
  ]
}

/** The pointed-at street's values on the street layer that is switched on, with Plan a trip's row names. */
function streetRows(
  id: EnvironmentLayerId,
  p: Record<string, unknown>,
  labels: StreetLabels,
): HTMLElement[] {
  const num = (key: string) =>
    typeof p[key] === 'number' ? (p[key] as number) : null
  const known = (value: number | null, show: (_v: number) => string) =>
    value == null ? labels.notMeasured : show(value)
  const percent = (v: number) => `${labels.number(v * 100, 0)} %`
  const row = (key: string, value: string, tone?: 'good') =>
    popupRow(labels.row(key), value, tone)
  switch (id) {
    case 'environmental-score':
      return [
        popupRow(
          labels.layer(id),
          known(num('score'), v => `${labels.number(v, 0)} / 100`),
        ),
        popupRow(labels.ridden, p.ridden ? labels.yes : labels.no),
        ...whyRows(p.why, labels),
      ]
    case 'surface-roughness':
      return [
        row(
          'roughness',
          known(num('roughness'), v => labels.number(v, 0)),
        ),
      ]
    case 'bike-friendly':
      return [row('bikePath', labels.yes, 'good')]
    case 'stop-and-go':
      return [
        row(
          'stopGo',
          known(num('stop_go'), v => labels.number(v, 2)),
        ),
      ]
    case 'speed':
      return [
        row(
          'speed',
          known(num('speed_kmh'), v => `${labels.number(v, 0)} km/h`),
        ),
      ]
    case 'shade':
      return [
        row('shade', known(num('shade'), percent)),
        el('span', 'text-[11px] text-leaf-muted/70', labels.shadeNote),
      ]
    case 'lighting': {
      const lights = num('lights_per_100m')
      return [
        row('lit', known(num('lit'), percent)),
        ...(lights == null
          ? []
          : [popupRow(labels.lightsPer100m, labels.number(lights, 1))]),
      ]
    }
    default:
      return []
  }
}

/**
 * Popup content for a pointed-at street, like a stretch on Plan a trip: its
 * name (a sidewalk takes the road's beside it) and kind of way, then the
 * layer's values. Not `named` yet (the backend just started): "Loading
 * street name…" in place of the name, the values already.
 */
export function streetPopup(
  id: EnvironmentLayerId,
  properties: Record<string, unknown>,
  labels: StreetLabels,
  named = true,
): HTMLElement {
  const place: StreetPlace = {
    name: typeof properties.name === 'string' ? properties.name : null,
    way: (properties.way as StreetPlace['way']) ?? null,
    along: properties.along === true,
  }
  const box = popupBox()
  box.append(
    ...(named
      ? streetTitle(place, labels)
      : [
          el(
            'span',
            'animate-pulse pr-4 text-sm italic text-leaf-muted',
            labels.nameLoading,
          ),
        ]),
    ...streetRows(id, properties, labels),
  )
  return box
}

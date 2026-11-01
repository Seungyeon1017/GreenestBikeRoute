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
 * layer's values.
 */
export function streetPopup(
  id: EnvironmentLayerId,
  properties: Record<string, unknown>,
  labels: StreetLabels,
): HTMLElement {
  const place: StreetPlace = {
    name: typeof properties.name === 'string' ? properties.name : null,
    way: (properties.way as StreetPlace['way']) ?? null,
    along: properties.along === true,
  }
  const box = popupBox()
  box.append(
    ...streetTitle(place, labels),
    ...streetRows(id, properties, labels),
  )
  return box
}

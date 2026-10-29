import type { FeatureCollection } from 'geojson'
import type maplibregl from 'maplibre-gl'
import type {
  GeofencingCollection,
  SharingTrip,
  SharingVehicleKind,
  VehicleCollection,
  VehicleProperties,
  ZoneCollection,
  ZoneProperties,
} from '@/types/greenest'
import {
  LOW_BATTERY_PCT,
  safeRentUrl,
  VEHICLE_COLORS,
  WALK_COLOR,
} from './SharingCard'
import { ROUTE_COLORS } from './RouteComparison'

const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] }

/** Layers a click opens a popup for, instead of setting a point. */
export const CLICKABLE_SHARING_LAYERS = ['sharing-vehicles', 'sharing-zones']

function source(map: maplibregl.Map, id: string) {
  return map.getSource<maplibregl.GeoJSONSource>(id)
}

/** Parking zones (white rings) and free vehicles (teal e-bike, pink e-scooter, faded when the battery is low). */
export function drawSharing(
  map: maplibregl.Map,
  vehicles: VehicleCollection | null,
  zones: ZoneCollection | null,
) {
  if (!map.getSource('sharing-vehicles')) {
    map.addSource('sharing-zones', { type: 'geojson', data: EMPTY })
    map.addSource('sharing-vehicles', { type: 'geojson', data: EMPTY })
    map.addLayer({
      id: 'sharing-zones',
      type: 'circle',
      source: 'sharing-zones',
      paint: {
        'circle-radius': 6,
        'circle-color': '#ffffff',
        'circle-stroke-color': WALK_COLOR,
        'circle-stroke-width': 2,
      },
    })
    const low = [
      '<',
      ['coalesce', ['get', 'battery_pct'], 100],
      LOW_BATTERY_PCT,
    ] as maplibregl.ExpressionSpecification
    map.addLayer({
      id: 'sharing-vehicles',
      type: 'circle',
      source: 'sharing-vehicles',
      paint: {
        'circle-radius': 5,
        'circle-color': [
          'match',
          ['get', 'vehicle'],
          'scooter',
          VEHICLE_COLORS.scooter,
          VEHICLE_COLORS.bike,
        ],
        'circle-opacity': ['case', low, 0.35, 0.95],
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 1,
        'circle-stroke-opacity': ['case', low, 0.4, 1],
      },
    })
  }
  source(map, 'sharing-zones')?.setData(zones ?? EMPTY)
  source(map, 'sharing-vehicles')?.setData(vehicles ?? EMPTY)
}

/** The provider's zones where this kind may not be left (`no`) or only at a parking zone. */
function fencesFor(
  fences: GeofencingCollection | null,
  kind: SharingVehicleKind,
): FeatureCollection {
  if (!fences) {
    return EMPTY
  }
  return {
    type: 'FeatureCollection',
    features: fences.features
      .filter(f => f.properties[kind] && f.properties[kind] !== 'anywhere')
      .map(f => ({ ...f, properties: { rule: f.properties[kind] } })),
  }
}

/**
 * The rented-vehicle trip: no-parking zones underneath, the same trip without the
 * rider's settings as a grey dashed line (like the shortest route), then the walks
 * (dark grey dotted) and the ride (vehicle colour), both on a white casing.
 */
export function drawTrip(
  map: maplibregl.Map,
  trip: SharingTrip | null,
  fences: GeofencingCollection | null,
  plainTrip: SharingTrip | null = null,
) {
  if (!map.getSource('trip')) {
    map.addSource('trip-fences', { type: 'geojson', data: EMPTY })
    map.addSource('trip-plain', { type: 'geojson', data: EMPTY })
    map.addSource('trip', { type: 'geojson', data: EMPTY })
    map.addLayer({
      id: 'trip-fences',
      type: 'fill',
      source: 'trip-fences',
      paint: {
        'fill-color': ['match', ['get', 'rule'], 'no', '#e53935', '#fb8c00'],
        'fill-opacity': 0.18,
        'fill-outline-color': [
          'match',
          ['get', 'rule'],
          'no',
          '#c62828',
          '#ef6c00',
        ],
      },
    })
    map.addLayer({
      id: 'trip-plain',
      type: 'line',
      source: 'trip-plain',
      layout: { 'line-join': 'round' },
      paint: {
        'line-color': ROUTE_COLORS.shortest,
        'line-width': 5,
        'line-dasharray': [2, 2],
      },
    })
    map.addLayer({
      id: 'trip-casing',
      type: 'line',
      source: 'trip',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#ffffff',
        'line-width': ['match', ['get', 'mode'], 'walk', 8, 10],
        'line-opacity': 0.9,
      },
    })
    map.addLayer({
      id: 'trip-walk',
      type: 'line',
      source: 'trip',
      filter: ['==', ['get', 'mode'], 'walk'],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': WALK_COLOR,
        'line-width': 4,
        'line-dasharray': [0.1, 2],
      },
    })
    map.addLayer({
      id: 'trip-ride',
      type: 'line',
      source: 'trip',
      filter: ['!=', ['get', 'mode'], 'walk'],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': [
          'match',
          ['get', 'mode'],
          'scooter',
          VEHICLE_COLORS.scooter,
          VEHICLE_COLORS.bike,
        ],
        'line-width': 6,
      },
    })
  }
  source(map, 'trip')?.setData(
    trip ? { type: 'FeatureCollection', features: trip.legs } : EMPTY,
  )
  source(map, 'trip-plain')?.setData(
    trip && plainTrip
      ? { type: 'FeatureCollection', features: plainTrip.legs }
      : EMPTY,
  )
  source(map, 'trip-fences')?.setData(
    trip ? fencesFor(fences, trip.vehicle.properties.vehicle) : EMPTY,
  )
}

/** Fades your route and the shortest one while the rented-vehicle trip is shown. */
export function fadeRoutes(map: maplibregl.Map, faded: boolean) {
  const opacity = faded ? 0.25 : 1
  for (const id of [
    'shortest',
    'greenest',
    'grade-casing',
    'grade',
    'segment-flag-casing',
    'segment-flag',
  ]) {
    if (map.getLayer(id)) {
      map.setPaintProperty(id, 'line-opacity', opacity)
    }
  }
}

type Labels = {
  vehicle: (_kind: SharingVehicleKind) => string
  away: (_m: number) => string
  range: (_km: number) => string
  /** The feed's price, e.g. "€1.00 to unlock + €0.44/min", in the page's language. */
  price: (_price: string) => string
  rent: (_provider: string) => string
  zoneCounts: (_bikes: number, _scooters: number) => string
}

/** A DOM element with classes and (safe) text. */
export function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag)
  node.className = className
  if (text !== undefined) {
    node.textContent = text
  }
  return node
}

/** Red under LOW_BATTERY_PCT, amber under half, green above. */
function batteryColor(pct: number) {
  return pct < LOW_BATTERY_PCT ? '#d63b3b' : pct < 50 ? '#f2994a' : '#2e7d32'
}

/** A small battery gauge with the percentage, e.g. [▮▮▮  ] 48 %. */
function battery(pct: number | null) {
  const row = el('span', 'flex items-center gap-1.5')
  const gauge = el(
    'span',
    'relative inline-block h-2.5 w-6 rounded-sm border border-leaf-ink/40 p-px',
  )
  if (pct != null) {
    const fill = el('span', 'block h-full rounded-[1px]')
    fill.style.width = `${Math.max(4, pct)}%`
    fill.style.background = batteryColor(pct)
    gauge.appendChild(fill)
  }
  row.append(gauge, el('span', 'tabular-nums', `${pct ?? '?'} %`))
  return row
}

/**
 * Popup content for a clicked vehicle or zone. Built from DOM nodes with
 * textContent, so text from the feed is never read as HTML.
 */
export function sharingPopup(
  layer: string,
  properties: Record<string, unknown>,
  labels: Labels,
): HTMLElement {
  const box = el(
    'div',
    'flex min-w-[11rem] flex-col gap-1.5 text-xs text-leaf-ink',
  )
  if (layer === 'sharing-zones') {
    const z = properties as unknown as ZoneProperties
    box.append(
      el('strong', 'pr-4 text-sm font-semibold text-leaf-forest', z.name),
      el(
        'span',
        'text-leaf-muted',
        labels.zoneCounts(z.bikes_available, z.scooters_available),
      ),
    )
    return box
  }
  const p = properties as unknown as VehicleProperties

  // Title: coloured dot (as on the map) and "Dott E-Bike".
  const title = el('span', 'flex items-center gap-2 pr-4')
  const dot = el('span', 'h-2.5 w-2.5 shrink-0 rounded-full')
  dot.style.background = VEHICLE_COLORS[p.vehicle]
  title.append(
    dot,
    el(
      'strong',
      'text-sm font-semibold text-leaf-forest',
      `${p.provider} ${labels.vehicle(p.vehicle)}`,
    ),
  )
  box.appendChild(title)

  // Battery gauge and range on one line.
  const charge = el('span', 'flex items-center gap-2')
  charge.appendChild(battery(p.battery_pct))
  if (p.range_m != null) {
    charge.appendChild(
      el(
        'span',
        'text-leaf-muted',
        `· ${labels.range(Math.round(p.range_m / 1000))}`,
      ),
    )
  }
  box.appendChild(charge)

  if (p.distance_m != null) {
    box.appendChild(el('span', 'text-leaf-muted', labels.away(p.distance_m)))
  }
  if (p.price) {
    box.appendChild(el('span', 'text-leaf-ink/80', labels.price(p.price)))
  }
  const url = safeRentUrl(p.rent_url)
  if (url) {
    const a = el(
      'a',
      'mt-1 rounded-full bg-leaf-forest px-3 py-1.5 text-center font-medium text-leaf-cream no-underline hover:bg-leaf-fern',
      `${labels.rent(p.provider)} ↗`,
    )
    a.href = url
    a.target = '_blank'
    a.rel = 'noreferrer'
    box.appendChild(a)
  }
  return box
}

/** A round (pick-up) or square (leave it) pin with a short text, for the trip. */
export function tripPin(text: string, color: string, square = false) {
  const el = document.createElement('div')
  el.textContent = text
  el.style.cssText =
    `width:24px;height:24px;border:2px solid #fff;border-radius:${square ? '5px' : '50%'};` +
    `background:${color};color:#fff;font:700 13px/20px system-ui;text-align:center;` +
    'box-shadow:0 1px 4px rgba(0,0,0,.4)'
  return el
}

export type PinInfo = {
  /** Badge as on the pin ("1" or "P") and its colour; square for P. */
  badge: string
  color: string
  square?: boolean
  title: string
  /** Battery gauge of the vehicle (pick-up pin only). */
  battery?: number | null
  lines: string[]
  rent?: { url: string; label: string }
}

/** Popup content for a trip pin, in the same style as the vehicle popup. */
export function pinPopup(info: PinInfo): HTMLElement {
  const box = el(
    'div',
    'flex min-w-[11rem] flex-col gap-1.5 text-xs text-leaf-ink',
  )
  const title = el('span', 'flex items-center gap-2 pr-4')
  const badge = el(
    'span',
    'flex h-5 w-5 shrink-0 items-center justify-center text-[11px] font-bold text-white',
    info.badge,
  )
  badge.style.background = info.color
  badge.style.borderRadius = info.square ? '4px' : '9999px'
  title.append(
    badge,
    el('strong', 'text-sm font-semibold text-leaf-forest', info.title),
  )
  box.appendChild(title)
  if (info.battery !== undefined) {
    box.appendChild(battery(info.battery))
  }
  info.lines.forEach(text =>
    box.appendChild(el('span', 'text-leaf-ink/80', text)),
  )
  if (info.rent) {
    const a = el(
      'a',
      'mt-1 rounded-full bg-leaf-forest px-3 py-1.5 text-center font-medium text-leaf-cream no-underline hover:bg-leaf-fern',
      `${info.rent.label} ↗`,
    )
    a.href = info.rent.url
    a.target = '_blank'
    a.rel = 'noreferrer'
    box.appendChild(a)
  }
  return box
}

/**
 * Shows `popup` at a pin while a mouse hovers it, and on tap or click
 * (touch screens); a second tap, the × or a click on the map closes it.
 * Clicks on the pin don't reach the map, so they never move the start or end.
 */
export function attachPinPopup(
  marker: maplibregl.Marker,
  map: maplibregl.Map,
  popup: maplibregl.Popup,
) {
  const pin = marker.getElement()
  let pinned = false
  pin.style.cursor = 'pointer'
  popup.on('close', () => {
    pinned = false
  })
  // Closing waits a moment, so the mouse can move from the pin onto the popup
  // (e.g. to its rent button); entering either one cancels it.
  let closing: ReturnType<typeof setTimeout> | undefined
  const stay = () => clearTimeout(closing)
  const leave = (e: PointerEvent) => {
    if (e.pointerType === 'mouse' && !pinned) {
      closing = setTimeout(() => popup.remove(), 200)
    }
  }
  const show = () => {
    stay()
    if (!popup.isOpen()) {
      popup.setLngLat(marker.getLngLat()).addTo(map)
      const element = popup.getElement()
      element.addEventListener('pointerenter', stay)
      element.addEventListener('pointerleave', leave)
    }
  }
  pin.addEventListener('pointerenter', e => {
    if (e.pointerType === 'mouse') {
      show()
    }
  })
  pin.addEventListener('pointerleave', leave)
  for (const type of [
    'mousedown',
    'mouseup',
    'touchstart',
    'touchend',
    'dblclick',
  ]) {
    pin.addEventListener(type, e => e.stopPropagation())
  }
  pin.addEventListener('click', e => {
    e.stopPropagation()
    if (pinned) {
      popup.remove()
      return
    }
    pinned = true
    show()
  })
}

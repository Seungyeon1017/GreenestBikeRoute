import type { Feature, FeatureCollection, Point } from 'geojson'
import type maplibregl from 'maplibre-gl'
import type { TransitStopCollection } from '@/types/greenest'

const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] }

/** The S-Bahn disc's green (also the search list's S badge) and the train disc's blue. */
export const SBAHN_COLOR = '#408335'
export const TRAIN_COLOR = '#2f5d8c'

/** lucide's train-front icon (24×24, stroked), drawn into the train disc. */
const TRAIN_PATHS = [
  'M8 3.1V7a4 4 0 0 0 8 0V3.1',
  'm9 15-1-1',
  'm15 15 1-1',
  'M9 19c-2.8 0-5-2.2-5-5v-4a8 8 0 0 1 16 0v4c0 2.8-2.2 5-5 5Z',
  'm8 19-2 3',
  'm16 19 2 3',
]

const SIZE = 22 // icon size in CSS pixels
const RATIO = 2 // drawn at twice the size, sharp on high-DPI screens

export type StationKind = 'sbahn' | 'train'

/** A station only S-Bahn lines call at (S4, S41, ...) is an S-Bahn stop; one with any other train line is a station. */
export function stationKind(lines: string[]): StationKind {
  return lines.every(line => /^S\d/.test(line)) ? 'sbahn' : 'train'
}

function disc(
  color: string,
  drawInside: (_ctx: CanvasRenderingContext2D) => void,
) {
  const px = SIZE * RATIO
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = px
  const ctx = canvas.getContext('2d')!
  ctx.scale(RATIO, RATIO)
  ctx.beginPath()
  ctx.arc(SIZE / 2, SIZE / 2, SIZE / 2 - 1, 0, 2 * Math.PI)
  ctx.fillStyle = color
  ctx.fill()
  ctx.lineWidth = 1.5
  ctx.strokeStyle = '#ffffff'
  ctx.stroke()
  drawInside(ctx)
  return ctx.getImageData(0, 0, px, px)
}

/** The S disc and the train disc as map images `station-sbahn` and `station-train`. */
export function addStationIcons(map: maplibregl.Map) {
  if (!map.hasImage('station-sbahn')) {
    const image = disc(SBAHN_COLOR, ctx => {
      ctx.fillStyle = '#ffffff'
      ctx.font = `bold ${SIZE * 0.62}px system-ui, sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText('S', SIZE / 2, SIZE / 2 + 1)
    })
    map.addImage('station-sbahn', image, { pixelRatio: RATIO })
  }
  if (!map.hasImage('station-train')) {
    const image = disc(TRAIN_COLOR, ctx => {
      const scale = (SIZE * 0.62) / 24
      ctx.translate(SIZE * 0.19, SIZE * 0.19)
      ctx.scale(scale, scale)
      ctx.strokeStyle = '#ffffff'
      ctx.lineWidth = 2.2
      ctx.lineCap = 'round'
      ctx.lineJoin = 'round'
      TRAIN_PATHS.forEach(d => ctx.stroke(new Path2D(d)))
    })
    map.addImage('station-train', image, { pixelRatio: RATIO })
  }
}

/** From this zoom on every stop of a station has its own name underneath. */
const STOP_NAMES_ZOOM = 17

/**
 * Stadtbahn and train stations: an S disc or a train disc at each stop of the station (the
 * Hauptbahnhof has its platforms and the Stadtbahn stop in front), each for the lines calling
 * there. The station's name is underneath its main stop from zoom 13 on (names that would
 * overlap are left out); from zoom 17 on each stop has its own name. Pass null to hide them.
 */
export function drawStations(
  map: maplibregl.Map,
  stops: TransitStopCollection | null,
) {
  if (!map.getSource('stations')) {
    addStationIcons(map)
    map.addSource('stations', { type: 'geojson', data: EMPTY })
    map.addLayer({
      id: 'stations',
      type: 'symbol',
      source: 'stations',
      layout: {
        'icon-image': ['concat', 'station-', ['get', 'kind']],
        'icon-size': ['interpolate', ['linear'], ['zoom'], 10, 0.7, 14, 1],
        'icon-allow-overlap': true,
        // S-Bahn stops on top where a train station sits next to one.
        'symbol-sort-key': ['match', ['get', 'kind'], 'sbahn', 1, 0],
        'text-field': [
          'step',
          ['zoom'],
          '',
          13,
          ['case', ['get', 'main'], ['get', 'name'], ''],
          STOP_NAMES_ZOOM,
          ['get', 'stop_name'],
        ],
        'text-font': [
          'Montserrat Medium',
          'Open Sans Regular',
          'Noto Sans Regular',
        ],
        'text-size': 11,
        'text-anchor': 'top',
        'text-offset': [0, 1.1],
        'text-optional': true,
        'text-max-width': 9,
      },
      paint: {
        'text-color': '#1f3b2c',
        'text-halo-color': '#ffffff',
        'text-halo-width': 1.5,
      },
    })
  }
  const features: Feature<Point>[] = (stops?.features ?? []).flatMap(f => {
    const { stop_id, name, lines } = f.properties
    const [lon, lat] = f.geometry.coordinates
    // An older backend sends no stops: the station's own point.
    const parts = f.properties.stops?.length
      ? f.properties.stops
      : [{ stop_place: stop_id, name, lon, lat, lines }]
    return parts.map((part, i) => ({
      type: 'Feature' as const,
      geometry: { type: 'Point' as const, coordinates: [part.lon, part.lat] },
      properties: {
        stop_id,
        name,
        stop_place: part.stop_place,
        stop_name: part.name,
        main: i === 0,
        kind: stationKind(part.lines) satisfies StationKind,
      },
    }))
  })
  map
    .getSource<maplibregl.GeoJSONSource>('stations')
    ?.setData({ type: 'FeatureCollection', features })
}
